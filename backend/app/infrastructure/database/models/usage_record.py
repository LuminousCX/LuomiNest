"""UsageRecord 模型 — LLM 用量记录（替代 usage_records.json 的 10000-cap FIFO）。

SQL 天然支持无上限存储；聚合统计由 SQL GROUP BY 完成（替代 Python 全表扫描）。
"""
from typing import Optional

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class UsageRecord(Base):
    __tablename__ = "usage_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[str] = mapped_column(String(64), index=True)
    provider: Mapped[str] = mapped_column(String(128), default="", index=True)
    model: Mapped[str] = mapped_column(String(128), default="")
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    agent_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    conv_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_stream: Mapped[bool] = mapped_column(Boolean, default=False)
