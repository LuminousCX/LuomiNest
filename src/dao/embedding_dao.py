"""向量嵌入数据访问对象。

基于 SQLAlchemy ORM 实现 Embedding 的 CRUD 操作，
支持向量 BLOB 存储和余弦相似度查询。

优化特性：
- 批量查询支持
- 内存向量矩阵缓存（LRU 策略）
- 批量余弦相似度计算
"""

from __future__ import annotations

from typing import Optional

import numpy as np
from sqlalchemy import delete, select, text

from src.dao.database import DatabaseManager
from src.model.embedding import EmbeddingModel
from src.utils.logger import get_logger
from src.utils.recall_engine import blob_to_vector, vector_to_blob

logger = get_logger()


class EmbeddingDao:
    """向量嵌入 DAO。

    使用 SQLAlchemy ORM 进行数据库操作，
    向量以 BLOB 格式存储，支持余弦相似度查询。

    Attributes:
        db_manager: 数据库管理器。
    """

    def __init__(self, db_manager: DatabaseManager) -> None:
        self.db_manager = db_manager
        self._vector_cache: dict[int, np.ndarray] = {}
        self._cache_maxsize = 10000

    def insert(self, chunk_id: int, vector: np.ndarray) -> int:
        """插入向量嵌入。

        Args:
            chunk_id: 关联的 Chunk ID。
            vector: 向量数据（numpy 数组）。

        Returns:
            插入后的 Embedding ID。
        """
        blob_data = vector_to_blob(vector)
        with self.db_manager.get_session() as session:
            model = EmbeddingModel(chunk_id=chunk_id, vector=blob_data)
            session.add(model)
            session.flush()
            emb_id = model.id
            self._cache_vector(chunk_id, vector)
            logger.debug(f"Embedding 创建成功: id={emb_id}, chunk_id={chunk_id}")
            return emb_id

    def upsert(self, chunk_id: int, vector: np.ndarray) -> int:
        """插入或更新向量嵌入。

        Args:
            chunk_id: 关联的 Chunk ID。
            vector: 向量数据。

        Returns:
            Embedding ID。
        """
        existing_id = self._get_id_by_chunk_id(chunk_id)
        if existing_id is not None:
            self.update_by_chunk_id(chunk_id, vector)
            return existing_id
        return self.insert(chunk_id, vector)

    def _get_id_by_chunk_id(self, chunk_id: int) -> Optional[int]:
        """根据 Chunk ID 查询 Embedding ID。"""
        with self.db_manager.get_session() as session:
            stmt = select(EmbeddingModel.id).where(EmbeddingModel.chunk_id == chunk_id)
            result = session.execute(stmt).scalar_one_or_none()
            return result

    def select_by_chunk_id(self, chunk_id: int) -> Optional[EmbeddingModel]:
        """根据 Chunk ID 查询向量嵌入模型。"""
        with self.db_manager.get_session() as session:
            stmt = select(EmbeddingModel).where(EmbeddingModel.chunk_id == chunk_id)
            model = session.execute(stmt).scalar_one_or_none()
            if model is None:
                return None
            session.expunge(model)
            return model

    def get_vector_by_chunk_id(self, chunk_id: int) -> Optional[np.ndarray]:
        """根据 Chunk ID 获取向量数据。"""
        if chunk_id in self._vector_cache:
            return self._vector_cache[chunk_id].copy()

        with self.db_manager.get_session() as session:
            stmt = select(EmbeddingModel.vector).where(
                EmbeddingModel.chunk_id == chunk_id
            )
            row = session.execute(stmt).scalar_one_or_none()
            if row is None:
                return None
            vector = blob_to_vector(row)
            self._cache_vector(chunk_id, vector)
            return vector

    def get_vectors_by_chunk_ids(self, chunk_ids: list[int]) -> dict[int, np.ndarray]:
        """批量获取向量数据。

        Args:
            chunk_ids: Chunk ID 列表。

        Returns:
            {chunk_id: vector} 字典。
        """
        result: dict[int, np.ndarray] = {}
        uncached_ids: list[int] = []

        for chunk_id in chunk_ids:
            if chunk_id in self._vector_cache:
                result[chunk_id] = self._vector_cache[chunk_id].copy()
            else:
                uncached_ids.append(chunk_id)

        if uncached_ids:
            with self.db_manager.get_session() as session:
                stmt = select(EmbeddingModel.chunk_id, EmbeddingModel.vector).where(
                    EmbeddingModel.chunk_id.in_(uncached_ids)
                )
                rows = session.execute(stmt).all()
                for chunk_id, blob in rows:
                    vector = blob_to_vector(blob)
                    result[chunk_id] = vector
                    self._cache_vector(chunk_id, vector)

        return result

    def _cache_vector(self, chunk_id: int, vector: np.ndarray) -> None:
        """缓存向量数据。"""
        if len(self._vector_cache) >= self._cache_maxsize:
            oldest_id = next(iter(self._vector_cache))
            del self._vector_cache[oldest_id]
        self._vector_cache[chunk_id] = vector.copy()

    def update_by_chunk_id(self, chunk_id: int, vector: np.ndarray) -> None:
        """根据 Chunk ID 更新向量数据。"""
        blob_data = vector_to_blob(vector)
        with self.db_manager.get_session() as session:
            stmt = select(EmbeddingModel).where(EmbeddingModel.chunk_id == chunk_id)
            model = session.execute(stmt).scalar_one_or_none()
            if model is not None:
                model.vector = blob_data
                self._cache_vector(chunk_id, vector)

    def delete_by_chunk_id(self, chunk_id: int) -> bool:
        """根据 Chunk ID 删除向量嵌入。"""
        with self.db_manager.get_session() as session:
            stmt = delete(EmbeddingModel).where(EmbeddingModel.chunk_id == chunk_id)
            session.execute(stmt)
            if chunk_id in self._vector_cache:
                del self._vector_cache[chunk_id]
            return True

    def delete_by_agent_id(self, agent_id: int) -> int:
        """删除指定 Agent 的所有向量嵌入。"""
        with self.db_manager.engine.begin() as conn:
            chunk_ids = conn.execute(text(
                "SELECT id FROM chunks WHERE agent_id = :agent_id"
            ), {"agent_id": agent_id}).scalars().all()

            sql = text("""
                DELETE FROM embeddings
                WHERE chunk_id IN (
                    SELECT id FROM chunks WHERE agent_id = :agent_id
                )
            """)
            result = conn.execute(sql, {"agent_id": agent_id})
            deleted_count = result.rowcount

            for chunk_id in chunk_ids:
                if chunk_id in self._vector_cache:
                    del self._vector_cache[chunk_id]
            return deleted_count

    def search_cosine_similarity(
        self,
        agent_id: int,
        query_vector: np.ndarray,
        limit: int = 20,
        batch_size: int = 1000,
    ) -> list[tuple[int, float]]:
        """使用余弦相似度搜索向量（批量优化）。

        优化策略：
        1. 按 batch_size 分批加载向量
        2. 批量计算余弦相似度
        3. 排序后返回 Top-N

        Args:
            agent_id: Agent ID。
            query_vector: 查询向量。
            limit: 返回数量限制。
            batch_size: 批量加载大小。

        Returns:
            (chunk_id, cosine_similarity) 元组列表，按相似度降序排列。
        """
        query_norm = np.linalg.norm(query_vector)
        if query_norm < 1e-10:
            return []

        sql = text("""
            SELECT e.chunk_id, e.vector
            FROM embeddings e
            JOIN chunks c ON c.id = e.chunk_id
            WHERE c.agent_id = :agent_id
              AND c.is_expired = 0
        """)

        results: list[tuple[int, float]] = []
        with self.db_manager.engine.connect() as conn:
            for batch in self._batch_query(conn, sql, {"agent_id": agent_id}, batch_size):
                batch_ids = []
                batch_vectors = []
                for chunk_id, blob in batch:
                    if chunk_id in self._vector_cache:
                        vector = self._vector_cache[chunk_id]
                    else:
                        vector = blob_to_vector(blob)
                        self._cache_vector(chunk_id, vector)
                    batch_ids.append(chunk_id)
                    batch_vectors.append(vector)

                if batch_vectors:
                    # 批量计算余弦相似度
                    vectors_array = np.stack(batch_vectors)
                    similarities = self._batch_cosine_similarity(vectors_array, query_vector, query_norm)
                    for chunk_id, sim in zip(batch_ids, similarities):
                        results.append((chunk_id, float(sim)))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    def _batch_query(self, conn, sql, params, batch_size):
        """分批执行查询。"""
        result = conn.execute(sql, params)
        while True:
            batch = result.fetchmany(batch_size)
            if not batch:
                break
            yield batch

    def _batch_cosine_similarity(
        self, vectors: np.ndarray, query_vector: np.ndarray, query_norm: float
    ) -> np.ndarray:
        """批量计算余弦相似度。

        Args:
            vectors: (N, D) 向量矩阵。
            query_vector: (D,) 查询向量。
            query_norm: 查询向量的范数。

        Returns:
            (N,) 相似度数组。
        """
        vectors_norm = np.linalg.norm(vectors, axis=1, keepdims=True)
        mask = vectors_norm > 1e-10
        similarities = np.zeros(vectors.shape[0], dtype=np.float32)
        similarities[mask.flatten()] = np.dot(vectors[mask.flatten()], query_vector) / (vectors_norm[mask] * query_norm).flatten()
        return similarities

    def clear_cache(self) -> None:
        """清空向量缓存。"""
        self._vector_cache.clear()
        logger.debug("向量缓存已清空")
