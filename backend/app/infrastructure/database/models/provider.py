"""Provider 模型 — LLM 供应商配置（替代 llm.providers.* 命名空间）。

api_key 由 ProviderRepository 始终加密存储（非可选加密）。
"""
from typing import Optional

from sqlalchemy import Boolean, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class Provider(Base):
    __tablename__ = "providers"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), default="")
    vendor: Mapped[str] = mapped_column(String(64), default="openai_compatible")
    base_url: Mapped[str] = mapped_column(String(512), default="")
    api_key: Mapped[str] = mapped_column(String(1024), default="")
    default_model: Mapped[str] = mapped_column(String(128), default="")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    selected_models: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[str] = mapped_column(String(64), default="")
    updated_at: Mapped[str] = mapped_column(String(64), default="")
