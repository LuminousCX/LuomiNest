"""Group 模型 — 群组（替代 groups.json）。

members 用 JSON 列存储（不拆独立表，与 Conversation 设计一致）。
消息已拆至 group_messages 独立表（见 group_message.py）：追加为单行 INSERT，
不再整列 JSON 重写；旧库若仍存在 messages 列，由 engine._migrate_columns_sync
回填到 group_messages 表后 DROP（幂等）。
消息结构：sender_id / sender_type / sender_name / content / role / timestamp。
"""
from typing import Optional

from sqlalchemy import String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    members: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[str] = mapped_column(String(64), default="")
    updated_at: Mapped[str] = mapped_column(String(64), default="", index=True)
