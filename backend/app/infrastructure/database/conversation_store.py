"""对话存储 — 委托 ConversationRepository + conversations 表（SQLite）。

替代原 data/conversations/*.json + _index.json 的 per-conv 文件方案：
- messages 用 JSON 列存储（不拆表）
- search_text 用 LIKE 搜索
- deleted_at 软删除（回收站）
- save() 自动构建 search_text 与 last_message
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

    def get(self, conv_id: str) -> Optional[dict]:
        return self._repo.get(conv_id)

    def get_meta(self, conv_id: str) -> Optional[dict]:
        """加载对话元数据（不含 messages/search_text）。"""
        return self._repo.get_meta(conv_id)

    def get_paginated(self, conv_id: str, limit: int = 100, before_id: Optional[str] = None) -> Optional[dict]:
        """加载对话 + 分页消息（最新 N 条）。"""
        return self._repo.get_paginated(conv_id, limit, before_id)

    def set(self, conv_id: str, conv: dict) -> None:
        self._repo.save(conv_id, conv)

    def delete(self, conv_id: str) -> None:
        self._repo.delete(conv_id)

    # ── List / Search ──

    def list_conversations(self, agent_id: Optional[str] = None, include_hidden: bool = False) -> list[dict]:
        return self._repo.list_meta(agent_id, include_hidden=include_hidden)

    def count_messages(self, agent_id: Optional[str] = None) -> int:
        return self._repo.count_messages(agent_id)

    def search_conversations(self, keyword: str, agent_id: Optional[str] = None) -> list[dict]:
        return self._repo.search(keyword, agent_id)

    # ── Soft delete / Trash ──

    def soft_delete(self, conv_id: str) -> bool:
        return self._repo.soft_delete(conv_id)

    def list_trash(self, agent_id: Optional[str] = None) -> list[dict]:
        return self._repo.list_trash(agent_id)

    def restore(self, conv_id: str) -> bool:
        return self._repo.restore(conv_id)

    def permanent_delete(self, conv_id: str) -> bool:
        return self._repo.permanent_delete(conv_id)

    def empty_trash(self, agent_id: Optional[str] = None) -> int:
        return self._repo.empty_trash(agent_id)

    def batch_restore(self, conv_ids: list[str]) -> int:
        return self._repo.batch_restore(conv_ids)

    def batch_permanent_delete(self, conv_ids: list[str]) -> int:
        return self._repo.batch_permanent_delete(conv_ids)

    def batch_soft_delete(self, conv_ids: list[str]) -> int:
        return self._repo.batch_soft_delete(conv_ids)

    def rename(self, conv_id: str, new_title: str) -> bool:
        return self._repo.rename(conv_id, new_title)

    def delete_by_agent_id(self, agent_id: str) -> int:
        return self._repo.delete_by_agent_id(agent_id)

    # ── Misc ──

    def items(self) -> list:
        """返回 [(conv_id, meta), ...]（不含 messages/search_text）。"""
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
        for conv_id, conv in old_data.items():
            if not isinstance(conv, dict):
                continue
            if self._repo.get(conv_id) is not None:
                continue
            self._repo.save(conv_id, conv)
            migrated += 1
        return migrated

    # ── Async wrappers ──

    async def get_async(self, conv_id: str) -> Optional[dict]:
        return await asyncio.to_thread(self.get, conv_id)

    async def get_meta_async(self, conv_id: str) -> Optional[dict]:
        return await asyncio.to_thread(self.get_meta, conv_id)

    async def get_paginated_async(self, conv_id: str, limit: int = 100, before_id: Optional[str] = None) -> Optional[dict]:
        return await asyncio.to_thread(self.get_paginated, conv_id, limit, before_id)

    async def set_async(self, conv_id: str, conv: dict) -> None:
        await asyncio.to_thread(self.set, conv_id, conv)

    async def delete_async(self, conv_id: str) -> None:
        await asyncio.to_thread(self.delete, conv_id)

    async def list_conversations_async(self, agent_id: Optional[str] = None, include_hidden: bool = False) -> list[dict]:
        return await asyncio.to_thread(self.list_conversations, agent_id, include_hidden)

    async def count_messages_async(self, agent_id: Optional[str] = None) -> int:
        return await asyncio.to_thread(self.count_messages, agent_id)

    async def search_conversations_async(self, keyword: str, agent_id: Optional[str] = None) -> list[dict]:
        return await asyncio.to_thread(self.search_conversations, keyword, agent_id)

    async def soft_delete_async(self, conv_id: str) -> bool:
        return await asyncio.to_thread(self.soft_delete, conv_id)

    async def list_trash_async(self, agent_id: Optional[str] = None) -> list[dict]:
        return await asyncio.to_thread(self.list_trash, agent_id)

    async def restore_async(self, conv_id: str) -> bool:
        return await asyncio.to_thread(self.restore, conv_id)

    async def permanent_delete_async(self, conv_id: str) -> bool:
        return await asyncio.to_thread(self.permanent_delete, conv_id)

    async def empty_trash_async(self, agent_id: Optional[str] = None) -> int:
        return await asyncio.to_thread(self.empty_trash, agent_id)

    async def batch_restore_async(self, conv_ids: list[str]) -> int:
        return await asyncio.to_thread(self.batch_restore, conv_ids)

    async def batch_permanent_delete_async(self, conv_ids: list[str]) -> int:
        return await asyncio.to_thread(self.batch_permanent_delete, conv_ids)

    async def batch_soft_delete_async(self, conv_ids: list[str]) -> int:
        return await asyncio.to_thread(self.batch_soft_delete, conv_ids)

    async def rename_async(self, conv_id: str, new_title: str) -> bool:
        return await asyncio.to_thread(self.rename, conv_id, new_title)

    async def delete_by_agent_id_async(self, agent_id: str) -> int:
        return await asyncio.to_thread(self.delete_by_agent_id, agent_id)


# ── 单例 ──

conversation_store = ConversationFacade(ConversationRepository())
