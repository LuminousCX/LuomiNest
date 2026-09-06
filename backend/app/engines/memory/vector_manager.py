from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from app.engines.memory.models import FactItem, FACT_SCOPE_CONVERSATION
from .store import agent_memory_dir
from .vector_store import VectorStore, VectorEntry, LLMEmbeddingProvider, LocalEmbeddingProvider, ScoredFact


class VectorSearchManager:
    """向量搜索管理器：负责事实的向量去重、语义检索和索引重建。"""

    def __init__(self, agent_id: str, provider: Any, storage_path: Path | None = None, owner_key: str | None = None) -> None:
        self._agent_id: str = agent_id
        if storage_path is None:
            storage_path = agent_memory_dir(agent_id) / "vectors"
        # owner_key：行级隔离键（owner:… / users:…），缺省按路径推导（与 MemoryStore 一致）
        self._store: VectorStore = VectorStore(storage_path, provider, owner_key=owner_key)

    async def dedup_and_add(self, facts: list[FactItem], conversation_id: str | None = None) -> list[FactItem]:
        if not facts:
            return []

        # 先做批次内去重：两两比较相同 category 的事实
        entries = []
        seen_content = {}  # (category, content_hash) -> fact_id

        for f in facts:
            # 已在向量索引中的 fact 跳过（避免重复 embedding）
            if f.id in self._store._cache:
                continue

            content_hash = hashlib.sha256(f.content.encode()).hexdigest()
            key = (f.category, content_hash)

            # 检查批次内重复
            if key in seen_content:
                continue
            seen_content[key] = f.id

            # 检查已有的向量索引
            dup_id = await self._store.dedup_check(f.content, f.category)
            if dup_id:
                continue

            scope = "conversation" if f.category in FACT_SCOPE_CONVERSATION else "agent"
            entries.append(VectorEntry(
                fact_id=f.id, content=f.content, category=f.category,
                scope=scope, conversation_id=conversation_id or ""
            ))

        await self._store.batch_add(entries)
        return [f for f in facts if f.id in {e.fact_id for e in entries}]

    async def retrieve(self, query: str, k: int = 10) -> list[ScoredFact]:
        return await self._store.search(query, k=k)

    async def rebuild(self, facts: list[FactItem], conversation_id: str | None = None) -> int:
        entries = []
        for f in facts:
            scope = "conversation" if f.category in FACT_SCOPE_CONVERSATION else "agent"
            entries.append(VectorEntry(
                fact_id=f.id, content=f.content, category=f.category, 
                scope=scope, conversation_id=conversation_id or ""
            ))
        await self._store.batch_add(entries)
        self._store.save()
        return len(entries)

    async def delete_conversation(self, conversation_id: str) -> int:
        return await self._store.delete_by_conversation(conversation_id)

    def save(self) -> None:
        self._store.save()