"""Conversation 模型 — 对话（替代 conversations/*.json + _index.json）。

messages 用 JSON 列存储（不拆独立表，避免 delete-reinsert 性能损耗）。
search_text 用于 LIKE 搜索（FTS5 预留扩展点）。
deleted_at 非空表示软删除（回收站）。
chat_mode 标记对话模式（normal/standard/ultra），切换模式需新建对话以隔离上下文。
"""
from typing import Optional

from sqlalchemy import Boolean, Index, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(256), default="New Conversation")
    agent_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    model: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    provider: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    chat_mode: Mapped[Optional[str]] = mapped_column(String(32), default="normal", nullable=True, index=True)
    messages: Mapped[list] = mapped_column(JSON, default=list)
    last_message: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    search_text: Mapped[str] = mapped_column(Text, default="")
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    deleted_at: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[str] = mapped_column(String(64), default="")
    updated_at: Mapped[str] = mapped_column(String(64), default="", index=True)
