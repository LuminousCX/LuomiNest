"""RepoSource 模型 — 仓库源（替代 repo_sources.json）。

sub_markets 用 JSON 列存储（插件/技能/Agent 子市场列表）。
"""
from typing import Optional

from sqlalchemy import Boolean, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class RepoSource(Base):
    __tablename__ = "repo_sources"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    type: Mapped[str] = mapped_column(String(32), default="", index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    url: Mapped[str] = mapped_column(String(512), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="idle")
    error_message: Mapped[str] = mapped_column(Text, default="")
    last_synced_at: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    sub_markets: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[str] = mapped_column(String(64), default="")
    updated_at: Mapped[str] = mapped_column(String(64), default="")
