from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from app.engines.memory.models import FactItem, FACT_SCOPE_CONVERSATION
from .store import agent_memory_dir
from .vector_store import VectorStore, VectorEntry, LLMEmbeddingProvider, ScoredFact


class VectorSearchManager:
    """向量搜索管理器：负责事实的向量去重、语义检索和索引重建。"""

    def __init__(self, agent_id: str, provider: Any, storage_path: Path | None = None, owner_key: str | None = None) -> None:
        self._agent_id: str = agent_id
        if storage_path is None:
            storage_path = agent_memory_dir(agent_id) / "vectors"
        # owner_key：行级隔离键（owner:… / users:…），缺省按路径推导（与 MemoryStore 一致）
        self._store: VectorStore = VectorStore(storage_path, provider, owner_key=owner_key)

    async def dedup_and_add(self, facts: list[FactItem], conversation_id: str | None = None) -> list[FactItem]:
        """批量去重 + 入库：全程只发起 1 次 embedding 请求。

        旧实现逐条 dedup_check（每条一次 embed 网络往返）再 batch_add 重新
        embed 一遍——N 条事实 = N+1 次串行 HTTP 调用（实测 N=30、RTT=200ms
        时约 6.3s）。现改为：一次批量嵌入 → 复用向量做语义判重 → 复用向量
        入库，网络调用收敛为 1 次，向量只算一遍。
        """
        if not facts:
            return []

        await self._store._ensure_loaded()

        # ── 步骤 1：批次内精确去重 + 已索引过滤（零网络调用） ──
        candidates: list[FactItem] = []
        seen_content: dict[tuple[str, str], str] = {}  # (category, content_hash) -> fact_id
        for f in facts:
            if f.id in self._store._cache:
                continue
            content_hash = hashlib.sha256(f.content.encode()).hexdigest()
            key = (f.category, content_hash)
            if key in seen_content:
                continue
            seen_content[key] = f.id
            candidates.append(f)

        if not candidates:
            return []

        # ── 步骤 2：一次性批量嵌入全部候选（含契约校验） ──
        texts = [f.content for f in candidates]
        vectors = await self._store.embed_batch(texts)

        # ── 步骤 3：复用预算向量做语义判重（不再触发 embed） ──
        entries: list[VectorEntry] = []
        pre_vectors = []
        for f, vec in zip(candidates, vectors):
            dup_id = await self._store.dedup_check(f.content, f.category, query_vec=vec)
            if dup_id:
                continue
            scope = "conversation" if f.category in FACT_SCOPE_CONVERSATION else "agent"
            entries.append(VectorEntry(
                fact_id=f.id, content=f.content, category=f.category,
                scope=scope, conversation_id=conversation_id or ""
            ))
            pre_vectors.append(vec)

        # ── 步骤 4：入库复用预算向量（不再触发 embed） ──
        if entries:
            await self._store.batch_add(entries, pre_vectors=pre_vectors)

        return [f for f in facts if f.id in {e.fact_id for e in entries}]

    async def add_fact(self, fact: FactItem, conversation_id: str | None = None) -> None:
        """单条事实向量入库（事实↔向量生命周期联动：写库后即时索引）。"""
        scope = "conversation" if fact.category in FACT_SCOPE_CONVERSATION else "agent"
        entry = VectorEntry(
            fact_id=fact.id, content=fact.content, category=fact.category,
            scope=scope, conversation_id=conversation_id or ""
        )
        await self._store.add(entry)

    async def remove(self, fact_id: str) -> None:
        """单条事实向量移除（事实↔向量生命周期联动：删库后即时摘除）。"""
        await self._store.remove(fact_id)

    async def retrieve(self, query: str, k: int = 10) -> list[ScoredFact]:
        return await self._store.search(query, k=k)

    async def rebuild(self, facts: list[FactItem], conversation_id: str | None = None) -> int:
        """重建索引：先清旧（agent 级 + 指定对话）再全量入库。

        旧实现只 upsert 不清旧——被删除事实的向量残留会被持续召回，
        索引只增不减；clear_for_rebuild 作用域不含其他对话的向量。
        """
        await self._store.clear_for_rebuild(conversation_id or "")
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

    async def aclose(self) -> None:
        await self._store.aclose()
