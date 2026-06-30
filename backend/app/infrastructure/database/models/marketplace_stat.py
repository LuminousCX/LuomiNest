"""MarketplaceStat 模型 — 统计计数（替代 marketplace_stats.json）。

download_count / like_count 通过 SQL 原子增 `UPDATE SET count=count+1`
（保留 mutate_async 语义，且并发安全）。
liked_by 存储 liked 该项的用户 ID 列表（JSON）。
"""
from typing import Optional

from sqlalchemy import Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class MarketplaceStat(Base):
    __tablename__ = "marketplace_stats"

    item_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    type: Mapped[str] = mapped_column(String(32), default="", index=True)
    download_count: Mapped[int] = mapped_column(Integer, default=0)
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    liked_by: Mapped[list] = mapped_column(JSON, default=list)
    updated_at: Mapped[str] = mapped_column(String(64), default="")
