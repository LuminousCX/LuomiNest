"""ProviderCredential 模型 — LLM 供应商凭证（api_key 加密存储）。

- api_key_encrypted: Fernet 密文（复用 get_cipher()，与 config_items 同密钥）
- api_key_prefix: 前6+...+后4 明文，用于前端展示
- api_key_hash: SHA-256 查重，防止同一 key 重复添加
"""
from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class ProviderCredential(Base):
    __tablename__ = "provider_credentials"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider_id: Mapped[str] = mapped_column(String(128), index=True)
    api_key_encrypted: Mapped[str] = mapped_column(Text, default="")
    api_key_prefix: Mapped[str] = mapped_column(String(32), default="")
    api_key_hash: Mapped[str] = mapped_column(String(64), index=True)
    label: Mapped[str] = mapped_column(String(128), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_used_at: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[str] = mapped_column(String(64), default="")
