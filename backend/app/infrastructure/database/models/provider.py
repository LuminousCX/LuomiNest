"""Provider 模型 — LLM 供应商元信息（不含 api_key）。

api_key 已迁移至 provider_credentials 表（加密存储 + 前缀显示 + SHA-256 查重）。
"""
from sqlalchemy import Boolean, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class Provider(Base):
    __tablename__ = "providers"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), default="")
    vendor: Mapped[str] = mapped_column(String(64), default="openai_compatible")
    base_url: Mapped[str] = mapped_column(String(512), default="")
    default_model: Mapped[str] = mapped_column(String(128), default="")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    selected_models: Mapped[list] = mapped_column(JSON, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String(64), default="")
    updated_at: Mapped[str] = mapped_column(String(64), default="")
