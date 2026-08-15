"""Agent 模型 — 智能体配置（替代 agents.json）。

主 Agent（is_main=True）与普通 Agent 共用本表。
"""
from typing import Optional

from sqlalchemy import Boolean, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants.colors import DEFAULT_AGENT_COLOR
from app.infrastructure.database.base import Base


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    model: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    provider: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    color: Mapped[str] = mapped_column(String(32), default=DEFAULT_AGENT_COLOR)
    avatar: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    capabilities: Mapped[list] = mapped_column(JSON, default=list)
    memory_access: Mapped[str] = mapped_column(String(32), default="none")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_main: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[str] = mapped_column(String(64), default="")
    updated_at: Mapped[str] = mapped_column(String(64), default="")
