from __future__ import annotations

import re
from loguru import logger

from app.engines.memory.core.models import (
    MemoryFact,
    MemoryLayer,
    TIER_SEARCH_WEIGHT,
)
from app.engines.memory.core.semantic_matcher import SemanticMatcher, get_semantic_matcher


class EmbeddingIndex:

    def __init__(self, semantic_matcher: SemanticMatcher | None = None):
        self._matcher = semantic_matcher or get_semantic_matcher()
        self._facts: dict[str, MemoryFact] = {}

    def index_facts(self, facts: list[MemoryFact]) -> None:
        for fact in facts:
            self._facts[fact.id] = fact

    def remove_fact(self, fact_id: str) -> None:
        self._facts.pop(fact_id, None)

    def clear(self) -> None:
        self._facts.clear()

    async def search(
        self,
        query: str,
        top_k: int = 8,
        min_score: float = 0.3,
        allowed_layers: list[str] | None = None,
        allowed_agent_ids: list[str] | None = None,
    ) -> list[tuple[MemoryFact, float]]:
        if not self._facts:
            return []

        all_facts = list(self._facts.values())
        ranked = await self._matcher.rank_facts(all_facts, query, top_k=top_k * 3)

        results = []
        for fact, score in ranked:
            if not self._passes_filter(fact, allowed_layers, allowed_agent_ids):
                continue
            weight = TIER_SEARCH_WEIGHT.get(fact.tier, 1.0)
            weighted_score = score * weight
            if weighted_score >= min_score:
                results.append((fact, weighted_score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    @staticmethod
    def _passes_filter(
        fact: MemoryFact,
        allowed_layers: list[str] | None,
        allowed_agent_ids: list[str] | None,
    ) -> bool:
        if allowed_layers and fact.layer not in allowed_layers:
            return False
        if fact.layer == MemoryLayer.USER:
            return True
        if fact.layer == MemoryLayer.AGENT and allowed_agent_ids:
            return fact.source_agent_id in allowed_agent_ids
        if fact.layer == MemoryLayer.AGENT:
            return False
        return True

    async def rebuild_index(self, facts: list[MemoryFact]) -> None:
        self._facts.clear()
        self.index_facts(facts)
        await self._matcher.batch_compute(facts)
        logger.info(f"[EmbeddingIndex] Rebuilt index with {len(facts)} facts")
