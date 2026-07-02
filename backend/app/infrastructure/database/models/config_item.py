"""ConfigItem 模型 — 统一 KV 配置存储（替代 user_config.json）。

替代 LumiConfigStore 的 flat KV 结构：
- key: 配置键（如 "llm.providers.openai.api_key"）
- value: JSON 序列化的值
- value_type: 值类型标记，便于反序列化
- encrypted: 是否加密存储（由 Repository 按 fnmatch 模式判定）

main_agent.json 与 model_config.json 也折叠到本表的命名空间下。
"""
from typing import Any

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class ConfigItem(Base):
    __tablename__ = "config_items"

    key: Mapped[str] = mapped_column(String(256), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    value_type: Mapped[str] = mapped_column(String(16), default="str")
    encrypted: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[str] = mapped_column(String(64), default="")
