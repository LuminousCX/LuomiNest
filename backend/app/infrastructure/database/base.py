"""SQLAlchemy 2.0 声明式基类。

所有 ORM 模型继承自 `Base`，通过 `Base.metadata` 统一管理建表。
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """ORM 声明式基类，所有模型继承自此。"""
    pass
