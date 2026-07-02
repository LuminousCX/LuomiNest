"""PlatformInstance 模型 — 平台实例（替代 platforms.json）。

config 用 JSON 列存储（含运行时配置、模型配置等）。
"""
from typing import Optional

from sqlalchemy import Boolean, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class PlatformInstance(Base):
    __tablename__ = "platform_instances"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    adapter_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    enable: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    last_sync: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str] = mapped_column(Text, default="")
    icon: Mapped[str] = mapped_column(String(64), default="Globe")
    category: Mapped[str] = mapped_column(String(64), default="general")
    display_name: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[str] = mapped_column(String(64), default="")
    updated_at: Mapped[str] = mapped_column(String(64), default="")
