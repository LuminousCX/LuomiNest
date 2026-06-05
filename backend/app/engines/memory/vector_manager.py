from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.engines.memory.models import FactItem
from .vector_store import VectorStore, VectorEntry, LLMEmbeddingProvider, LocalEmbeddingProvider, ScoredFact


class VectorSearchManager:
    def __init__(self, agent_id: str, provider):
        self._agent_id = agent_id
        storage_path = Path(settings.DATA_DIR) / "memory" / "agents" / agent_id / "vectors"
        self._store = VectorStore(storage_path, provider)

    async def dedup_and_add(self, facts: list[FactItem], conversation_id: str | None = None) -> list[FactItem]:
        if not facts:
            return []
        
        # 先做批次内去重：两两比较相同 category 的事实
        entries = []
        seen_content = {}  # (category, content_hash) -> fact_id
        
        for f in facts:
            content_hash = hash(f.content)
            key = (f.category, content_hash)
            
            # 检查批次内重复
            if key in seen_content:
                continue
            seen_content[key] = f.id
            
            # 检查已有的向量索引
            dup_id = await self._store.dedup_check(f.content, f.category)
            if dup_id:
                continue
            
            scope = "conversation" if f.category in {"context", "behavior", "goal"} else "agent"
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
            scope = "conversation" if f.category in {"context", "behavior", "goal"} else "agent"
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