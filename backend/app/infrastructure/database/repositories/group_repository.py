"""GroupRepository — 群组配置（替代 groups.json）。

消息拆至 ``group_messages`` 独立表（每消息一行，seq 自增主键，与
conversation_messages 同款设计）：
- 追加消息 = 单条 INSERT（O(1)），不再「读全量 → append → 写全量」；
- 历史/最近上下文读取走 SQL 层 ORDER BY seq；
- 群组删除时消息行由 FK ON DELETE CASCADE 级联清理。
- ``save()`` 为 upsert；data 携带 ``messages`` 键时按全量替换语义在事务内
  重建消息行（成员变更/元数据编辑等冷路径整体回写），未携带时不触碰消息行。
"""
import asyncio
from typing import Optional

from sqlalchemy import select, text
from sqlalchemy import delete as sa_delete

from app.infrastructure.database.models.group import Group
from app.infrastructure.database.models.group_message import GroupMessage
from app.infrastructure.database.repositories.base import BaseRepository, orm_to_dict, utcnow_iso
from app.infrastructure.database.session import sync_session_factory


def _msg_text(message: dict) -> str:
    """消息的纯文本内容（content 可能非字符串）。"""
    content = message.get("content", "") if isinstance(message, dict) else ""
    return content if isinstance(content, str) else ""


def _msg_field(message: dict, *keys: str) -> str:
    """按候选键序取消息字段（存量消息存在 camelCase/snake_case 两种键风格）。"""
    for k in keys:
        v = message.get(k)
        if v:
            return str(v)
    return ""


class GroupRepository(BaseRepository):
    model = Group
    pk = "id"

    # ── 消息行辅助 ──

    @staticmethod
    def _message_row(group_id: str, message: dict) -> GroupMessage:
        return GroupMessage(
            group_id=group_id,
            mid=_msg_field(message, "id"),
            sender_type=_msg_field(message, "sender_type", "senderType"),
            content=_msg_text(message),
            data=dict(message),
            created_at=_msg_field(message, "timestamp"),
        )

    @staticmethod
    def _row_to_message(row: GroupMessage) -> dict:
        """消息行 → 与旧 messages 列表元素同构的 dict（优先还原原始 dict）。"""
        if isinstance(row.data, dict):
            return dict(row.data)
        # 兜底（理论上不会发生：data 始终写入）
        msg: dict = {"sender_type": row.sender_type, "content": row.content}
        if row.mid:
            msg["id"] = row.mid
        if row.created_at:
            msg["timestamp"] = row.created_at
        return msg

    # ── Override save：upsert + 可选消息行全量替换（单事务） ──

    def save(self, key: str, data: dict) -> dict:
        group = dict(data)
        has_messages = "messages" in group
        messages = group.pop("messages", None) or []
        with sync_session_factory() as session:
            obj = session.get(Group, key)
            if obj is None:
                obj = Group(id=key)
                session.add(obj)
            for k, v in group.items():
                if k != self.pk:
                    setattr(obj, k, v)
            if has_messages:
                # 全量替换路径（冷路径整体回写）；热路径请用 append_message
                session.execute(sa_delete(GroupMessage).where(GroupMessage.group_id == key))
                for msg in messages:
                    session.add(self._message_row(key, msg))
            session.commit()
            session.refresh(obj)
            result = orm_to_dict(obj)
        result["messages"] = messages if has_messages else self.get_messages(key)
        return result

    # ── 消息增量写入（热路径，O(1) 追加） ──

    def append_message(self, group_id: str, message: dict) -> bool:
        """追加单条群聊消息：INSERT 一行 + 群组 updated_at 取消息时间戳。"""
        with sync_session_factory() as session:
            if session.get(Group, group_id) is None:
                return False
            session.add(self._message_row(group_id, message))
            session.execute(
                text("UPDATE groups SET updated_at = :now WHERE id = :key"),
                {"now": _msg_field(message, "timestamp") or utcnow_iso(), "key": group_id},
            )
            session.commit()
            return True

    def append_messages(self, group_id: str, messages: list[dict]) -> bool:
        """批量追加多条群聊消息（单事务，updated_at 取最后一条的时间戳）。"""
        if not messages:
            return False
        with sync_session_factory() as session:
            if session.get(Group, group_id) is None:
                return False
            for msg in messages:
                session.add(self._message_row(group_id, msg))
            session.execute(
                text("UPDATE groups SET updated_at = :now WHERE id = :key"),
                {
                    "now": _msg_field(messages[-1], "timestamp") or utcnow_iso(),
                    "key": group_id,
                },
            )
            session.commit()
            return True

    # ── 读路径（消息来自 group_messages 表） ──

    def get_messages(self, group_id: str, limit: Optional[int] = None) -> list[dict]:
        """按 seq 升序读取群聊消息（limit 取最新 N 条，仍按时间正序返回）。"""
        with sync_session_factory() as session:
            stmt = select(GroupMessage).where(GroupMessage.group_id == group_id)
            if limit is not None:
                rows = (
                    session.execute(stmt.order_by(GroupMessage.seq.desc()).limit(limit))
                    .scalars()
                    .all()
                )
                rows = list(reversed(rows))
            else:
                rows = session.execute(stmt.order_by(GroupMessage.seq.asc())).scalars().all()
            return [self._row_to_message(r) for r in rows]

    def get(self, key: str) -> Optional[dict]:
        """加载群组（messages 来自 group_messages 表，与旧 JSON 列同构）。"""
        with sync_session_factory() as session:
            obj = session.get(Group, key)
            if obj is None:
                return None
            d = orm_to_dict(obj)
            rows = (
                session.execute(
                    select(GroupMessage)
                    .where(GroupMessage.group_id == key)
                    .order_by(GroupMessage.seq.asc())
                )
                .scalars()
                .all()
            )
            d["messages"] = [self._row_to_message(r) for r in rows]
            return d

    def get_all(self) -> list[dict]:
        """加载全部群组（每个群组携带完整 messages，与旧 JSON 列读取语义一致）。"""
        with sync_session_factory() as session:
            objs = session.execute(select(Group)).scalars().all()
            rows = (
                session.execute(
                    select(GroupMessage).order_by(GroupMessage.group_id.asc(), GroupMessage.seq.asc())
                )
                .scalars()
                .all()
            )
        grouped: dict[str, list[dict]] = {}
        for r in rows:
            grouped.setdefault(r.group_id, []).append(self._row_to_message(r))
        return [{**orm_to_dict(o), "messages": grouped.get(o.id, [])} for o in objs]

    def get_meta(self, group_id: str) -> Optional[dict]:
        """加载群组元数据（不含消息行，协作消息批量落库等场景避免整表加载）。"""
        with sync_session_factory() as session:
            obj = session.get(Group, group_id)
            if obj is None:
                return None
            d = orm_to_dict(obj)
            d["messages"] = []
            return d

    # ── Async wrappers ──

    async def append_message_async(self, group_id: str, message: dict) -> bool:
        return await asyncio.to_thread(self.append_message, group_id, message)

    async def append_messages_async(self, group_id: str, messages: list[dict]) -> bool:
        return await asyncio.to_thread(self.append_messages, group_id, messages)

    async def get_messages_async(self, group_id: str, limit: Optional[int] = None) -> list[dict]:
        return await asyncio.to_thread(self.get_messages, group_id, limit)

    async def get_meta_async(self, group_id: str) -> Optional[dict]:
        return await asyncio.to_thread(self.get_meta, group_id)
