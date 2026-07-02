"""ConversationRepository — 对话存储（替代 conversations/*.json + _index.json）。

- messages 用 JSON 列存储（不拆表）
- search_text 用 LIKE 搜索
- deleted_at 软删除（回收站）
- save() 自动构建 search_text 与 last_message
"""
import asyncio
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, or_, select

from app.infrastructure.database.models.conversation import Conversation
from app.infrastructure.database.repositories.base import BaseRepository, orm_to_dict, utcnow_iso
from app.infrastructure.database.session import sync_session_factory


def _build_search_text(conv: dict) -> str:
    """拼接所有消息 content 构建 search_text。"""
    parts = []
    for msg in conv.get("messages", []):
        content = msg.get("content", "")
        if isinstance(content, str) and content:
            parts.append(content)
    return " ".join(parts)


def _build_last_message(conv: dict) -> Optional[str]:
    """最后一条消息 content 前 50 字。"""
    messages = conv.get("messages")
    if not messages:
        return None
    return messages[-1].get("content", "")[:50]


def _build_snippet(search_text: str, title: str, keyword: str) -> str:
    """提取匹配片段（前后 30 字）。"""
    src = search_text or title
    src_lower = src.lower()
    pos = src_lower.find(keyword.lower())
    if pos < 0:
        return title
    start = max(0, pos - 30)
    end = min(len(src), pos + len(keyword) + 30)
    snippet = src[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(src):
        snippet = snippet + "..."
    return snippet


class ConversationRepository(BaseRepository):
    model = Conversation
    pk = "id"

    # ── Override save to build search_text/last_message ──

    def save(self, key: str, data: dict) -> dict:
        conv = dict(data)
        conv["search_text"] = _build_search_text(conv)
        conv["last_message"] = _build_last_message(conv)
        if not conv.get("created_at"):
            conv["created_at"] = utcnow_iso()
        conv["updated_at"] = utcnow_iso()
        return super().save(key, conv)

    # ── List / Search ──

    def list_meta(self, agent_id: Optional[str] = None) -> list[dict]:
        """列表查询（不含 messages/search_text），按 updated_at 降序。"""
        with sync_session_factory() as session:
            stmt = select(Conversation).where(Conversation.deleted_at.is_(None))
            if agent_id:
                stmt = stmt.where(Conversation.agent_id == agent_id)
            stmt = stmt.order_by(Conversation.updated_at.desc())
            objs = session.execute(stmt).scalars().all()
            result = []
            for o in objs:
                d = orm_to_dict(o)
                d.pop("messages", None)
                d.pop("search_text", None)
                result.append(d)
            return result

    def search(self, keyword: str, agent_id: Optional[str] = None) -> list[dict]:
        if not keyword or not keyword.strip():
            return []
        q = f"%{keyword.strip()}%"
        q_lower = keyword.strip().lower()
        with sync_session_factory() as session:
            stmt = select(Conversation).where(
                Conversation.deleted_at.is_(None),
                or_(
                    func.lower(Conversation.search_text).like(f"%{q_lower}%"),
                    func.lower(Conversation.title).like(f"%{q_lower}%"),
                ),
            )
            if agent_id:
                stmt = stmt.where(Conversation.agent_id == agent_id)
            objs = session.execute(stmt).scalars().all()
            results = []
            for o in objs:
                snippet = _build_snippet(o.search_text or "", o.title or "", keyword.strip())
                results.append({
                    "id": o.id,
                    "title": o.title,
                    "snippet": snippet,
                    "updated_at": o.updated_at,
                })
            results.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
            return results

    # ── Soft delete / Trash ──

    def soft_delete(self, conv_id: str) -> bool:
        with sync_session_factory() as session:
            obj = session.get(Conversation, conv_id)
            if obj is None:
                return False
            obj.deleted_at = utcnow_iso()
            session.commit()
            return True

    def list_trash(self, agent_id: Optional[str] = None) -> list[dict]:
        with sync_session_factory() as session:
            stmt = select(Conversation).where(Conversation.deleted_at.is_not(None))
            if agent_id:
                stmt = stmt.where(Conversation.agent_id == agent_id)
            stmt = stmt.order_by(Conversation.deleted_at.desc())
            objs = session.execute(stmt).scalars().all()
            result = []
            for o in objs:
                d = orm_to_dict(o)
                d.pop("messages", None)
                d.pop("search_text", None)
                result.append(d)
            return result

    def restore(self, conv_id: str) -> bool:
        with sync_session_factory() as session:
            obj = session.get(Conversation, conv_id)
            if obj is None:
                return False
            obj.deleted_at = None
            session.commit()
            return True

    def permanent_delete(self, conv_id: str) -> bool:
        return self.delete(conv_id)

    def empty_trash(self, agent_id: Optional[str] = None) -> int:
        trash = self.list_trash(agent_id)
        count = 0
        for item in trash:
            if self.delete(item["id"]):
                count += 1
        return count

    def batch_soft_delete(self, conv_ids: list[str]) -> int:
        return sum(1 for cid in conv_ids if self.soft_delete(cid))

    def batch_restore(self, conv_ids: list[str]) -> int:
        return sum(1 for cid in conv_ids if self.restore(cid))

    def batch_permanent_delete(self, conv_ids: list[str]) -> int:
        return sum(1 for cid in conv_ids if self.permanent_delete(cid))

    def rename(self, conv_id: str, new_title: str) -> bool:
        with sync_session_factory() as session:
            obj = session.get(Conversation, conv_id)
            if obj is None:
                return False
            obj.title = new_title
            obj.updated_at = utcnow_iso()
            session.commit()
            return True

    def delete_by_agent_id(self, agent_id: str) -> int:
        convs = self.list_meta(agent_id)
        return sum(1 for c in convs if self.delete(c["id"]))

    # ── Async wrappers ──

    async def list_meta_async(self, agent_id: Optional[str] = None) -> list[dict]:
        return await asyncio.to_thread(self.list_meta, agent_id)

    async def search_async(self, keyword: str, agent_id: Optional[str] = None) -> list[dict]:
        return await asyncio.to_thread(self.search, keyword, agent_id)

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

    async def batch_soft_delete_async(self, conv_ids: list[str]) -> int:
        return await asyncio.to_thread(self.batch_soft_delete, conv_ids)

    async def batch_restore_async(self, conv_ids: list[str]) -> int:
        return await asyncio.to_thread(self.batch_restore, conv_ids)

    async def batch_permanent_delete_async(self, conv_ids: list[str]) -> int:
        return await asyncio.to_thread(self.batch_permanent_delete, conv_ids)

    async def rename_async(self, conv_id: str, new_title: str) -> bool:
        return await asyncio.to_thread(self.rename, conv_id, new_title)

    async def delete_by_agent_id_async(self, agent_id: str) -> int:
        return await asyncio.to_thread(self.delete_by_agent_id, agent_id)
