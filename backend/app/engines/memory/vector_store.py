import numpy as np
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Protocol
import json
import httpx
import asyncio

from loguru import logger


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
    def __init__(self, provider, model: str = "text-embedding-3-small"):
        self._provider = provider
        self._model = model
        self._dim = 1536 if "large" not in model else 3072

    @property
    def dim(self) -> int:
        return self._dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        
        base_url = getattr(self._provider, "base_url", "https://api.openai.com/v1")
        api_key = getattr(self._provider, "api_key", "")
        
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
    def __init__(self, storage_path: Path, provider: EmbeddingProvider):
        self._path = Path(storage_path)
        self._provider = provider
        self._cache: dict[str, VectorEntry] = {}
        self._category_index: dict[str, set[str]] = {}
        self._scope_index: dict[str, set[str]] = {}
        self._conv_index: dict[str, set[str]] = {}
        self._loaded = False

    def _ensure_loaded(self):
        if not self._loaded:
            self._load()
            self._loaded = True

    async def add(self, entry: VectorEntry) -> None:
        self._ensure_loaded()
        if entry.vector.size == 0:
            vectors = await self._provider.embed([entry.content])
            entry.vector = np.array(vectors[0], dtype=np.float32)
        self._cache[entry.fact_id] = entry
        self._update_indexes(entry, add=True)

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

    async def remove(self, fact_id: str) -> None:
        self._ensure_loaded()
        if fact_id not in self._cache:
            return
        entry = self._cache[fact_id]
        self._update_indexes(entry, add=False)
        del self._cache[fact_id]

    async def delete_by_conversation(self, conversation_id: str) -> int:
        self._ensure_loaded()
        deleted = 0
        to_delete = list(self._conv_index.get(conversation_id, set()))
        for fact_id in to_delete:
            await self.remove(fact_id)
            deleted += 1
        return deleted

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
        if not self._cache:
            return
        self._path.mkdir(parents=True, exist_ok=True)
        
        ids = list(self._cache.keys())
        vectors = np.stack([self._cache[fid].vector for fid in ids])
        
        np.savez_compressed(self._path / "vectors.npz", ids=np.array(ids), vectors=vectors)
        
        meta = {
            fid: {
                "content": self._cache[fid].content,
                "category": self._cache[fid].category,
                "scope": self._cache[fid].scope,
                "conversation_id": self._cache[fid].conversation_id,
            }
            for fid in ids
        }
        (self._path / "vectors_meta.json").write_text(
            json.dumps(meta, ensure_ascii=False), encoding="utf-8"
        )

    def _load(self) -> None:
        path = self._path / "vectors.npz"
        if not path.exists():
            return
        
        try:
            data = np.load(path, allow_pickle=True)
            ids = [str(x) for x in data["ids"]]
            vectors = data["vectors"]
            
            meta_path = self._path / "vectors_meta.json"
            meta = {}
            if meta_path.exists():
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            
            for i, fid in enumerate(ids):
                m = meta.get(fid, {})
                entry = VectorEntry(
                    fact_id=fid,
                    content=m.get("content", ""),
                    category=m.get("category", ""),
                    scope=m.get("scope", ""),
                    conversation_id=m.get("conversation_id", ""),
                    vector=vectors[i].astype(np.float32),
                )
                self._cache[fid] = entry
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