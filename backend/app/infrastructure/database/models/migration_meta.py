"""MigrationMeta 模型 — 迁移标记表（幂等用，非行数判断）。

记录每个数据源是否已从 JSON 迁移到 SQLite。
空库也可能已完成迁移，因此不能用行数判断，需用标记表。
"""
from typing import Optional

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class MigrationMeta(Base):
    __tablename__ = "_migration_meta"

    source: Mapped[str] = mapped_column(String(128), primary_key=True)
    migrated_at: Mapped[str] = mapped_column(String(64), default="")
    record_count: Mapped[int] = mapped_column(Integer, default=0)
