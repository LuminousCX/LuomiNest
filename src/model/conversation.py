"""对话记录数据模型。

定义对话消息、对话会话等实体。
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import DeclarativeBaseModel
from src.utils.datetime_utils import now_beijing
from src.utils.string_utils import generate_id


class MessageRole(str, Enum):
    """消息角色类型。"""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class ResponseMode(str, Enum):
    """响应模式。"""

    EXPERT = "expert"
    FAST = "fast"


class ConversationModel(DeclarativeBaseModel):
    """对话会话 SQLAlchemy ORM 模型。"""

    __tablename__ = "conversation"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, comment="会话唯一标识")
    agent_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="关联Agent ID")
    title: Mapped[str] = mapped_column(String(100), nullable=False, default="新对话", comment="会话标题")
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="fast", comment="响应模式")
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="总消耗token数")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )

    def __repr__(self) -> str:
        return f"<ConversationModel(id={self.id}, agent_id={self.agent_id})>"


class MessageModel(DeclarativeBaseModel):
    """对话消息 SQLAlchemy ORM 模型。"""

    __tablename__ = "message"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, comment="消息唯一标识")
    conversation_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, comment="关联会话ID"
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False, comment="消息角色")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="消息内容")
    tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="消耗token数")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), comment="创建时间"
    )

    def __repr__(self) -> str:
        return f"<MessageModel(id={self.id}, role={self.role})>"


class MessageEntity(BaseModel):
    """单条对话消息实体。

    Attributes:
        id: 消息唯一标识。
        role: 消息角色（system/user/assistant）。
        content: 消息内容。
        tokens: 消息消耗的 token 数。
        created_at: 创建时间。
    """

    id: str = Field(default_factory=generate_id, description="消息唯一标识")
    role: MessageRole = Field(..., description="消息角色")
    content: str = Field(default="", description="消息内容")
    tokens: int = Field(default=0, ge=0, description="消息消耗的 token 数")
    created_at: datetime = Field(default_factory=now_beijing, description="创建时间")

    def to_openai_format(self) -> dict[str, str]:
        """转换为 OpenAI API 消息格式。"""
        return {"role": self.role.value, "content": self.content}

    def to_storage_dict(self) -> dict:
        """转换为存储用的字典。"""
        data = self.model_dump()
        data["created_at"] = self.created_at.isoformat()
        return data

    @classmethod
    def from_storage_dict(cls, data: dict) -> MessageEntity:
        """从存储字典创建实体。"""
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        return cls(**data)


class ConversationEntity(BaseModel):
    """对话会话实体。

    Attributes:
        id: 会话唯一标识。
        agent_id: 关联的 Agent 角色ID。
        title: 会话标题。
        mode: 响应模式（专家/快速）。
        messages: 消息列表。
        total_tokens: 总消耗 token 数。
        created_at: 创建时间。
        updated_at: 更新时间。
    """

    id: str = Field(default_factory=generate_id, description="会话唯一标识")
    agent_id: str = Field(..., description="关联的 Agent 角色ID")
    title: str = Field(default="新对话", max_length=100, description="会话标题")
    mode: ResponseMode = Field(default=ResponseMode.FAST, description="响应模式")
    messages: list[MessageEntity] = Field(default_factory=list, description="消息列表")
    total_tokens: int = Field(default=0, ge=0, description="总消耗 token 数")
    created_at: datetime = Field(default_factory=now_beijing, description="创建时间")
    updated_at: datetime = Field(default_factory=now_beijing, description="更新时间")

    def add_message(self, role: MessageRole, content: str, tokens: int = 0) -> MessageEntity:
        """添加一条消息到会话。

        Args:
            role: 消息角色。
            content: 消息内容。
            tokens: 消息消耗的 token 数。

        Returns:
            新创建的消息实体。
        """
        message = MessageEntity(
            role=role,
            content=content,
            tokens=tokens,
        )
        self.messages.append(message)
        self.total_tokens += tokens
        self.update_timestamp()
        return message

    def get_openai_messages(self, max_messages: int = 50) -> list[dict[str, str]]:
        """获取 OpenAI 格式的消息列表（用于模型调用）。

        Args:
            max_messages: 最大消息数量，超出时截断早期消息。

        Returns:
            OpenAI 格式消息列表。
        """
        recent = self.messages[-max_messages:] if len(self.messages) > max_messages else self.messages
        return [msg.to_openai_format() for msg in recent]

    def get_last_user_message(self) -> Optional[MessageEntity]:
        """获取最后一条用户消息。"""
        for msg in reversed(self.messages):
            if msg.role == MessageRole.USER:
                return msg
        return None

    def update_timestamp(self) -> None:
        """更新修改时间戳。"""
        self.updated_at = now_beijing()

    def to_storage_dict(self) -> dict:
        """转换为存储用的字典。"""
        data = self.model_dump()
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        data["messages"] = [msg.to_storage_dict() for msg in self.messages]
        return data

    @classmethod
    def from_storage_dict(cls, data: dict) -> ConversationEntity:
        """从存储字典创建实体。"""
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if isinstance(data.get("updated_at"), str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        if "messages" in data and isinstance(data["messages"], list):
            data["messages"] = [
                MessageEntity.from_storage_dict(msg) if isinstance(msg, dict) else msg
                for msg in data["messages"]
            ]
        return cls(**data)
