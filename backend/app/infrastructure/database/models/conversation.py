"""Conversation 模型 — 对话（替代 conversations/*.json + _index.json）。

- 消息已拆至 conversation_messages 独立表（见 conversation_message.py），
  本表仅存对话元数据；search_text 由 repository 在消息写入时增量维护
  （FTS5 预留扩展点）。
- 旧库若仍存在 messages 列，由 engine._migrate_columns 回填到
  conversation_messages 表后 DROP（幂等）。
- deleted_at 非空表示软删除（回收站）。
- chat_mode 标记对话模式（normal/standard/ultra），切换模式需新建对话以隔离上下文。
- domain/scene/user_key 为对话域字段（洋葱架构 §5.2/§12.1）：
  - domain 决定列表隔离边界（workbench | agent:{id} | platform:{instId}，创建后不可变）
  - scene 标记来源（workbench | avatar | platform，默认 workbench）
  - user_key 为远期用户中心记忆池关联键（§8.5：私聊 {Platform}_{User_ID}，群聊为空）
"""
from typing import Optional

from sqlalchemy import Boolean, String, Text
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
    # 对话域（§5.2）：workbench | agent:{id} | platform:{instId}，决定列表隔离边界，创建后不可变
    domain: Mapped[Optional[str]] = mapped_column(String(96), default="", nullable=True, index=True)
    # 来源标记（§5.2）：workbench | avatar | platform，默认 workbench
    scene: Mapped[Optional[str]] = mapped_column(String(32), default="workbench", nullable=True)
    # 远期用户中心记忆池关联键（§8.5）：私聊 {Platform}_{User_ID}，群聊为空
    user_key: Mapped[Optional[str]] = mapped_column(String(128), default="", nullable=True, index=True)
    last_message: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    # 全文检索文本：由 repository 在消息写入时增量拼接（FTS5 预留扩展点）
    search_text: Mapped[str] = mapped_column(Text, default="")
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    deleted_at: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[str] = mapped_column(String(64), default="")
    updated_at: Mapped[str] = mapped_column(String(64), default="", index=True)
