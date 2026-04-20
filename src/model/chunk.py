"""记忆分块数据模型。

定义记忆分块（Chunk）的 ORM 模型、Pydantic 实体和枚举类型。
Chunk 是记忆系统的核心存储单元，每条对话、段落、代码块等
都作为一个独立的 Chunk 存储，并关联到特定 Agent。
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import DeclarativeBaseModel
from src.utils.datetime_utils import now_beijing


class ChunkType(str, Enum):
    """记忆分块类型。"""

    PARAGRAPH = "paragraph"
    CONVERSATION = "conversation"
    CODE_BLOCK = "code_block"
    COMMAND = "command"
    ERROR = "error"
    SUMMARY = "summary"
    KNOWLEDGE = "knowledge"


class ChunkModel(DeclarativeBaseModel):
    """记忆分块 SQLAlchemy ORM 模型。

    对应数据库表 chunks，存储每条记忆的结构化数据。
    """

    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="记忆内容")
    content_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="内容哈希（SHA256）"
    )
    chunk_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ChunkType.CONVERSATION.value,
        comment="分块类型"
    )
    agent_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, comment="所属Agent ID")
    parent_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="父记忆ID（用于Q-A对关联）"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )
    event_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="事件发生时间（TSM）"
    )
    merge_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="合并次数"
    )
    access_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="访问次数（AdaMem）"
    )
    metadata_: Mapped[Optional[dict[str, Any]]] = mapped_column(
        "metadata", JSON, nullable=True, comment="扩展元数据"
    )
    confidence: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0, comment="置信度"
    )
    is_expired: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="是否已过期"
    )

    __table_args__ = (
        UniqueConstraint('content_hash', 'agent_id', name='uq_content_hash_agent_id'),
    )

    def __repr__(self) -> str:
        return f"<ChunkModel(id={self.id}, agent_id={self.agent_id}, type='{self.chunk_type}')>"


class ChunkEntity(BaseModel):
    """记忆分块实体（Pydantic 模型）。

    用于业务逻辑层和 API 层的数据传输。
    """

    id: Optional[int] = Field(default=None, description="主键ID")
    content: str = Field(..., min_length=1, description="记忆内容")
    content_hash: str = Field(default="", description="内容哈希")
    chunk_type: ChunkType = Field(default=ChunkType.CONVERSATION, description="分块类型")
    agent_id: int = Field(..., ge=1, description="所属Agent ID")
    parent_id: Optional[int] = Field(default=None, description="父记忆ID")
    created_at: datetime = Field(default_factory=now_beijing, description="创建时间")
    updated_at: datetime = Field(default_factory=now_beijing, description="更新时间")
    event_time: Optional[datetime] = Field(default=None, description="事件发生时间")
    merge_count: int = Field(default=0, ge=0, description="合并次数")
    access_count: int = Field(default=0, ge=0, description="访问次数")
    metadata_: Optional[dict[str, Any]] = Field(default=None, description="扩展元数据")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="置信度")
    is_expired: bool = Field(default=False, description="是否已过期")

    def to_orm_model(self) -> ChunkModel:
        """转换为 SQLAlchemy ORM 模型。"""
        return ChunkModel(
            id=self.id,
            content=self.content,
            content_hash=self.content_hash,
            chunk_type=self.chunk_type.value,
            agent_id=self.agent_id,
            parent_id=self.parent_id,
            created_at=self.created_at,
            updated_at=self.updated_at,
            event_time=self.event_time,
            merge_count=self.merge_count,
            access_count=self.access_count,
            metadata_=self.metadata_,
            confidence=self.confidence,
            is_expired=self.is_expired,
        )

    @classmethod
    def from_orm_model(cls, orm_model: ChunkModel) -> ChunkEntity:
        """从 SQLAlchemy ORM 模型创建实体。"""
        metadata_value = getattr(orm_model, "metadata_", None)
        if metadata_value is None:
            raw_meta = getattr(orm_model, "__dict__", {}).get("metadata")
            metadata_value = raw_meta if isinstance(raw_meta, dict) else None

        return cls(
            id=orm_model.id,
            content=orm_model.content,
            content_hash=orm_model.content_hash,
            chunk_type=ChunkType(orm_model.chunk_type),
            agent_id=orm_model.agent_id,
            parent_id=orm_model.parent_id,
            created_at=orm_model.created_at,
            updated_at=orm_model.updated_at,
            event_time=orm_model.event_time,
            merge_count=orm_model.merge_count,
            access_count=orm_model.access_count,
            metadata_=metadata_value,
            confidence=orm_model.confidence,
            is_expired=orm_model.is_expired,
        )
