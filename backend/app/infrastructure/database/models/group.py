"""Group 模型 — 群组（替代 groups.json）。

members 与 messages 用 JSON 列存储（不拆独立表，与 Conversation 设计一致）。
群聊消息结构：sender_id / sender_type / sender_name / content / role / timestamp。
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
    messages: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[str] = mapped_column(String(64), default="")
    updated_at: Mapped[str] = mapped_column(String(64), default="", index=True)
