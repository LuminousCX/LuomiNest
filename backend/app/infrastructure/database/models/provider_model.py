"""ProviderModel 模型 — 每个供应商下的模型元信息。

用于持久化 /models 接口返回的模型列表，并支持按模型维度配置：
- 是否启用（enabled）
- 最大上下文长度（max_context_tokens，0 表示自动推断）

主键为自增 id；业务唯一性由 (provider_id, model_id) 保证。
"""
from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class ProviderModel(Base):
    __tablename__ = "provider_models"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    model_id: Mapped[str] = mapped_column(String(256), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(256), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    max_context_tokens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String(64), default="")
    updated_at: Mapped[str] = mapped_column(String(64), default="")
