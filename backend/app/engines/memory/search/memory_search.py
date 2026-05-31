from __future__ import annotations

import re
from loguru import logger

from app.engines.memory.core.models import (
    MemoryFact,
    MemoryLayer,
    TIER_SEARCH_WEIGHT,
)
from app.engines.memory.core.storage import MemoryStorage, get_memory_storage
from .embedding_index import EmbeddingIndex


class MemorySearchEngine:

    def __init__(self, storage: MemoryStorage | None = None):
        self._storage = storage or get_memory_storage()
        self._index = EmbeddingIndex()
        self._built = False

    async def rebuild_index(self, agent_id: str | None = None) -> None:
        all_facts: list[MemoryFact] = []
        user_space = self._storage.load_user_space()
        all_facts.extend(user_space.facts)

        if agent_id:
            agent_memory = self._storage.load_agent_memory(agent_id)
            all_facts.extend(agent_memory.agent_facts)
        else:
            for aid in self._storage.list_agents():
                am = self._storage.load_agent_memory(aid)
                all_facts.extend(am.agent_facts)

        self._index = EmbeddingIndex()
        await self._index.rebuild_index(all_facts)
        self._built = True
        logger.info(
            f"[MemorySearchEngine] Index rebuilt: {len(all_facts)} facts, "
            f"agent_id={'all' if not agent_id else agent_id}"
        )

    async def search(
        self,
        query: str,
        agent_id: str,
        top_k: int = 8,
    ) -> list[tuple[MemoryFact, float]]:
        if self._built:
            return await self._index.search(
                query,
                top_k=top_k,
                allowed_layers=["user", "agent"],
                allowed_agent_ids=[agent_id],
            )
        return self._keyword_fallback(query, agent_id, top_k)

    def _keyword_fallback(
        self,
        query: str,
        agent_id: str,
        top_k: int,
    ) -> list[tuple[MemoryFact, float]]:
        user_space = self._storage.load_user_space()
        agent_memory = self._storage.load_agent_memory(agent_id)

        all_facts: list[MemoryFact] = []
        for f in user_space.facts:
            if f.layer == "user":
                all_facts.append(f)
        for f in agent_memory.agent_facts:
            if f.layer == "agent" and f.source_agent_id == agent_id:
                all_facts.append(f)

        query_words = set(re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]{2,}', query.lower()))
        if not query_words:
            return []

        results: list[tuple[MemoryFact, float]] = []
        for fact in all_facts:
            content_words = set(re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]{2,}', fact.content.lower()))
            overlap = query_words & content_words
            if overlap:
                score = len(overlap) / len(query_words)
                weight = TIER_SEARCH_WEIGHT.get(fact.tier, 1.0)
                results.append((fact, score * weight))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
