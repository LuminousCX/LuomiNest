"""SQLAlchemy 声明式基类。

提供所有 ORM 模型共享的基类，统一管理元数据。
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class DeclarativeBaseModel(DeclarativeBase):
    """SQLAlchemy 声明式基类。"""

    pass
