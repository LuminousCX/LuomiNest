"""实体知识数据模型。

定义实体知识（Entity）的 ORM 模型和 Pydantic 实体。
Entity 用于语义知识库，从对话中提取的人名、偏好、习惯等
结构化知识，支持计数和最后出现时间追踪。
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


class EntityType(str, Enum):
    """实体类型。"""

    PERSON = "person"
    PREFERENCE = "preference"
    HABIT = "habit"
    FACT = "fact"
    SKILL = "skill"
    LOCATION = "location"
    ORGANIZATION = "organization"
    OTHER = "other"


class EntityModel(DeclarativeBaseModel):
    """实体知识 SQLAlchemy ORM 模型。

    对应数据库表 entities，存储从对话中提取的结构化知识。
    """

    __tablename__ = "entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="实体名称")
    type: Mapped[str] = mapped_column(
        String(50), nullable=False, default=EntityType.OTHER.value, comment="实体类型"
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="实体描述")
    agent_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, comment="所属Agent ID")
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="出现次数")
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), comment="最后出现时间"
    )

    def __repr__(self) -> str:
        return f"<EntityModel(id={self.id}, name='{self.name}', type='{self.type}')>"


class EntityEntity(BaseModel):
    """实体知识实体（Pydantic 模型）。"""

    id: Optional[int] = Field(default=None, description="主键ID")
    name: str = Field(..., min_length=1, max_length=200, description="实体名称")
    type: EntityType = Field(default=EntityType.OTHER, description="实体类型")
    description: Optional[str] = Field(default=None, description="实体描述")
    agent_id: int = Field(..., ge=1, description="所属Agent ID")
    count: int = Field(default=1, ge=1, description="出现次数")
    last_seen_at: datetime = Field(default_factory=now_beijing, description="最后出现时间")

    def to_orm_model(self) -> EntityModel:
        """转换为 SQLAlchemy ORM 模型。"""
        return EntityModel(
            id=self.id,
            name=self.name,
            type=self.type.value,
            description=self.description,
            agent_id=self.agent_id,
            count=self.count,
            last_seen_at=self.last_seen_at,
        )

    @classmethod
    def from_orm_model(cls, orm_model: EntityModel) -> EntityEntity:
        """从 SQLAlchemy ORM 模型创建实体。"""
        return cls(
            id=orm_model.id,
            name=orm_model.name,
            type=EntityType(orm_model.type),
            description=orm_model.description,
            agent_id=orm_model.agent_id,
            count=orm_model.count,
            last_seen_at=orm_model.last_seen_at,
        )
