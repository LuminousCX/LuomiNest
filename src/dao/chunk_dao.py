"""记忆分块数据访问对象。

基于 SQLAlchemy ORM 实现 Chunk 的 CRUD 操作，
以及 FTS5 全文搜索和向量相似度查询。

优化特性：
- 批量查询支持
- 访问计数递增
- 修复 content_hash 唯一约束
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import delete, select, update, text
from sqlalchemy.orm import Session

from src.dao.database import DatabaseManager
from src.exceptions import DaoError, MemoryNotFoundError
from src.model.chunk import ChunkEntity, ChunkModel, ChunkType
from src.utils.logger import get_logger

logger = get_logger()


class ChunkDao:
    """记忆分块 DAO。

    使用 SQLAlchemy ORM 进行数据库操作，
    支持按 agent_id 完全隔离记忆空间。

    Attributes:
        db_manager: 数据库管理器。
    """

    def __init__(self, db_manager: DatabaseManager) -> None:
        self.db_manager = db_manager

    def insert(self, entity: ChunkEntity) -> ChunkEntity:
        """插入记忆分块。

        Args:
            entity: Chunk 实体。

        Returns:
            插入后的 Chunk 实体（含 ID）。
        """
        with self.db_manager.get_session() as session:
            orm_model = entity.to_orm_model()
            session.add(orm_model)
            session.flush()
            result = ChunkEntity.from_orm_model(orm_model)
            logger.debug(f"Chunk 创建成功: id={result.id}, agent_id={result.agent_id}")
            return result

    def delete_by_id(self, chunk_id: int) -> bool:
        """根据 ID 删除记忆分块。

        Args:
            chunk_id: Chunk ID。

        Returns:
            是否删除成功。
        """
        with self.db_manager.get_session() as session:
            stmt = delete(ChunkModel).where(ChunkModel.id == chunk_id)
            session.execute(stmt)
            return True

    def delete_by_agent_id(self, agent_id: int) -> int:
        """删除指定 Agent 的所有记忆分块。

        Args:
            agent_id: Agent ID。

        Returns:
            删除的记录数。
        """
        with self.db_manager.get_session() as session:
            stmt = delete(ChunkModel).where(ChunkModel.agent_id == agent_id)
            result = session.execute(stmt)
            return result.rowcount

    def select_by_id(self, chunk_id: int) -> Optional[ChunkEntity]:
        """根据 ID 查询记忆分块。"""
        with self.db_manager.get_session() as session:
            orm_model = session.get(ChunkModel, chunk_id)
            if orm_model is None:
                return None
            return ChunkEntity.from_orm_model(orm_model)

    def select_by_ids(self, chunk_ids: list[int]) -> list[ChunkEntity]:
        """批量根据 ID 查询记忆分块。"""
        with self.db_manager.get_session() as session:
            stmt = select(ChunkModel).where(ChunkModel.id.in_(chunk_ids))
            results = session.execute(stmt).scalars().all()
            return [ChunkEntity.from_orm_model(m) for m in results]

    def select_by_hash(self, content_hash: str, agent_id: int) -> Optional[ChunkEntity]:
        """根据内容哈希和 Agent ID 查询记忆分块。"""
        with self.db_manager.get_session() as session:
            stmt = select(ChunkModel).where(
                ChunkModel.content_hash == content_hash,
                ChunkModel.agent_id == agent_id,
            )
            result = session.execute(stmt).scalar_one_or_none()
            if result is None:
                return None
            return ChunkEntity.from_orm_model(result)

    def select_by_agent_id(
        self,
        agent_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ChunkEntity]:
        """查询指定 Agent 的所有记忆分块。"""
        with self.db_manager.get_session() as session:
            stmt = (
                select(ChunkModel)
                .where(ChunkModel.agent_id == agent_id, ChunkModel.is_expired == False)
                .order_by(ChunkModel.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            results = session.execute(stmt).scalars().all()
            return [ChunkEntity.from_orm_model(m) for m in results]

    def count_by_agent_id(self, agent_id: int) -> int:
        """统计指定 Agent 的记忆分块数量。"""
        from sqlalchemy import func

        with self.db_manager.get_session() as session:
            stmt = select(func.count(ChunkModel.id)).where(
                ChunkModel.agent_id == agent_id,
                ChunkModel.is_expired == False,
            )
            return session.execute(stmt).scalar() or 0

    def search_bm25(self, agent_id: int, query: str, limit: int = 20) -> list[tuple[int, float]]:
        """使用 FTS5 进行 BM25 全文搜索。

        Args:
            agent_id: Agent ID。
            query: 搜索关键词。
            limit: 返回数量限制。

        Returns:
            (chunk_id, bm25_score) 元组列表。
        """
        sql = text("""
            SELECT c.id, bm25(chunks_fts) AS score
            FROM chunks_fts f
            JOIN chunks c ON c.id = f.rowid
            WHERE chunks_fts MATCH :query
              AND c.agent_id = :agent_id
              AND c.is_expired = 0
            ORDER BY score
            LIMIT :limit
        """)
        with self.db_manager.engine.connect() as conn:
            rows = conn.execute(sql, {
                "query": query,
                "agent_id": agent_id,
                "limit": limit,
            }).fetchall()
            return [(row[0], float(row[1])) for row in rows]

    def update_merge_count(self, chunk_id: int) -> None:
        """增加合并次数。"""
        with self.db_manager.get_session() as session:
            orm_model = session.get(ChunkModel, chunk_id)
            if orm_model is not None:
                orm_model.merge_count += 1

    def update_content(self, chunk_id: int, content: str, content_hash: str) -> None:
        """更新记忆内容和哈希。"""
        with self.db_manager.get_session() as session:
            orm_model = session.get(ChunkModel, chunk_id)
            if orm_model is not None:
                orm_model.content = content
                orm_model.content_hash = content_hash

    def mark_expired(self, chunk_id: int) -> None:
        """标记记忆为已过期。"""
        with self.db_manager.get_session() as session:
            orm_model = session.get(ChunkModel, chunk_id)
            if orm_model is not None:
                orm_model.is_expired = True

    def mark_expired_batch(self, agent_id: int, before_time: datetime) -> int:
        """批量标记过期记忆。"""
        with self.db_manager.get_session() as session:
            stmt = (
                update(ChunkModel)
                .where(
                    ChunkModel.agent_id == agent_id,
                    ChunkModel.created_at < before_time,
                    ChunkModel.is_expired == False,
                )
                .values(is_expired=True)
            )
            result = session.execute(stmt)
            return result.rowcount

    def increment_access_count(self, chunk_id: int) -> None:
        """增加访问次数（用于 AdaMem）。"""
        with self.db_manager.get_session() as session:
            stmt = (
                update(ChunkModel)
                .where(ChunkModel.id == chunk_id)
                .values(access_count=ChunkModel.access_count + 1)
            )
            session.execute(stmt)

    def increment_access_counts(self, chunk_ids: list[int]) -> None:
        """批量增加访问次数。"""
        if not chunk_ids:
            return
        with self.db_manager.get_session() as session:
            stmt = (
                update(ChunkModel)
                .where(ChunkModel.id.in_(chunk_ids))
                .values(access_count=ChunkModel.access_count + 1)
            )
            session.execute(stmt)

    def get_created_times(self, chunk_ids: list[int]) -> dict[int, datetime]:
        """批量获取创建时间。"""
        with self.db_manager.get_session() as session:
            stmt = select(ChunkModel.id, ChunkModel.created_at).where(
                ChunkModel.id.in_(chunk_ids)
            )
            rows = session.execute(stmt).all()
            return {row[0]: row[1] for row in rows}

    def get_chunk_stats(self, chunk_ids: list[int]) -> dict[int, dict]:
        """批量获取记忆统计信息（用于 AdaMem）。"""
        with self.db_manager.get_session() as session:
            stmt = select(
                ChunkModel.id,
                ChunkModel.merge_count,
                ChunkModel.access_count,
                ChunkModel.confidence,
            ).where(ChunkModel.id.in_(chunk_ids))
            rows = session.execute(stmt).all()
            return {
                row[0]: {
                    "merge_count": row[1],
                    "access_count": row[2],
                    "confidence": row[3],
                }
                for row in rows
            }
