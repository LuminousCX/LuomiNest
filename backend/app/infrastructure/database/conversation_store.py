"""对话存储 — 委托 ConversationRepository + conversations/conversation_messages 表（SQLite）。

替代原 data/conversations/*.json + _index.json 的 per-conv 文件方案：
- 消息存 conversation_messages 独立表（每消息一行），追加 O(1)、SQL 层分页
- search_text 随写入增量维护，用 LIKE 搜索（FTS5 预留扩展点）
- deleted_at 软删除（回收站）
- save()/set() 为全量替换（元数据 + 消息行单事务）
- append_message/append_messages/update_message 为热路径增量写入
- migrate_from_json_store() 供 Phase 5 迁移器调用
"""
import asyncio
from typing import Optional

from app.infrastructure.database.repositories import ConversationRepository


class ConversationFacade:
    """委托 ConversationRepository，接口与原 ConversationStore 一致。"""

    def __init__(self, repo: ConversationRepository):
        self._repo = repo

    # ── Basic CRUD ──

    def get(self, conversation_id: str) -> Optional[dict]:
        return self._repo.get(conversation_id)

    def get_meta(self, conversation_id: str) -> Optional[dict]:
        """加载对话元数据（不含 messages/search_text）。"""
        return self._repo.get_meta(conversation_id)

    def get_paginated(self, conversation_id: str, limit: int = 100, before_id: Optional[str] = None) -> Optional[dict]:
        """加载对话 + 分页消息（SQL 层 keyset 分页）。"""
        return self._repo.get_paginated(conversation_id, limit, before_id)

    def set(self, conversation_id: str, conv: dict) -> None:
        self._repo.save(conversation_id, conv)

    # ── 热路径增量写入（O(1) 追加，避免全量重写） ──

    def append_message(self, conversation_id: str, message: dict) -> bool:
        """追加单条消息（INSERT + 增量维护 search_text/last_message）。"""
        return self._repo.append_message(conversation_id, message)

    def append_messages(self, conversation_id: str, messages: list[dict]) -> bool:
        """批量追加多条消息（单事务）。"""
        return self._repo.append_messages(conversation_id, messages)

    def update_message(self, conversation_id: str, mid: str, message: dict) -> bool:
        """按消息 id 更新单行（如合并文件内容的最后一条 user 消息）。"""
        return self._repo.update_message(conversation_id, mid, message)

    def update_meta(self, conversation_id: str, updates: dict) -> Optional[dict]:
        """仅更新对话元数据（标题/模型等），不影响消息与 search_text。"""
        return self._repo.update_meta(conversation_id, updates)

    def delete(self, conversation_id: str) -> None:
        self._repo.delete(conversation_id)

    # ── List / Search ──

    def list_conversations(
        self,
        agent_id: Optional[str] = None,
        include_hidden: bool = False,
        domain: Optional[str] = None,
        exclude_domain_prefix: Optional[str] = None,
    ) -> list[dict]:
        return self._repo.list_meta(
            agent_id,
            include_hidden=include_hidden,
            domain=domain,
            exclude_domain_prefix=exclude_domain_prefix,
        )

    def count_messages(self, agent_id: Optional[str] = None) -> int:
        return self._repo.count_messages(agent_id)

    def search_conversations(self, keyword: str, agent_id: Optional[str] = None) -> list[dict]:
        return self._repo.search(keyword, agent_id)

    # ── Soft delete / Trash ──

    def soft_delete(self, conversation_id: str) -> bool:
        return self._repo.soft_delete(conversation_id)

    def list_trash(self, agent_id: Optional[str] = None) -> list[dict]:
        return self._repo.list_trash(agent_id)

    def restore(self, conversation_id: str) -> bool:
        return self._repo.restore(conversation_id)

    def permanent_delete(self, conversation_id: str) -> bool:
        return self._repo.permanent_delete(conversation_id)

    def empty_trash(self, agent_id: Optional[str] = None) -> int:
        return self._repo.empty_trash(agent_id)

    def batch_restore(self, conversation_ids: list[str]) -> int:
        return self._repo.batch_restore(conversation_ids)

    def batch_permanent_delete(self, conversation_ids: list[str]) -> int:
        return self._repo.batch_permanent_delete(conversation_ids)

    def batch_soft_delete(self, conversation_ids: list[str]) -> int:
        return self._repo.batch_soft_delete(conversation_ids)

    def rename(self, conversation_id: str, new_title: str) -> bool:
        return self._repo.rename(conversation_id, new_title)

    def delete_by_agent_id(self, agent_id: str) -> int:
        return self._repo.delete_by_agent_id(agent_id)

    # ── Misc ──

    def items(self) -> list:
        """返回 [(conversation_id, meta), ...]（不含 messages/search_text）。"""
        return [(m["id"], m) for m in self._repo.list_meta()]

    def values(self) -> list:
        return self._repo.list_meta()

    def count(self) -> int:
        return len(self._repo.list_meta())

    def migrate_from_json_store(self, old_store) -> int:
        """从旧 JsonStore 迁移对话数据（幂等：已存在则跳过）。"""
        old_data = old_store.list_all()
        if not old_data:
            return 0
        migrated = 0
        for conversation_id, conv in old_data.items():
            if not isinstance(conv, dict):
                continue
            if self._repo.get(conversation_id) is not None:
                continue
            self._repo.save(conversation_id, conv)
            migrated += 1
        return migrated

    # ── Async wrappers ──

    async def get_async(self, conversation_id: str) -> Optional[dict]:
        return await asyncio.to_thread(self.get, conversation_id)

    async def get_meta_async(self, conversation_id: str) -> Optional[dict]:
        return await asyncio.to_thread(self.get_meta, conversation_id)

    async def get_paginated_async(self, conversation_id: str, limit: int = 100, before_id: Optional[str] = None) -> Optional[dict]:
        return await asyncio.to_thread(self.get_paginated, conversation_id, limit, before_id)

    async def set_async(self, conversation_id: str, conv: dict) -> None:
        await asyncio.to_thread(self.set, conversation_id, conv)

    async def append_message_async(self, conversation_id: str, message: dict) -> bool:
        return await asyncio.to_thread(self.append_message, conversation_id, message)

    async def append_messages_async(self, conversation_id: str, messages: list[dict]) -> bool:
        return await asyncio.to_thread(self.append_messages, conversation_id, messages)

    async def update_message_async(self, conversation_id: str, mid: str, message: dict) -> bool:
        return await asyncio.to_thread(self.update_message, conversation_id, mid, message)

    async def update_meta_async(self, conversation_id: str, updates: dict) -> Optional[dict]:
        return await asyncio.to_thread(self.update_meta, conversation_id, updates)

    async def delete_async(self, conversation_id: str) -> None:
        await asyncio.to_thread(self.delete, conversation_id)

    async def list_conversations_async(
        self,
        agent_id: Optional[str] = None,
        include_hidden: bool = False,
        domain: Optional[str] = None,
        exclude_domain_prefix: Optional[str] = None,
    ) -> list[dict]:
        return await asyncio.to_thread(
            self.list_conversations, agent_id, include_hidden, domain, exclude_domain_prefix,
        )

    async def count_messages_async(self, agent_id: Optional[str] = None) -> int:
        return await asyncio.to_thread(self.count_messages, agent_id)

    async def search_conversations_async(self, keyword: str, agent_id: Optional[str] = None) -> list[dict]:
        return await asyncio.to_thread(self.search_conversations, keyword, agent_id)

    async def soft_delete_async(self, conversation_id: str) -> bool:
        return await asyncio.to_thread(self.soft_delete, conversation_id)

    async def list_trash_async(self, agent_id: Optional[str] = None) -> list[dict]:
        return await asyncio.to_thread(self.list_trash, agent_id)

    async def restore_async(self, conversation_id: str) -> bool:
        return await asyncio.to_thread(self.restore, conversation_id)

    async def permanent_delete_async(self, conversation_id: str) -> bool:
        return await asyncio.to_thread(self.permanent_delete, conversation_id)

    async def empty_trash_async(self, agent_id: Optional[str] = None) -> int:
        return await asyncio.to_thread(self.empty_trash, agent_id)

    async def batch_restore_async(self, conversation_ids: list[str]) -> int:
        return await asyncio.to_thread(self.batch_restore, conversation_ids)

    async def batch_permanent_delete_async(self, conversation_ids: list[str]) -> int:
        return await asyncio.to_thread(self.batch_permanent_delete, conversation_ids)

    async def batch_soft_delete_async(self, conversation_ids: list[str]) -> int:
        return await asyncio.to_thread(self.batch_soft_delete, conversation_ids)

    async def rename_async(self, conversation_id: str, new_title: str) -> bool:
        return await asyncio.to_thread(self.rename, conversation_id, new_title)

    async def delete_by_agent_id_async(self, agent_id: str) -> int:
        return await asyncio.to_thread(self.delete_by_agent_id, agent_id)


# ── 单例 ──

conversation_store = ConversationFacade(ConversationRepository())
