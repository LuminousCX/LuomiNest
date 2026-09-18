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
    """基于 LLM API 的嵌入提供器（批量协议：list[str] → list[list[float]]）。

    直接经 OpenAI 兼容 /embeddings 端点批量获取向量，持有长生命周期
    httpx 连接池（provider 的 base_url/api_key 变更时自动重建），避免
    每次请求重建 TCP/TLS 连接。api_key 为空时不携带 Authorization 头
    （本地推理服务如 Ollama 无需鉴权即可使用）。
    """

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
        self._client: httpx.AsyncClient | None = None
        self._client_key: tuple[str, str] | None = None

    @property
    def dim(self) -> int:
        return self._dim

    async def _get_client(self) -> httpx.AsyncClient:
        base_url = str(getattr(self._provider, "base_url", "") or "https://api.openai.com/v1")
        api_key = str(getattr(self._provider, "api_key", "") or "")
        key = (base_url, api_key)
        if self._client is not None and not self._client.is_closed and self._client_key == key:
            return self._client
        old, self._client = self._client, httpx.AsyncClient(timeout=30.0)
        self._client_key = key
        if old is not None and not old.is_closed:
            await old.aclose()
        return self._client

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        base_url = str(getattr(self._provider, "base_url", "") or "https://api.openai.com/v1")
        api_key = str(getattr(self._provider, "api_key", "") or "")
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        client = await self._get_client()
        resp = await client.post(
            f"{base_url.rstrip('/')}/embeddings",
            headers=headers,
            json={"model": self._model, "input": texts},
        )
        resp.raise_for_status()
        return [d["embedding"] for d in resp.json()["data"]]

    async def aclose(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
        self._client = None
        self._client_key = None


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
        # 本地模式（临时/测试目录）下 memory.db 落在 storage_path 内，
        # 目录不存在会导致 SQLite "unable to open database file"；生产全局模式无副作用
        self._path.mkdir(parents=True, exist_ok=True)
        self._provider = provider
        self._owner_key = owner_key or _derive_owner_key(self._path)
        self._db = _MemoryDB(self._path)
        self._cache: dict[str, VectorEntry] = {}
        self._category_index: dict[str, set[str]] = {}
        self._scope_index: dict[str, set[str]] = {}
        self._conv_index: dict[str, set[str]] = {}
        self._loaded = False
        self._load_lock = asyncio.Lock()

    def close(self) -> None:
        self._db.close()

    async def aclose(self) -> None:
        """异步关闭：先关 embedding provider 的连接池（如有 aclose），再关 DB。"""
        provider_close = getattr(self._provider, "aclose", None)
        if callable(provider_close):
            try:
                await provider_close()
            except Exception as e:
                logger.debug(f"[VectorStore] Provider aclose failed (ignored): {e}")
        self.close()

    # ── 嵌入契约（批量协议校验，防 provider 实现错配静默产出标量垃圾） ──

    def _coerce_vectors(self, vectors: Any, expected_count: int) -> list[np.ndarray]:
        """校验 embed 返回结构并转为 float32 一维数组列表。

        契约：vectors 必须是 list[list[float]] 且长度 == expected_count；
        provider 声明 dim 时每条维度必须一致。违反契约抛 ValueError
        （fail-loud），替代旧版 np.array(vectors[i]) 对标量静默产出 () 形状。
        """
        if not isinstance(vectors, (list, tuple)) or len(vectors) != expected_count:
            got = len(vectors) if hasattr(vectors, "__len__") else "n/a"
            raise ValueError(
                f"embed returned {type(vectors).__name__} len={got}, "
                f"expected list[list[float]] of length {expected_count}"
            )
        dim = getattr(self._provider, "dim", None)
        out: list[np.ndarray] = []
        for i, v in enumerate(vectors):
            arr = np.asarray(v, dtype=np.float32)
            if arr.ndim != 1 or (dim is not None and arr.shape[0] != dim):
                raise ValueError(
                    f"embed[{i}] shape={arr.shape}, expected ({dim},); "
                    "provider likely returned a scalar/1D list instead of list[list[float]]"
                )
            out.append(arr)
        return out

    async def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        """批量嵌入 + 契约校验（单次 HTTP 调用，供去重/入库共用）。"""
        vectors = await self._provider.embed(texts)
        return self._coerce_vectors(vectors, len(texts))

    async def _ensure_loaded(self) -> None:
        # 冷启动全量加载是同步 SQLite 读（BLOB 进内存），必须在 to_thread 中执行；
        # asyncio.Lock 保证并发调用只触发一次加载（与原同步实现的原子性一致）
        if self._loaded:
            return
        async with self._load_lock:
            if not self._loaded:
                await asyncio.to_thread(self._load)
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
        await self._ensure_loaded()
        if entry.vector.size == 0:
            entry.vector = (await self.embed_batch([entry.content]))[0]
        self._cache[entry.fact_id] = entry
        self._update_indexes(entry, add=True)
        try:
            await asyncio.to_thread(self._persist_upsert, entry)
        except Exception as e:
            logger.warning(f"[VectorStore] Persist add failed for {entry.fact_id}: {e}")

    async def batch_add(
        self,
        entries: list[VectorEntry],
        pre_vectors: list[np.ndarray] | None = None,
    ) -> None:
        """批量写入。pre_vectors 提供时跳过嵌入（调用方已批量算好并复用）。

        落盘失败时回滚内存 cache/索引（_persist_batch 单事务全有或全无），
        避免出现"内存有、库里无"的永久缺口（该 fact 此后会被
        dedup_and_add 的已索引检查跳过而无法补录）。
        """
        await self._ensure_loaded()
        if not entries:
            return

        if pre_vectors is not None:
            if len(pre_vectors) != len(entries):
                raise ValueError(f"pre_vectors length {len(pre_vectors)} != entries length {len(entries)}")
            for entry, vec in zip(entries, pre_vectors):
                entry.vector = vec
        else:
            coerced = await self.embed_batch([e.content for e in entries])
            for entry, vec in zip(entries, coerced):
                entry.vector = vec

        for entry in entries:
            self._cache[entry.fact_id] = entry
            self._update_indexes(entry, add=True)

        # 批量落盘（单事务）
        try:
            await asyncio.to_thread(self._persist_batch, entries)
        except Exception as e:
            for entry in entries:
                self._update_indexes(entry, add=False)
                self._cache.pop(entry.fact_id, None)
            logger.warning(f"[VectorStore] Batch persist failed ({len(entries)} entries): {e}")

    def _persist_batch(self, entries: list[VectorEntry]) -> None:
        # 一次性取回存量行再分流 upsert，避免逐条 session.get 的 N+1 查询
        # （fact_id 为主键，与原逐条 get 一致，不按 owner_key 过滤）
        with self._db.session() as session:
            existing = {
                row.fact_id: row
                for row in session.execute(
                    select(MemoryVector).where(
                        MemoryVector.fact_id.in_([e.fact_id for e in entries])
                    )
                ).scalars()
            }
            for entry in entries:
                row = existing.get(entry.fact_id)
                if row is None:
                    session.add(self._row_from_entry(entry))
                else:
                    row.content = entry.content
                    row.category = entry.category
                    row.scope = entry.scope
                    row.conversation_id = entry.conversation_id
                    row.vector = self._vector_to_blob(entry.vector)
            session.commit()

    def _persist_delete(self, fact_id: str) -> None:
        with self._db.session() as session:
            session.execute(
                delete(MemoryVector).where(
                    MemoryVector.fact_id == fact_id,
                    MemoryVector.owner_key == self._owner_key,
                )
            )
            session.commit()

    def _persist_delete_by_conversation(self, conversation_id: str) -> None:
        with self._db.session() as session:
            session.execute(
                delete(MemoryVector).where(
                    MemoryVector.owner_key == self._owner_key,
                    MemoryVector.conversation_id == conversation_id,
                )
            )
            session.commit()

    async def remove(self, fact_id: str) -> None:
        await self._ensure_loaded()
        if fact_id not in self._cache:
            return
        entry = self._cache[fact_id]
        self._update_indexes(entry, add=False)
        del self._cache[fact_id]
        try:
            await asyncio.to_thread(self._persist_delete, fact_id)
        except Exception as e:
            logger.warning(f"[VectorStore] Persist remove failed for {fact_id}: {e}")

    async def delete_by_conversation(self, conversation_id: str) -> int:
        await self._ensure_loaded()
        to_delete = list(self._conv_index.get(conversation_id, set()))
        for fact_id in to_delete:
            entry = self._cache.get(fact_id)
            if entry is None:
                continue
            self._update_indexes(entry, add=False)
            del self._cache[fact_id]
        if to_delete:
            try:
                await asyncio.to_thread(self._persist_delete_by_conversation, conversation_id)
            except Exception as e:
                logger.warning(f"[VectorStore] Persist delete_by_conversation failed: {e}")
        return len(to_delete)

    async def clear_for_rebuild(self, conversation_id: str = "") -> int:
        """重建前清理：删除 agent 级向量 + 指定对话的向量（其他对话不动）。

        修复"rebuild 只 upsert 不清旧"——被删除事实的向量残留在索引中
        会被持续召回，且索引只增不减。conversation_id 为空时清理
        conversation_id 为空的行（无对话归属的条目）。
        """
        await self._ensure_loaded()
        target_conv = conversation_id or ""
        to_drop = [
            fid for fid, entry in self._cache.items()
            if entry.scope == "agent" or entry.conversation_id == target_conv
        ]
        for fid in to_drop:
            entry = self._cache.pop(fid)
            self._update_indexes(entry, add=False)
        if to_drop:
            try:
                await asyncio.to_thread(self._persist_clear_for_rebuild, target_conv)
            except Exception as e:
                logger.warning(f"[VectorStore] Persist clear_for_rebuild failed: {e}")
        return len(to_drop)

    def _persist_clear_for_rebuild(self, conversation_id: str) -> None:
        with self._db.session() as session:
            session.execute(
                delete(MemoryVector).where(
                    MemoryVector.owner_key == self._owner_key,
                    (MemoryVector.scope == "agent") | (MemoryVector.conversation_id == conversation_id),
                )
            )
            session.commit()

    # ── 检索（进程内 cache + 索引，与旧实现一致） ──

    async def search(
        self, query: str, k: int = 10,
        category: str | None = None, scope: str | None = None,
        conversation_id: str | None = None, min_score: float = 0.0
    ) -> list[ScoredFact]:
        await self._ensure_loaded()
        query_vec = (await self.embed_batch([query]))[0]
        candidates = self._get_candidates(category, scope, conversation_id)
        results = await asyncio.to_thread(self._rank_candidates, query_vec, candidates, min_score)
        return [
            ScoredFact(fact_id=fid, score=score, category=self._cache[fid].category)
            for fid, score in results[:k] if fid in self._cache
        ]

    def _rank_candidates(
        self, query_vec: np.ndarray, candidates: set[str], min_score: float
    ) -> list[tuple[str, float]]:
        """批量余弦打分并降序排序（纯 CPU，放到线程避免阻塞事件循环）。

        候选向量堆叠 (n,d) 矩阵单次 matmul（审计 B5-1）：旧实现逐候选 Python 级
        np.dot，1 万条 50-100ms、10 万条秒级；堆叠后 10-100× 提升。
        维度不匹配条目跳过（模型切换后的残留向量，加载侧已过滤，此处兜底）。
        """
        q = np.asarray(query_vec, dtype=np.float32)
        q_norm = float(np.linalg.norm(q))
        if q_norm == 0.0 or not candidates:
            return []

        fids: list[str] = []
        vecs: list[np.ndarray] = []
        for fid in candidates:
            entry = self._cache.get(fid)
            if entry is None or entry.vector.shape != q.shape:
                continue
            fids.append(fid)
            vecs.append(entry.vector)
        if not vecs:
            return []

        matrix = np.vstack(vecs)
        denom = np.linalg.norm(matrix, axis=1) * q_norm
        # 零向量余弦恒 0（与 _cosine 除零保护语义一致），仍参与 min_score 过滤
        denom[denom == 0.0] = 1.0
        scores = (matrix @ q) / denom
        results = [(fid, float(score)) for fid, score in zip(fids, scores) if score >= min_score]
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    async def dedup_check(
        self,
        content: str,
        category: str,
        threshold: float = 0.85,
        query_vec: np.ndarray | None = None,
    ) -> str | None:
        """语义判重。query_vec 提供时跳过嵌入（批量流程已算好直接复用）。"""
        await self._ensure_loaded()
        if query_vec is None:
            query_vec = (await self.embed_batch([content]))[0]
        else:
            dim = getattr(self._provider, "dim", None)
            if dim is not None and query_vec.shape != (dim,):
                raise ValueError(f"query_vec shape {query_vec.shape} != ({dim},)")
        # 传入 to_thread 前必须快照：直接传索引内活 set 会被事件循环侧 add()/remove()
        # 并发修改，工作线程迭代中途集合变更 → "Set changed size during iteration"
        candidates = set(self._category_index.get(category, ()))
        return await asyncio.to_thread(self._best_match, query_vec, candidates, threshold)

    def _best_match(
        self, query_vec: np.ndarray, candidates: set[str], threshold: float
    ) -> str | None:
        q = np.asarray(query_vec, dtype=np.float32)
        q_norm = float(np.linalg.norm(q))
        if q_norm == 0.0:
            return None
        best_score, best_id = 0.0, None
        for fid in candidates:
            entry = self._cache.get(fid)
            if entry is None:
                continue
            vec = entry.vector
            # 形状守卫（审计 B5-1）：维度不匹配的残留向量跳过，防 np.dot 抛 ValueError
            if vec.shape != q.shape:
                continue
            # 零向量余弦恒 0（除零保护语义），不会通过 threshold>0 的判重
            norm = float(np.linalg.norm(vec))
            score = float(np.dot(q, vec) / (q_norm * norm)) if norm > 0.0 else 0.0
            if score >= threshold and score > best_score:
                best_score, best_id = score, fid
        return best_id

    def save(self) -> None:
        """兼容保留：数据已实时持久化（增量写），无需全量重写。"""
        # 旧实现在此全量重写 vectors.npz + vectors_meta.json；
        # SQLite 行存储后 add/batch_add/remove 已即时落盘，此处为空操作。
        return

    def _load(self) -> None:
        # 维度校验：provider 声明 dim 时，形状不符的行（历史接口错配产生的
        # 标量垃圾 / 换嵌入模型后的旧维度）不可用于余弦计算，剔除并删除。
        dim = getattr(self._provider, "dim", None)
        invalid_ids: list[str] = []
        try:
            with self._db.session() as session:
                rows = session.execute(
                    select(MemoryVector).where(MemoryVector.owner_key == self._owner_key)
                ).scalars().all()
                for row in rows:
                    vector = self._blob_to_vector(row.vector)
                    if dim is not None and vector.shape != (dim,):
                        invalid_ids.append(row.fact_id)
                        continue
                    entry = VectorEntry(
                        fact_id=row.fact_id,
                        content=row.content or "",
                        category=row.category or "",
                        scope=row.scope or "",
                        conversation_id=row.conversation_id or "",
                        vector=vector,
                    )
                    self._cache[entry.fact_id] = entry
                    self._update_indexes(entry, add=True)
                if invalid_ids:
                    session.execute(
                        delete(MemoryVector).where(
                            MemoryVector.owner_key == self._owner_key,
                            MemoryVector.fact_id.in_(invalid_ids),
                        )
                    )
                    session.commit()
                    logger.warning(
                        f"[VectorStore] Dropped {len(invalid_ids)} invalid-dimension vector row(s) "
                        "(stale index from earlier embedding mismatch or model change); "
                        "run memory.vector_rebuild to re-index"
                    )
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
