"""记忆系统单元测试。

测试记忆系统的核心功能：
- 记忆写入与检索
- 精确去重与模糊合并
- 按Agent隔离记忆空间
- 召回引擎流水线
- 实体知识提取
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta

import numpy as np

from src.dao.database import DatabaseManager
from src.dao.chunk_dao import ChunkDao
from src.dao.embedding_dao import EmbeddingDao
from src.dao.entity_dao import EntityDao
from src.model.chunk import ChunkEntity, ChunkType
from src.model.entity import EntityEntity, EntityType
from src.service.memory_service import MemoryService, _compute_content_hash
from src.utils.recall_engine import (
    blob_to_vector,
    vector_to_blob,
    rrf_fusion,
    mmr_rerank,
    apply_time_decay,
    compute_adaptive_memory_score,
)
from src.utils.datetime_utils import now_beijing


class TestVectorConversion:
    """向量与 BLOB 互转测试。"""

    def test_vector_to_blob_and_back(self) -> None:
        vector = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32)
        blob = vector_to_blob(vector)
        restored = blob_to_vector(blob)
        assert np.allclose(vector, restored)

    def test_empty_vector(self) -> None:
        vector = np.array([], dtype=np.float32)
        blob = vector_to_blob(vector)
        restored = blob_to_vector(blob)
        assert len(restored) == 0


class TestRRFFusion:
    """RRF 融合算法测试。"""

    def test_basic_fusion(self) -> None:
        bm25 = [(1, -5.0), (2, -3.0), (3, -1.0)]
        vector = [(2, 0.9), (3, 0.8), (4, 0.7)]
        result = rrf_fusion(bm25, vector, k=60)
        assert 1 in result
        assert 2 in result
        assert 3 in result
        assert 4 in result

    def test_empty_inputs(self) -> None:
        result = rrf_fusion([], [])
        assert result == {}

    def test_single_list(self) -> None:
        bm25 = [(1, -5.0)]
        result = rrf_fusion(bm25, [], k=60)
        assert 1 in result


class TestMMRRerank:
    """MMR 重排序测试。"""

    def test_basic_rerank(self) -> None:
        candidates = [(1, 0.9), (2, 0.8), (3, 0.7)]
        query_vec = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        embeddings = {
            1: np.array([1.0, 0.0, 0.0], dtype=np.float32),
            2: np.array([0.9, 0.1, 0.0], dtype=np.float32),
            3: np.array([0.0, 1.0, 0.0], dtype=np.float32),
        }
        result = mmr_rerank(candidates, embeddings, query_vec, lambda_param=0.5, top_k=3)
        assert len(result) <= 3
        assert all(isinstance(r, tuple) and len(r) == 2 for r in result)

    def test_empty_candidates(self) -> None:
        result = mmr_rerank([], {}, np.zeros(3, dtype=np.float32))
        assert result == []


class TestTimeDecay:
    """时间衰减测试。"""

    def test_recent_memory_higher_score(self) -> None:
        now = now_beijing()
        recent_id = 1
        old_id = 2
        scores = {recent_id: 1.0, old_id: 1.0}
        times = {
            recent_id: now - timedelta(hours=1),
            old_id: now - timedelta(days=60),
        }
        result = apply_time_decay(scores, times, half_life_days=30.0)
        assert result[recent_id] > result[old_id]

    def test_missing_time_no_decay(self) -> None:
        scores = {1: 1.0}
        result = apply_time_decay(scores, {}, half_life_days=30.0)
        assert result[1] == 1.0


class TestAdaptiveMemoryScore:
    """自适应记忆优先级测试。"""

    def test_high_confidence_higher_score(self) -> None:
        low = compute_adaptive_memory_score(1, 0.5, 0.3, 0, 0)
        high = compute_adaptive_memory_score(2, 0.5, 0.9, 0, 0)
        assert high > low

    def test_merge_count_effect(self) -> None:
        no_merge = compute_adaptive_memory_score(1, 0.5, 0.5, 0, 0)
        merged = compute_adaptive_memory_score(2, 0.5, 0.5, 5, 0)
        assert merged > no_merge


class TestContentHash:
    """内容哈希测试。"""

    def test_same_content_same_hash(self) -> None:
        h1 = _compute_content_hash("hello", 1)
        h2 = _compute_content_hash("hello", 1)
        assert h1 == h2

    def test_different_agent_different_hash(self) -> None:
        h1 = _compute_content_hash("hello", 1)
        h2 = _compute_content_hash("hello", 2)
        assert h1 != h2

    def test_different_content_different_hash(self) -> None:
        h1 = _compute_content_hash("hello", 1)
        h2 = _compute_content_hash("world", 1)
        assert h1 != h2


class TestDatabaseManager:
    """数据库管理器测试。"""

    def setup_method(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "test_memory.db")
        self.db_manager = DatabaseManager(self.db_path)

    def test_tables_created(self) -> None:
        with self.db_manager.engine.connect() as conn:
            from sqlalchemy import text
            tables = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )).fetchall()
            table_names = [t[0] for t in tables]
            assert "chunks" in table_names
            assert "embeddings" in table_names
            assert "entities" in table_names

    def test_fts5_created(self) -> None:
        with self.db_manager.engine.connect() as conn:
            from sqlalchemy import text
            tables = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='chunks_fts'"
            )).fetchall()
            assert len(tables) > 0


class TestChunkDao:
    """Chunk DAO 测试。"""

    def setup_method(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "test_chunk.db")
        self.db_manager = DatabaseManager(self.db_path)
        self.chunk_dao = ChunkDao(self.db_manager)

    def test_insert_and_select(self) -> None:
        entity = ChunkEntity(
            content="测试记忆内容",
            content_hash=_compute_content_hash("测试记忆内容", 1),
            chunk_type=ChunkType.CONVERSATION,
            agent_id=1,
        )
        saved = self.chunk_dao.insert(entity)
        assert saved.id is not None
        assert saved.content == "测试记忆内容"

        found = self.chunk_dao.select_by_id(saved.id)
        assert found is not None
        assert found.content == "测试记忆内容"

    def test_select_by_hash(self) -> None:
        content = "哈希测试"
        entity = ChunkEntity(
            content=content,
            content_hash=_compute_content_hash(content, 1),
            chunk_type=ChunkType.CONVERSATION,
            agent_id=1,
        )
        self.chunk_dao.insert(entity)

        found = self.chunk_dao.select_by_hash(
            _compute_content_hash(content, 1), 1
        )
        assert found is not None
        assert found.content == content

    def test_agent_isolation(self) -> None:
        for agent_id in [1, 2]:
            for i in range(3):
                entity = ChunkEntity(
                    content=f"Agent{agent_id}记忆{i}",
                    content_hash=_compute_content_hash(f"Agent{agent_id}记忆{i}", agent_id),
                    chunk_type=ChunkType.CONVERSATION,
                    agent_id=agent_id,
                )
                self.chunk_dao.insert(entity)

        agent1_chunks = self.chunk_dao.select_by_agent_id(1)
        agent2_chunks = self.chunk_dao.select_by_agent_id(2)
        assert len(agent1_chunks) == 3
        assert len(agent2_chunks) == 3

    def test_delete_by_agent_id(self) -> None:
        for i in range(3):
            entity = ChunkEntity(
                content=f"记忆{i}",
                content_hash=_compute_content_hash(f"记忆{i}", 1),
                chunk_type=ChunkType.CONVERSATION,
                agent_id=1,
            )
            self.chunk_dao.insert(entity)

        deleted = self.chunk_dao.delete_by_agent_id(1)
        assert deleted == 3


class TestEmbeddingDao:
    """Embedding DAO 测试。"""

    def setup_method(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "test_embedding.db")
        self.db_manager = DatabaseManager(self.db_path)
        self.chunk_dao = ChunkDao(self.db_manager)
        self.embedding_dao = EmbeddingDao(self.db_manager)

    def _create_chunk(self, content: str = "测试") -> int:
        entity = ChunkEntity(
            content=content,
            content_hash=_compute_content_hash(content, 1),
            chunk_type=ChunkType.CONVERSATION,
            agent_id=1,
        )
        saved = self.chunk_dao.insert(entity)
        return saved.id

    def test_insert_and_get_vector(self) -> None:
        chunk_id = self._create_chunk()
        vector = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        self.embedding_dao.insert(chunk_id, vector)

        restored = self.embedding_dao.get_vector_by_chunk_id(chunk_id)
        assert restored is not None
        assert np.allclose(vector, restored)

    def test_upsert(self) -> None:
        chunk_id = self._create_chunk()
        v1 = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        v2 = np.array([0.4, 0.5, 0.6], dtype=np.float32)

        self.embedding_dao.upsert(chunk_id, v1)
        self.embedding_dao.upsert(chunk_id, v2)

        restored = self.embedding_dao.get_vector_by_chunk_id(chunk_id)
        assert restored is not None
        assert np.allclose(v2, restored)


class TestEntityDao:
    """Entity DAO 测试。"""

    def setup_method(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "test_entity.db")
        self.db_manager = DatabaseManager(self.db_path)
        self.entity_dao = EntityDao(self.db_manager)

    def test_insert_and_select(self) -> None:
        entity = EntityEntity(
            name="Python",
            type=EntityType.SKILL,
            description="用户精通Python编程",
            agent_id=1,
        )
        saved = self.entity_dao.insert(entity)
        assert saved.id is not None

        found = self.entity_dao.select_by_id(saved.id)
        assert found is not None
        assert found.name == "Python"

    def test_upsert_by_name(self) -> None:
        entity1 = EntityEntity(
            name="Python",
            type=EntityType.SKILL,
            description="用户会Python",
            agent_id=1,
        )
        self.entity_dao.upsert_by_name(entity1)

        entity2 = EntityEntity(
            name="Python",
            type=EntityType.SKILL,
            description="用户精通Python",
            agent_id=1,
        )
        self.entity_dao.upsert_by_name(entity2)

        found = self.entity_dao.select_by_name("Python", 1, EntityType.SKILL)
        assert found is not None
        assert found.count == 2
        assert "精通" in found.description


class TestMemoryService:
    """记忆服务集成测试。

    使用 Mock 替代真实嵌入模型，避免下载模型导致测试超时。
    """

    def setup_method(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "test_service.db")
        self.db_manager = DatabaseManager(self.db_path)
        self.memory_service = MemoryService(self.db_manager)
        self._patch_embedding()

    def _patch_embedding(self) -> None:
        """用 Mock 替换全局嵌入工具。"""
        from unittest.mock import MagicMock
        from src.utils import embedding_util

        mock_util = MagicMock()
        mock_util.dimension = 384
        mock_util.encode.side_effect = lambda text: np.random.randn(384).astype(np.float32)
        mock_util.encode_batch.side_effect = lambda texts: np.random.randn(len(texts), 384).astype(np.float32)
        embedding_util._embedding_service = mock_util

    def test_memorize_and_retrieve(self) -> None:
        self.memory_service.memorize(
            agent_id=1,
            user_msg="我喜欢Python编程",
            assistant_msg="Python是一门很棒的语言！",
        )

        results = self.memory_service.retrieve(
            agent_id=1,
            query="编程语言",
            top_k=5,
        )
        assert isinstance(results, list)

    def test_agent_isolation(self) -> None:
        self.memory_service.memorize(1, "Agent1记忆", "回复1")
        self.memory_service.memorize(2, "Agent2记忆", "回复2")

        count1 = self.memory_service.count_memories(1)
        count2 = self.memory_service.count_memories(2)
        assert count1 >= 1
        assert count2 >= 1

    def test_clear_memories(self) -> None:
        self.memory_service.memorize(1, "测试记忆", "测试回复")
        deleted_chunks, deleted_entities = self.memory_service.clear(1)
        assert deleted_chunks >= 0

    def test_delete_memory(self) -> None:
        self.memory_service.memorize(1, "待删除记忆", "待删除回复")
        chunks = self.memory_service.get_memories_by_agent(1)
        if chunks:
            self.memory_service.delete_memory(chunks[0].id)
            found = self.memory_service.chunk_dao.select_by_id(chunks[0].id)
            assert found is None


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
