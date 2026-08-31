import numpy as np
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Protocol
import httpx
import asyncio

from loguru import logger
from sqlalchemy import delete, select

from app.infrastructure.database.models.memory import MemoryVector
from .store import _MemoryDB, _derive_owner_key


@dataclass
class ScoredFact:
    fact_id: str
    score: float
    category: str = ""


@dataclass
class VectorEntry:
    fact_id: str
    content: str
    category: str = ""
    scope: str = ""
    conversation_id: str = ""
    vector: np.ndarray = field(default_factory=lambda: np.array([]))


class EmbeddingProvider(Protocol):
    @property
    def dim(self) -> int: ...
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class LLMEmbeddingProvider:
    """基于 LLM API 的嵌入提供器，通过 OpenAI 兼容接口获取文本向量。"""

    # 已知模型的维度映射
    _KNOWN_DIMS: dict[str, int] = {
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,
    }

    def __init__(self, provider: Any, model: str = "text-embedding-3-small") -> None:
        self._provider = provider
        self._model = model
        if model in self._KNOWN_DIMS:
            self._dim = self._KNOWN_DIMS[model]
        else:
            self._dim = 1536
            logger.warning(f"[VectorStore] Unknown embedding model '{model}', defaulting to dim={self._dim}")

    @property
    def dim(self) -> int:
        return self._dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        base_url = getattr(self._provider, "base_url", "https://api.openai.com/v1")
        api_key = getattr(self._provider, "api_key", None)
        if not api_key:
            raise ValueError("Embedding provider api_key is missing or empty")

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{base_url}/embeddings",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": self._model, "input": texts},
            )
            resp.raise_for_status()
            return [d["embedding"] for d in resp.json()["data"]]


class LocalEmbeddingProvider:
    def __init__(self, model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model_name)
        self._dim = self.model.get_sentence_embedding_dimension()

    @property
    def dim(self) -> int:
        return self._dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        loop = asyncio.get_running_loop()
        vectors = await loop.run_in_executor(None, self.model.encode, texts)
        return vectors.tolist()


class VectorStore:
    """向量存储 — SQLite BLOB 按行存储 + 增量写（替代 vectors.npz 全量重写）。

    设计（前端后端项目锐评 · 高优先级 #3）：
    - 每条向量一行（memory_vectors.fact_id 主键），add/batch_add/remove
      立即单事务落库，进程崩溃不丢增量；
    - save() 兼容保留（历史调用点），但已无需全量重写（数据实时持久化）；
    - 检索仍走进程内 cache + 分类/作用域/对话索引（与旧实现一致），
      冷启动时 _load() 一次性从 SQLite 读回。
    - owner_key 行级隔离：主人轨 / 平台用户轨的向量互不串扰。
    """

    def __init__(self, storage_path: Path, provider: EmbeddingProvider, owner_key: str | None = None):
        self._path = Path(storage_path)
        self._provider = provider
        self._owner_key = owner_key or _derive_owner_key(self._path)
        self._db = _MemoryDB(self._path)
        self._cache: dict[str, VectorEntry] = {}
        self._category_index: dict[str, set[str]] = {}
        self._scope_index: dict[str, set[str]] = {}
        self._conv_index: dict[str, set[str]] = {}
        self._loaded = False

    def close(self) -> None:
        self._db.close()

    def _ensure_loaded(self):
        if not self._loaded:
            self._load()
            self._loaded = True

    # ── 持久化（增量写，单事务） ──

    @staticmethod
    def _vector_to_blob(vector: np.ndarray) -> bytes:
        return np.asarray(vector, dtype=np.float32).tobytes()

    @staticmethod
    def _blob_to_vector(blob: bytes) -> np.ndarray:
        return np.frombuffer(blob, dtype=np.float32)

    def _row_from_entry(self, entry: VectorEntry) -> MemoryVector:
        return MemoryVector(
            fact_id=entry.fact_id,
            owner_key=self._owner_key,
            content=entry.content,
            category=entry.category,
            scope=entry.scope,
            conversation_id=entry.conversation_id,
            vector=self._vector_to_blob(entry.vector),
        )

    def _persist_upsert(self, entry: VectorEntry) -> None:
        """单行 upsert（SQLite INSERT OR REPLACE 语义）。"""
        with self._db.session() as session:
            row = session.get(MemoryVector, entry.fact_id)
            if row is None:
                session.add(self._row_from_entry(entry))
            else:
                row.content = entry.content
                row.category = entry.category
                row.scope = entry.scope
                row.conversation_id = entry.conversation_id
                row.vector = self._vector_to_blob(entry.vector)
            session.commit()

    # ── 写入 ──

    async def add(self, entry: VectorEntry) -> None:
        self._ensure_loaded()
        if entry.vector.size == 0:
            vectors = await self._provider.embed([entry.content])
            entry.vector = np.array(vectors[0], dtype=np.float32)
        self._cache[entry.fact_id] = entry
        self._update_indexes(entry, add=True)
        try:
            self._persist_upsert(entry)
        except Exception as e:
            logger.warning(f"[VectorStore] Persist add failed for {entry.fact_id}: {e}")

    async def batch_add(self, entries: list[VectorEntry]) -> None:
        self._ensure_loaded()
        if not entries:
            return

        texts = [e.content for e in entries]
        vectors = await self._provider.embed(texts)

        for i, entry in enumerate(entries):
            entry.vector = np.array(vectors[i], dtype=np.float32)
            self._cache[entry.fact_id] = entry
            self._update_indexes(entry, add=True)

        # 批量落盘（单事务）
        try:
            with self._db.session() as session:
                for entry in entries:
                    row = session.get(MemoryVector, entry.fact_id)
                    if row is None:
                        session.add(self._row_from_entry(entry))
                    else:
                        row.content = entry.content
                        row.category = entry.category
                        row.scope = entry.scope
                        row.conversation_id = entry.conversation_id
                        row.vector = self._vector_to_blob(entry.vector)
                session.commit()
        except Exception as e:
            logger.warning(f"[VectorStore] Batch persist failed ({len(entries)} entries): {e}")

    async def remove(self, fact_id: str) -> None:
        self._ensure_loaded()
        if fact_id not in self._cache:
            return
        entry = self._cache[fact_id]
        self._update_indexes(entry, add=False)
        del self._cache[fact_id]
        try:
            with self._db.session() as session:
                session.execute(
                    delete(MemoryVector).where(
                        MemoryVector.fact_id == fact_id,
                        MemoryVector.owner_key == self._owner_key,
                    )
                )
                session.commit()
        except Exception as e:
            logger.warning(f"[VectorStore] Persist remove failed for {fact_id}: {e}")

    async def delete_by_conversation(self, conversation_id: str) -> int:
        self._ensure_loaded()
        to_delete = list(self._conv_index.get(conversation_id, set()))
        for fact_id in to_delete:
            entry = self._cache.get(fact_id)
            if entry is None:
                continue
            self._update_indexes(entry, add=False)
            del self._cache[fact_id]
        if to_delete:
            try:
                with self._db.session() as session:
                    session.execute(
                        delete(MemoryVector).where(
                            MemoryVector.owner_key == self._owner_key,
                            MemoryVector.conversation_id == conversation_id,
                        )
                    )
                    session.commit()
            except Exception as e:
                logger.warning(f"[VectorStore] Persist delete_by_conversation failed: {e}")
        return len(to_delete)

    # ── 检索（进程内 cache + 索引，与旧实现一致） ──

    async def search(
        self, query: str, k: int = 10,
        category: str | None = None, scope: str | None = None,
        conversation_id: str | None = None, min_score: float = 0.0
    ) -> list[ScoredFact]:
        self._ensure_loaded()
        query_vec = np.array((await self._provider.embed([query]))[0], dtype=np.float32)
        candidates = self._get_candidates(category, scope, conversation_id)

        results = []
        for fid in candidates:
            entry = self._cache.get(fid)
            if entry is None:
                continue
            score = self._cosine(query_vec, entry.vector)
            if score >= min_score:
                results.append((fid, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return [
            ScoredFact(fact_id=fid, score=score, category=self._cache[fid].category)
            for fid, score in results[:k] if fid in self._cache
        ]

    async def dedup_check(
        self, content: str, category: str, threshold: float = 0.85
    ) -> str | None:
        self._ensure_loaded()
        query_vec = np.array((await self._provider.embed([content]))[0], dtype=np.float32)
        candidates = self._category_index.get(category, set())

        best_score, best_id = 0.0, None
        for fid in candidates:
            entry = self._cache.get(fid)
            if entry is None:
                continue
            score = self._cosine(query_vec, entry.vector)
            if score >= threshold and score > best_score:
                best_score, best_id = score, fid
        return best_id

    def save(self) -> None:
        """兼容保留：数据已实时持久化（增量写），无需全量重写。"""
        # 旧实现在此全量重写 vectors.npz + vectors_meta.json；
        # SQLite 行存储后 add/batch_add/remove 已即时落盘，此处为空操作。
        return

    def _load(self) -> None:
        try:
            with self._db.session() as session:
                rows = session.execute(
                    select(MemoryVector).where(MemoryVector.owner_key == self._owner_key)
                ).scalars().all()
            for row in rows:
                entry = VectorEntry(
                    fact_id=row.fact_id,
                    content=row.content or "",
                    category=row.category or "",
                    scope=row.scope or "",
                    conversation_id=row.conversation_id or "",
                    vector=self._blob_to_vector(row.vector),
                )
                self._cache[entry.fact_id] = entry
                self._update_indexes(entry, add=True)
        except Exception as e:
            logger.warning(f"[VectorStore] Load failed: {e}")

    def _update_indexes(self, entry: VectorEntry, add: bool) -> None:
        if add:
            self._category_index.setdefault(entry.category, set()).add(entry.fact_id)
            self._scope_index.setdefault(entry.scope, set()).add(entry.fact_id)
            self._conv_index.setdefault(entry.conversation_id, set()).add(entry.fact_id)
        else:
            if entry.category in self._category_index:
                self._category_index[entry.category].discard(entry.fact_id)
            if entry.scope in self._scope_index:
                self._scope_index[entry.scope].discard(entry.fact_id)
            if entry.conversation_id in self._conv_index:
                self._conv_index[entry.conversation_id].discard(entry.fact_id)

    def _get_candidates(
        self, category: str | None, scope: str | None, conversation_id: str | None
    ) -> set[str]:
        candidates: set[str] = set(self._cache.keys())
        if category:
            candidates &= self._category_index.get(category, set())
        if scope:
            candidates &= self._scope_index.get(scope, set())
        if conversation_id:
            candidates &= self._conv_index.get(conversation_id, set())
        return candidates

    @staticmethod
    def _cosine(a: np.ndarray, b: np.ndarray) -> float:
        norm_a, norm_b = np.linalg.norm(a), np.linalg.norm(b)
        if norm_a < 1e-8 or norm_b < 1e-8:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))
