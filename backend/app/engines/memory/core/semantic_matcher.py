"""
语义匹配器 — 用 embedding 余弦相似度替代关键词匹配，提升记忆注入的相关性。

- 事实写入时异步计算 embedding 并缓存
- 注入时用 query embedding 对 facts 做相似度排序
- fallback 到关键词匹配（embedding 失败时）
"""
from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Any

from loguru import logger

from app.core.config import settings
from app.runtime.provider.llm.adapter import llm_adapter

from .models import MemoryFact


class SemanticMatcher:
    """给 facts 预计算 embedding 并提供语义相关性查询。"""

    def __init__(self):
        self._cache_path = Path(settings.DATA_DIR) / "memory" / "fact_embeddings.json"
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._embeddings: dict[str, list[float]] = {}
        self._load_cache()

    def _load_cache(self):
        if self._cache_path.exists():
            try:
                with open(self._cache_path, "r", encoding="utf-8") as f:
                    self._embeddings = json.load(f)
                logger.info(f"[SemanticMatcher] Loaded {len(self._embeddings)} cached embeddings")
            except Exception as e:
                logger.warning(f"[SemanticMatcher] Failed to load cache: {e}")

    def _save_cache(self):
        with self._lock:
            tmp = self._cache_path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._embeddings, f, ensure_ascii=False)
            tmp.replace(self._cache_path)

    def get_embedding(self, fact_id: str) -> list[float] | None:
        return self._embeddings.get(fact_id)

    async def compute_embedding(self, fact: MemoryFact) -> list[float] | None:
        if fact.id in self._embeddings:
            return self._embeddings[fact.id]
        try:
            embedding = await llm_adapter.embed(fact.content)
            if embedding:
                with self._lock:
                    self._embeddings[fact.id] = embedding
                return embedding
        except Exception as e:
            logger.debug(f"[SemanticMatcher] Embedding failed for {fact.id}: {e}")
        return None

    async def batch_compute(self, facts: list[MemoryFact]) -> None:
        missing = [f for f in facts if f.id not in self._embeddings]
        if not missing:
            return
        logger.info(f"[SemanticMatcher] Computing embeddings for {len(missing)} facts...")
        for fact in missing:
            await self.compute_embedding(fact)
        self._save_cache()

    async def rank_facts(
        self,
        facts: list[MemoryFact],
        query: str,
        top_k: int = 10,
    ) -> list[tuple[MemoryFact, float]]:
        query_embedding = None
        try:
            query_embedding = await llm_adapter.embed(query)
        except Exception as e:
            logger.debug(f"[SemanticMatcher] Query embedding failed: {e}")

        scored = []
        for fact in facts:
            if query_embedding:
                fact_emb = self._embeddings.get(fact.id)
                if fact_emb and len(fact_emb) == len(query_embedding):
                    score = self._cosine_sim(query_embedding, fact_emb)
                    scored.append((fact, score))
                    continue
            score = self._keyword_overlap(query, fact.content)
            scored.append((fact, score * 0.5))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    @staticmethod
    def _cosine_sim(a: list[float], b: list[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = sum(x * x for x in a) ** 0.5
        nb = sum(x * x for x in b) ** 0.5
        return dot / (na * nb) if na and nb else 0.0

    @staticmethod
    def _keyword_overlap(query: str, content: str) -> float:
        qw = set(re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', query.lower()))
        cw = set(re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', content.lower()))
        if not qw:
            return 0.0
        return len(qw & cw) / len(qw)

    def remove_embeddings(self, fact_ids: list[str]) -> None:
        with self._lock:
            for fid in fact_ids:
                self._embeddings.pop(fid, None)
        self._save_cache()

    def clear(self):
        with self._lock:
            self._embeddings.clear()
        if self._cache_path.exists():
            self._cache_path.unlink()


_semantic_matcher_instance: SemanticMatcher | None = None


def get_semantic_matcher() -> SemanticMatcher:
    global _semantic_matcher_instance
    if _semantic_matcher_instance is None:
        _semantic_matcher_instance = SemanticMatcher()
    return _semantic_matcher_instance
