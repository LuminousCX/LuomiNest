"""ConversationRepository — 对话存储（替代 conversations/*.json + _index.json）。

重构要点（前端后端项目锐评 · 高优先级 #1）：
- 消息拆至 ``conversation_messages`` 独立表（每消息一行，seq 自增主键）：
  - 追加消息 = 单条 INSERT（O(1)），不再「读全量 → append → 写全量」；
  - 分页 = SQL 层 keyset（seq < 游标）LIMIT/OFFSET，不再 Python 切片；
  - search_text / last_message 随消息写入增量维护，不再每次全量重算；
  - 搜索仍为 search_text LIKE（FTS5 预留扩展点，见模型注释）。
- ``save()`` 保留全量替换语义（upsert 元数据 + 事务内重建消息行），
  供压缩/重生成/导入等非常热路径使用；热路径请用 ``append_message`` /
  ``append_messages`` / ``update_message``。
- deleted_at 软删除（回收站）；消息行级联删除由 FK ON DELETE CASCADE 保证。
"""
import asyncio
from typing import Optional

from sqlalchemy import func, or_, select, text
from sqlalchemy import delete as sa_delete
from sqlalchemy import update as sa_update
from sqlalchemy.orm import defer

from app.core.exceptions import ConversationModeLockedError
from app.infrastructure.database.models.conversation import Conversation
from app.infrastructure.database.models.conversation_message import ConversationMessage
from app.infrastructure.database.repositories.base import BaseRepository, orm_to_dict, utcnow_iso
from app.infrastructure.database.session import sync_session_factory


def _msg_text(message: dict) -> str:
    """消息的纯文本内容（搜索/索引用；content 可能非字符串）。"""
    content = message.get("content", "") if isinstance(message, dict) else ""
    return content if isinstance(content, str) else ""


def _build_search_text(messages: list) -> str:
    """拼接所有消息 content 构建 search_text。"""
    parts = []
    for msg in messages or []:
        content = _msg_text(msg)
        if content:
            parts.append(content)
    return " ".join(parts)


def _build_last_message(messages: list) -> Optional[str]:
    """最后一条消息 content 前 50 字。"""
    if not messages:
        return None
    content = _msg_text(messages[-1])
    return content[:50] or None


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

    # ── 消息行辅助 ──

    @staticmethod
    def _message_row(conversation_id: str, message: dict) -> ConversationMessage:
        return ConversationMessage(
            conversation_id=conversation_id,
            mid=str(message.get("id", "") or ""),
            role=str(message.get("role", "") or ""),
            content=_msg_text(message),
            data=dict(message),
            created_at=utcnow_iso(),
        )

    @staticmethod
    def _row_to_message(row: ConversationMessage) -> dict:
        """消息行 → 与旧 messages 列表元素同构的 dict。"""
        if isinstance(row.data, dict):
            return dict(row.data)
        # 兜底（理论上不会发生：data 始终写入）
        msg: dict = {"role": row.role, "content": row.content}
        if row.mid:
            msg["id"] = row.mid
        return msg

    # ── Override save：全量替换（元数据 + 消息行，单事务） ──

    def save(self, key: str, data: dict) -> dict:
        conv = dict(data)
        messages = conv.pop("messages", None) or []
        conv["search_text"] = _build_search_text(messages)
        conv["last_message"] = _build_last_message(messages)
        if not conv.get("created_at"):
            conv["created_at"] = utcnow_iso()
        conv["updated_at"] = utcnow_iso()
        # 模式锁（洋葱架构 §6）：已有消息的对话 chat_mode 不可变更，后端权威校验
        self._enforce_mode_lock(key, conv)
        with sync_session_factory() as session:
            obj = session.get(Conversation, key)
            if obj is None:
                obj = Conversation(id=key)
                session.add(obj)
            for k, v in conv.items():
                if k != self.pk:
                    setattr(obj, k, v)
            # 事务内重建消息行（全量替换路径；热路径请用 append_message）
            session.execute(
                sa_delete(ConversationMessage).where(ConversationMessage.conversation_id == key)
            )
            for msg in messages:
                session.add(self._message_row(key, msg))
            session.commit()
            session.refresh(obj)
            result = orm_to_dict(obj)
        result["messages"] = messages
        return result

    # ── 增量写入（热路径，O(1) 追加） ──

    def append_message(self, conversation_id: str, message: dict) -> bool:
        """追加单条消息：INSERT 一行 + 增量维护 search_text/last_message/updated_at。"""
        content = _msg_text(message)
        with sync_session_factory() as session:
            if session.get(Conversation, conversation_id) is None:
                return False
            session.add(self._message_row(conversation_id, message))
            session.execute(
                text(
                    "UPDATE conversations SET "
                    "search_text = CASE WHEN COALESCE(search_text, '') = '' "
                    "  THEN :content ELSE search_text || ' ' || :content END, "
                    "last_message = :last, updated_at = :now "
                    "WHERE id = :key"
                ),
                {
                    "content": content,
                    "last": content[:50] or None,
                    "now": utcnow_iso(),
                    "key": conversation_id,
                },
            )
            session.commit()
            return True

    def append_messages(self, conversation_id: str, messages: list[dict]) -> bool:
        """批量追加多条消息（单事务，增量维护）。"""
        if not messages:
            return False
        with sync_session_factory() as session:
            if session.get(Conversation, conversation_id) is None:
                return False
            for msg in messages:
                session.add(self._message_row(conversation_id, msg))
            last = _build_last_message(messages)
            session.execute(
                text(
                    "UPDATE conversations SET "
                    "search_text = CASE WHEN COALESCE(search_text, '') = '' "
                    "  THEN :tail ELSE search_text || ' ' || :tail END, "
                    "last_message = :last, updated_at = :now "
                    "WHERE id = :key"
                ),
                {"tail": _build_search_text(messages), "last": last, "now": utcnow_iso(), "key": conversation_id},
            )
            session.commit()
            return True

    def update_message(self, conversation_id: str, mid: str, message: dict) -> bool:
        """按消息 id 更新单行（如合并文件内容的最后一条 user 消息），并重建 search_text。"""
        if not mid:
            return False
        with sync_session_factory() as session:
            row = (
                session.execute(
                    select(ConversationMessage)
                    .where(
                        ConversationMessage.conversation_id == conversation_id,
                        ConversationMessage.mid == mid,
                    )
                    .order_by(ConversationMessage.seq.desc())
                    .limit(1)
                )
                .scalars()
                .first()
            )
            if row is None:
                return False
            row.data = dict(message)
            row.content = _msg_text(message)
            # 消息集合内容变更 → 从 DB 重建 search_text / last_message（非热路径，可接受）
            contents = (
                session.execute(
                    select(ConversationMessage.content)
                    .where(ConversationMessage.conversation_id == conversation_id)
                    .order_by(ConversationMessage.seq.asc())
                )
                .scalars()
                .all()
            )
            session.execute(
                text(
                    "UPDATE conversations SET search_text = :st, last_message = :last, "
                    "updated_at = :now WHERE id = :key"
                ),
                {
                    "st": " ".join(c for c in contents if c),
                    "last": (contents[-1][:50] if contents else None),
                    "now": utcnow_iso(),
                    "key": conversation_id,
                },
            )
            session.commit()
            return True

    def update_meta(self, conversation_id: str, updates: dict) -> Optional[dict]:
        """仅更新对话元数据（不含消息），不影响 search_text/last_message。"""
        updates = dict(updates)
        updates.pop("messages", None)
        updates.pop("search_text", None)
        if not updates:
            return self.get_meta(conversation_id)
        return super().update(conversation_id, updates)

    def _enforce_mode_lock(self, key: str, data: dict) -> None:
        """模式锁定校验（§6）：会话已有消息后 chat_mode 不可变更。

        - 新建会话设初始模式：不受限（无存量行）
        - 存量会话无消息：仍允许变更
        - 存量会话有消息且模式不同：抛 ConversationModeLockedError（409 / ERR_CONV_MODE_LOCKED）
        - 请求未携带 chat_mode 或模式相同：不受限
        """
        if "chat_mode" not in data:
            return
        new_mode = data.get("chat_mode")
        if not new_mode:
            return
        with sync_session_factory() as session:
            obj = session.get(Conversation, key)
            if obj is None:
                return  # 新建会话，初始模式不受限
            has_messages = (
                session.execute(
                    select(func.count())
                    .select_from(ConversationMessage)
                    .where(ConversationMessage.conversation_id == key)
                ).scalar()
                or 0
            ) > 0
            old_mode = obj.chat_mode or "normal"
        if not has_messages:
            return
        if str(new_mode) != str(old_mode):
            raise ConversationModeLockedError(
                f"Conversation {key} already has messages, "
                f"chat_mode cannot change from '{old_mode}' to '{new_mode}'"
            )

    # ── 读路径（消息来自 conversation_messages 表） ──

    def get(self, key: str) -> Optional[dict]:
        with sync_session_factory() as session:
            obj = session.get(Conversation, key)
            if obj is None:
                return None
            d = orm_to_dict(obj)
            d.pop("search_text", None)
            rows = (
                session.execute(
                    select(ConversationMessage)
                    .where(ConversationMessage.conversation_id == key)
                    .order_by(ConversationMessage.seq.asc())
                )
                .scalars()
                .all()
            )
            d["messages"] = [self._row_to_message(r) for r in rows]
            return d

    def get_meta(self, conversation_id: str) -> Optional[dict]:
        """加载对话元数据（不含 messages/search_text），SQL 层跳过重列加载。"""
        with sync_session_factory() as session:
            stmt = (
                select(Conversation)
                .options(defer(Conversation.search_text))
                .where(Conversation.id == conversation_id)
            )
            obj = session.execute(stmt).scalar_one_or_none()
            if obj is None:
                return None
            d = orm_to_dict(obj)
            d["messages"] = []
            return d

    def get_paginated(self, conversation_id: str, limit: int = 100, before_id: Optional[str] = None) -> Optional[dict]:
        """加载对话 + 分页消息（最新 N 条），SQL 层 keyset 分页（seq 游标）。"""
        with sync_session_factory() as session:
            obj = session.get(Conversation, conversation_id)
            if obj is None:
                return None
            d = orm_to_dict(obj)
            d.pop("search_text", None)

            # 游标解析：before_id（消息 id）→ seq；空/找不到时按"最新一页"处理
            before_seq: Optional[int] = None
            if before_id:
                before_seq = (
                    session.execute(
                        select(ConversationMessage.seq)
                        .where(
                            ConversationMessage.conversation_id == conversation_id,
                            ConversationMessage.mid == before_id,
                        )
                        .order_by(ConversationMessage.seq.desc())
                        .limit(1)
                    )
                    .scalar()
                )

            total = (
                session.execute(
                    select(func.count())
                    .select_from(ConversationMessage)
                    .where(ConversationMessage.conversation_id == conversation_id)
                ).scalar()
                or 0
            )

            stmt = select(ConversationMessage).where(ConversationMessage.conversation_id == conversation_id)
            if before_seq is not None:
                stmt = stmt.where(ConversationMessage.seq < before_seq)
            rows = (
                session.execute(stmt.order_by(ConversationMessage.seq.desc()).limit(limit))
                .scalars()
                .all()
            )
            rows = list(reversed(rows))
            d["messages"] = [self._row_to_message(r) for r in rows]

            if before_seq is not None:
                # has_more：游标之前是否还有更早的消息
                first_seq = rows[0].seq if rows else before_seq
                older = (
                    session.execute(
                        select(func.count())
                        .select_from(ConversationMessage)
                        .where(
                            ConversationMessage.conversation_id == conversation_id,
                            ConversationMessage.seq < first_seq,
                        )
                    ).scalar()
                    or 0
                )
                d["has_more"] = older > 0
            else:
                d["has_more"] = total > limit

            d["total_messages"] = total
            return d

    # ── List / Search ──

    def list_meta(
        self,
        agent_id: Optional[str] = None,
        include_hidden: bool = False,
        domain: Optional[str] = None,
        exclude_domain_prefix: Optional[str] = None,
    ) -> list[dict]:
        """列表查询（不含 messages/search_text），按 updated_at 降序。

        对话域过滤（洋葱架构 §5.3 列表隔离）：
        - domain：精确匹配对话域（如 workbench / agent:{id} / platform:{instId}）
        - exclude_domain_prefix：排除指定前缀的域（domain 为空/NULL 的对话不排除，兼容存量）
        """
        with sync_session_factory() as session:
            stmt = select(Conversation).where(Conversation.deleted_at.is_(None))
            if not include_hidden:
                stmt = stmt.where(
                    or_(Conversation.is_hidden.is_(False), Conversation.is_hidden.is_(None))
                )
            if agent_id:
                stmt = stmt.where(Conversation.agent_id == agent_id)
            if domain:
                stmt = stmt.where(Conversation.domain == domain)
            if exclude_domain_prefix:
                stmt = stmt.where(
                    or_(
                        Conversation.domain.is_(None),
                        Conversation.domain == "",
                        ~Conversation.domain.like(f"{exclude_domain_prefix}%"),
                    )
                )
            stmt = stmt.order_by(Conversation.updated_at.desc())
            objs = session.execute(stmt).scalars().all()
            result = []
            for o in objs:
                d = orm_to_dict(o)
                d.pop("search_text", None)
                result.append(d)
            return result

    def count_messages(self, agent_id: Optional[str] = None) -> int:
        """统计所有非删除对话的消息总数（DB 层聚合，避免 N+1）。"""
        with sync_session_factory() as session:
            stmt = select(func.count()).select_from(
                ConversationMessage.__table__.join(
                    Conversation.__table__,
                    ConversationMessage.conversation_id == Conversation.id,
                )
            ).where(Conversation.deleted_at.is_(None))
            if agent_id:
                stmt = stmt.where(Conversation.agent_id == agent_id)
            return session.execute(stmt).scalar() or 0

    def search(self, keyword: str, agent_id: Optional[str] = None) -> list[dict]:
        if not keyword or not keyword.strip():
            return []
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

    # ── Soft delete / Trash（消息行由 FK CASCADE 级联清理） ──

    def soft_delete(self, conversation_id: str) -> bool:
        with sync_session_factory() as session:
            obj = session.get(Conversation, conversation_id)
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
                d.pop("search_text", None)
                result.append(d)
            return result

    def restore(self, conversation_id: str) -> bool:
        with sync_session_factory() as session:
            obj = session.get(Conversation, conversation_id)
            if obj is None:
                return False
            obj.deleted_at = None
            session.commit()
            return True

    def permanent_delete(self, conversation_id: str) -> bool:
        return self.delete(conversation_id)

    def empty_trash(self, agent_id: Optional[str] = None) -> int:
        """批量清空回收站（单次 DELETE，消息行级联清理）。"""
        with sync_session_factory() as session:
            stmt = sa_delete(Conversation).where(Conversation.deleted_at.is_not(None))
            if agent_id:
                stmt = stmt.where(Conversation.agent_id == agent_id)
            result = session.execute(stmt)
            session.commit()
            return result.rowcount or 0

    def batch_soft_delete(self, conversation_ids: list[str]) -> int:
        """批量软删除（单次 UPDATE）。"""
        if not conversation_ids:
            return 0
        with sync_session_factory() as session:
            stmt = (
                sa_update(Conversation)
                .where(Conversation.id.in_(conversation_ids), Conversation.deleted_at.is_(None))
                .values(deleted_at=utcnow_iso(), updated_at=utcnow_iso())
            )
            result = session.execute(stmt)
            session.commit()
            return result.rowcount or 0

    def batch_restore(self, conversation_ids: list[str]) -> int:
        """批量恢复（单次 UPDATE）。"""
        if not conversation_ids:
            return 0
        with sync_session_factory() as session:
            stmt = (
                sa_update(Conversation)
                .where(Conversation.id.in_(conversation_ids), Conversation.deleted_at.is_not(None))
                .values(deleted_at=None, updated_at=utcnow_iso())
            )
            result = session.execute(stmt)
            session.commit()
            return result.rowcount or 0

    def batch_permanent_delete(self, conversation_ids: list[str]) -> int:
        """批量永久删除（单次 DELETE，消息行级联清理）。"""
        if not conversation_ids:
            return 0
        with sync_session_factory() as session:
            stmt = sa_delete(Conversation).where(Conversation.id.in_(conversation_ids))
            result = session.execute(stmt)
            session.commit()
            return result.rowcount or 0

    def rename(self, conversation_id: str, new_title: str) -> bool:
        with sync_session_factory() as session:
            obj = session.get(Conversation, conversation_id)
            if obj is None:
                return False
            obj.title = new_title
            obj.updated_at = utcnow_iso()
            session.commit()
            return True

    def delete_by_agent_id(self, agent_id: str) -> int:
        """批量删除某 agent 的所有对话（单次 DELETE，消息行级联清理）。"""
        with sync_session_factory() as session:
            stmt = sa_delete(Conversation).where(Conversation.agent_id == agent_id)
            result = session.execute(stmt)
            session.commit()
            return result.rowcount or 0

    # ── Async wrappers ──

    async def get_meta_async(self, conversation_id: str) -> Optional[dict]:
        return await asyncio.to_thread(self.get_meta, conversation_id)

    async def get_paginated_async(self, conversation_id: str, limit: int = 100, before_id: Optional[str] = None) -> Optional[dict]:
        return await asyncio.to_thread(self.get_paginated, conversation_id, limit, before_id)

    async def append_message_async(self, conversation_id: str, message: dict) -> bool:
        return await asyncio.to_thread(self.append_message, conversation_id, message)

    async def append_messages_async(self, conversation_id: str, messages: list[dict]) -> bool:
        return await asyncio.to_thread(self.append_messages, conversation_id, messages)

    async def update_message_async(self, conversation_id: str, mid: str, message: dict) -> bool:
        return await asyncio.to_thread(self.update_message, conversation_id, mid, message)

    async def update_meta_async(self, conversation_id: str, updates: dict) -> Optional[dict]:
        return await asyncio.to_thread(self.update_meta, conversation_id, updates)

    async def list_meta_async(
        self,
        agent_id: Optional[str] = None,
        include_hidden: bool = False,
        domain: Optional[str] = None,
        exclude_domain_prefix: Optional[str] = None,
    ) -> list[dict]:
        return await asyncio.to_thread(
            self.list_meta, agent_id, include_hidden, domain, exclude_domain_prefix,
        )

    async def search_async(self, keyword: str, agent_id: Optional[str] = None) -> list[dict]:
        return await asyncio.to_thread(self.search, keyword, agent_id)

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

    async def batch_soft_delete_async(self, conversation_ids: list[str]) -> int:
        return await asyncio.to_thread(self.batch_soft_delete, conversation_ids)

    async def batch_restore_async(self, conversation_ids: list[str]) -> int:
        return await asyncio.to_thread(self.batch_restore, conversation_ids)

    async def batch_permanent_delete_async(self, conversation_ids: list[str]) -> int:
        return await asyncio.to_thread(self.batch_permanent_delete, conversation_ids)

    async def rename_async(self, conversation_id: str, new_title: str) -> bool:
        return await asyncio.to_thread(self.rename, conversation_id, new_title)

    async def delete_by_agent_id_async(self, agent_id: str) -> int:
        return await asyncio.to_thread(self.delete_by_agent_id, agent_id)
