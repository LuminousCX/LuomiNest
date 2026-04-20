"""对话记录数据访问对象。

基于 SQLAlchemy ORM 实现对话会话和消息的 CRUD 操作。
"""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Optional

from sqlalchemy import delete, func, select, update

from src.dao.database import DatabaseManager
from src.exceptions import DaoError
from src.model.conversation import (
    ConversationEntity,
    ConversationModel,
    MessageEntity,
    MessageModel,
    MessageRole,
    ResponseMode,
)
from src.utils.datetime_utils import now_beijing
from src.utils.logger import get_logger

logger = get_logger()

_CONV_CACHE_LOCK = threading.Lock()
_CONV_CACHE: dict[str, ConversationEntity] = {}
_CONV_CACHE_MAX = 64


class ConversationDao:
    """对话会话 DAO。

    使用 SQLAlchemy ORM 进行数据库操作。

    Attributes:
        db_manager: 数据库管理器。
    """

    def __init__(self, db_manager: DatabaseManager) -> None:
        self.db_manager = db_manager

    def insert_conversation(self, conversation: ConversationEntity) -> ConversationEntity:
        """插入对话会话。"""
        with self.db_manager.get_session() as session:
            conv_model = ConversationModel(
                id=conversation.id,
                agent_id=conversation.agent_id,
                title=conversation.title,
                mode=conversation.mode.value,
                total_tokens=conversation.total_tokens,
                created_at=conversation.created_at,
                updated_at=conversation.updated_at,
            )
            session.add(conv_model)

            for msg in conversation.messages:
                msg_model = MessageModel(
                    id=msg.id,
                    conversation_id=conversation.id,
                    role=msg.role.value,
                    content=msg.content,
                    tokens=msg.tokens,
                    created_at=msg.created_at,
                )
                session.add(msg_model)

        self._cache_put(conversation.id, conversation)
        logger.info(f"对话会话创建成功: id={conversation.id}")
        return conversation

    def add_message(self, conversation_id: str, message: MessageEntity) -> None:
        """向已有会话添加消息。"""
        with self.db_manager.get_session() as session:
            msg_model = MessageModel(
                id=message.id,
                conversation_id=conversation_id,
                role=message.role.value,
                content=message.content,
                tokens=message.tokens,
                created_at=message.created_at,
            )
            session.add(msg_model)

            stmt = (
                update(ConversationModel)
                .where(ConversationModel.id == conversation_id)
                .values(
                    total_tokens=ConversationModel.total_tokens + message.tokens,
                    updated_at=message.created_at,
                )
            )
            session.execute(stmt)

        self._cache_evict(conversation_id)

    def select_conversation_by_id(self, conversation_id: str) -> Optional[ConversationEntity]:
        """根据 ID 查询对话会话（含所有消息）。"""
        cached = self._cache_get(conversation_id)
        if cached is not None:
            return cached

        with self.db_manager.get_session() as session:
            conv_model = session.get(ConversationModel, conversation_id)
            if conv_model is None:
                return None

            messages = self._select_messages_by_conversation_id(session, conversation_id)
            entity = self._model_to_entity(conv_model, messages)
            self._cache_put(conversation_id, entity)
            return entity

    def select_conversations_by_agent(
        self, agent_id: str, limit: int = 50
    ) -> list[ConversationEntity]:
        """根据 Agent ID 查询对话列表（不含消息详情）。"""
        with self.db_manager.get_session() as session:
            stmt = (
                select(ConversationModel)
                .where(ConversationModel.agent_id == agent_id)
                .order_by(ConversationModel.updated_at.desc())
                .limit(limit)
            )
            results = session.execute(stmt).scalars().all()
            return [self._model_to_entity(m, []) for m in results]

    def select_all_conversations(self, limit: int = 100) -> list[ConversationEntity]:
        """查询所有对话会话（不含消息详情）。"""
        with self.db_manager.get_session() as session:
            stmt = (
                select(ConversationModel)
                .order_by(ConversationModel.updated_at.desc())
                .limit(limit)
            )
            results = session.execute(stmt).scalars().all()
            return [self._model_to_entity(m, []) for m in results]

    def _select_messages_by_conversation_id(
        self, session, conversation_id: str
    ) -> list[MessageEntity]:
        """查询会话下的所有消息。"""
        stmt = (
            select(MessageModel)
            .where(MessageModel.conversation_id == conversation_id)
            .order_by(MessageModel.created_at.asc())
        )
        results = session.execute(stmt).scalars().all()
        return [self._msg_model_to_entity(m) for m in results]

    def update_conversation_mode(self, conversation_id: str, mode: str) -> bool:
        """更新对话模式。"""
        with self.db_manager.get_session() as session:
            stmt = (
                update(ConversationModel)
                .where(ConversationModel.id == conversation_id)
                .values(mode=mode, updated_at=now_beijing())
            )
            session.execute(stmt)
        self._cache_evict(conversation_id)
        return True

    def delete_conversation(self, conversation_id: str) -> bool:
        """删除对话会话及其所有消息。"""
        with self.db_manager.get_session() as session:
            stmt = delete(MessageModel).where(MessageModel.conversation_id == conversation_id)
            session.execute(stmt)
            stmt = delete(ConversationModel).where(ConversationModel.id == conversation_id)
            session.execute(stmt)
        self._cache_evict(conversation_id)
        logger.info(f"对话会话删除成功: id={conversation_id}")
        return True

    def _model_to_entity(
        self, model: ConversationModel, messages: list[MessageEntity]
    ) -> ConversationEntity:
        """将 ORM 模型转换为 ConversationEntity。"""
        return ConversationEntity(
            id=model.id,
            agent_id=model.agent_id,
            title=model.title or "新对话",
            mode=ResponseMode(model.mode),
            messages=messages,
            total_tokens=model.total_tokens or 0,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _msg_model_to_entity(model: MessageModel) -> MessageEntity:
        """将 ORM 模型转换为 MessageEntity。"""
        return MessageEntity(
            id=model.id,
            role=MessageRole(model.role),
            content=model.content or "",
            tokens=model.tokens or 0,
            created_at=model.created_at,
        )

    @staticmethod
    def _cache_get(conversation_id: str) -> Optional[ConversationEntity]:
        with _CONV_CACHE_LOCK:
            return _CONV_CACHE.get(conversation_id)

    @staticmethod
    def _cache_put(conversation_id: str, entity: ConversationEntity) -> None:
        with _CONV_CACHE_LOCK:
            if len(_CONV_CACHE) >= _CONV_CACHE_MAX:
                oldest_key = next(iter(_CONV_CACHE))
                del _CONV_CACHE[oldest_key]
            _CONV_CACHE[conversation_id] = entity

    @staticmethod
    def _cache_evict(conversation_id: str) -> None:
        with _CONV_CACHE_LOCK:
            _CONV_CACHE.pop(conversation_id, None)
