"""向量嵌入数据模型。

定义向量嵌入（Embedding）的 ORM 模型。
每条 Chunk 对应一个 Embedding，向量以 BLOB 格式存储在 SQLite 中。
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import BLOB, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import DeclarativeBaseModel


class EmbeddingModel(DeclarativeBaseModel):
    """向量嵌入 SQLAlchemy ORM 模型。

    对应数据库表 embeddings，存储 Chunk 的向量表示。
    """

    __tablename__ = "embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chunk_id: Mapped[int] = mapped_column(
        Integer, nullable=False, unique=True, index=True, comment="关联Chunk ID"
    )
    vector: Mapped[bytes] = mapped_column(BLOB, nullable=False, comment="向量数据（BLOB）")

    def __repr__(self) -> str:
        return f"<EmbeddingModel(id={self.id}, chunk_id={self.chunk_id})>"
