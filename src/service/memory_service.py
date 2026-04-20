"""双层记忆系统服务。

基于 MemOS + Memary 混合架构实现：
- 情景记忆流（MemoryStream）：记录每一条对话的原始内容
- 语义知识库（EntityKnowledgeStore）：从对话中提取实体、偏好、习惯

核心接口：
- memorize(agent_id, user_msg, assistant_msg): 写入记忆
- retrieve(agent_id, query, top_k): 检索记忆
- clear(agent_id): 清空指定 Agent 的所有记忆
- delete_memory(memory_id): 删除单条记忆

优化特性：
- 原子操作 + 事务一致性保障
- 对话轮关联存储（Q-A 对绑定 parent_id）
- LLM 驱动的实体提取（GPT-3.5/4 自动 NER）
- 记忆 Token 预算管理
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Optional

import numpy as np

from src.config.settings import get_settings
from src.dao.chunk_dao import ChunkDao
from src.dao.database import DatabaseManager
from src.dao.embedding_dao import EmbeddingDao
from src.dao.entity_dao import EntityDao
from src.exceptions import MemoryNotFoundError, MemoryStoreError
from src.model.chunk import ChunkEntity, ChunkType
from src.model.entity import EntityEntity, EntityType
from src.utils.datetime_utils import now_beijing
from src.utils.embedding_util import get_embedding_util
from src.utils.logger import get_logger
from src.utils.recall_engine import RecallEngine, compute_adaptive_memory_score

logger = get_logger()

_DEFAULT_USER_ID = 1


def _compute_content_hash(content: str, agent_id: int) -> str:
    """计算内容哈希（用于精确去重）。

    Args:
        content: 记忆内容。
        agent_id: Agent ID。

    Returns:
        SHA256 哈希字符串。
    """
    raw = f"{agent_id}:{content}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class MemoryService:
    """双层记忆系统服务。

    情景记忆流 + 语义知识库，按 agent_id 完全隔离记忆空间。

    Attributes:
        chunk_dao: Chunk DAO。
        embedding_dao: Embedding DAO。
        entity_dao: Entity DAO。
        recall_engine: 召回引擎。
    """

    def __init__(self, db_manager: DatabaseManager) -> None:
        """初始化记忆服务。

        Args:
            db_manager: 数据库管理器。
        """
        self.db_manager = db_manager
        self.chunk_dao = ChunkDao(db_manager)
        self.embedding_dao = EmbeddingDao(db_manager)
        self.entity_dao = EntityDao(db_manager)
        self.recall_engine = RecallEngine(self.chunk_dao, self.embedding_dao)

    async def memorize(
        self,
        agent_id: int,
        user_msg: str,
        assistant_msg: str,
        chunk_type: ChunkType = ChunkType.CONVERSATION,
        event_time: Optional[datetime] = None,
    ) -> tuple[int, int]:
        """写入记忆（原子操作）。

        将用户消息和助手回复作为一个对话轮关联存储，
        自动生成向量嵌入。实体提取在后台异步完成，
        不阻塞对话响应。

        Args:
            agent_id: Agent ID。
            user_msg: 用户消息。
            assistant_msg: 助手回复。
            chunk_type: 记忆类型。
            event_time: 事件发生时间（TSM）。

        Returns:
            (user_chunk_id, assistant_chunk_id) 元组。
        """
        settings = get_settings()

        try:
            user_chunk, assistant_chunk = self._store_conversation_round(
                agent_id=agent_id,
                user_msg=user_msg,
                assistant_msg=assistant_msg,
                chunk_type=chunk_type,
                event_time=event_time,
                max_length=settings.memory_max_chunk_length,
            )

            import asyncio
            asyncio.create_task(
                self._background_extract_entities(agent_id, user_msg, assistant_msg)
            )
            self._auto_expire_memories(agent_id, settings.memory_auto_expire_days)

            logger.debug(
                f"记忆写入完成: agent_id={agent_id}, "
                f"user_chunk={user_chunk.id}, assistant_chunk={assistant_chunk.id}"
            )
            return user_chunk.id, assistant_chunk.id
        except Exception as e:
            raise MemoryStoreError(
                message=f"记忆存储失败: {e}"
            ) from e

    def _store_conversation_round(
        self,
        agent_id: int,
        user_msg: str,
        assistant_msg: str,
        chunk_type: ChunkType,
        event_time: Optional[datetime],
        max_length: int,
    ) -> tuple[ChunkEntity, ChunkEntity]:
        """存储一个对话轮（Q-A 对），保证原子性。"""
        with self.db_manager.get_session() as session:
            # 1. 处理用户消息
            user_content = user_msg[:max_length] if len(user_msg) > max_length else user_msg
            user_hash = _compute_content_hash(user_content, agent_id)

            # 2. 处理助手回复
            assistant_content = assistant_msg[:max_length] if len(assistant_msg) > max_length else assistant_msg
            assistant_hash = _compute_content_hash(assistant_content, agent_id)

            # 3. 检查去重
            user_chunk = self._check_and_store_chunk(
                session=session,
                content=user_content,
                content_hash=user_hash,
                chunk_type=chunk_type,
                agent_id=agent_id,
                role="user",
                event_time=event_time,
            )

            # 4. 存储助手回复并关联父ID
            assistant_chunk = self._check_and_store_chunk(
                session=session,
                content=assistant_content,
                content_hash=assistant_hash,
                chunk_type=chunk_type,
                agent_id=agent_id,
                role="assistant",
                event_time=event_time,
                parent_id=user_chunk.id,
            )

            # 5. 提交事务
            session.commit()

            return user_chunk, assistant_chunk

    def _check_and_store_chunk(
        self,
        session,
        content: str,
        content_hash: str,
        chunk_type: ChunkType,
        agent_id: int,
        role: str,
        event_time: Optional[datetime],
        parent_id: Optional[int] = None,
    ) -> ChunkEntity:
        """检查去重并存储 Chunk，返回存储结果。"""
        # 精确去重
        existing = self.chunk_dao.select_by_hash(content_hash, agent_id)
        if existing is not None:
            existing.merge_count += 1
            session.add(existing)
            logger.debug(f"记忆精确去重: hash={content_hash[:16]}...")
            return existing

        # 模糊合并
        similar = self._find_similar_chunk(agent_id, content)
        if similar is not None:
            merged = f"{similar.content}\n[合并]{content}"
            merged_hash = _compute_content_hash(merged, agent_id)
            similar.content = merged
            similar.content_hash = merged_hash
            similar.merge_count += 1
            session.add(similar)
            # 更新向量
            self._update_embedding(similar.id, merged)
            logger.debug(f"记忆模糊合并: chunk_id={similar.id}")
            return similar

        # 新建 Chunk
        chunk = ChunkEntity(
            content=content,
            content_hash=content_hash,
            chunk_type=chunk_type,
            agent_id=agent_id,
            parent_id=parent_id,
            event_time=event_time,
            metadata_={"role": role},
        )
        orm_model = chunk.to_orm_model()
        session.add(orm_model)
        session.flush()

        # 生成向量
        try:
            embedding_util = get_embedding_util()
            vector = embedding_util.encode(content)
            self.embedding_dao.insert(orm_model.id, vector)
        except Exception as e:
            logger.warning(f"向量嵌入生成失败: {e}")

        return ChunkEntity.from_orm_model(orm_model)

    def _find_similar_chunk(
        self, agent_id: int, content: str
    ) -> Optional[ChunkEntity]:
        """查找相似记忆（用于模糊合并）。"""
        settings = get_settings()
        try:
            embedding_util = get_embedding_util()
            query_vector = embedding_util.encode(content)
            results = self.embedding_dao.search_cosine_similarity(
                agent_id, query_vector, limit=5
            )
            threshold = settings.memory_merge_similarity

            for chunk_id, similarity in results:
                if similarity > threshold:
                    return self.chunk_dao.select_by_id(chunk_id)
        except Exception as e:
            logger.warning(f"模糊合并查找失败: {e}")
        return None

    def _update_embedding(self, chunk_id: int, content: str) -> None:
        """更新向量嵌入。"""
        try:
            embedding_util = get_embedding_util()
            vector = embedding_util.encode(content)
            self.embedding_dao.upsert(chunk_id, vector)
        except Exception as e:
            logger.warning(f"向量嵌入更新失败: {e}")

    async def _background_extract_entities(
        self, agent_id: int, user_msg: str, assistant_msg: str
    ) -> None:
        """后台实体提取任务（fire-and-forget，不阻塞对话响应）。"""
        try:
            await self._extract_entities(agent_id, user_msg, assistant_msg)
        except Exception as e:
            logger.warning(f"后台实体提取失败: {e}")

    async def _extract_entities(
        self, agent_id: int, user_msg: str, assistant_msg: str
    ) -> None:
        """从对话中提取实体知识（LLM 驱动）。

        使用 OpenAI API 提取实体，或回退到规则提取。
        """
        try:
            entities = await self._llm_entity_extraction(user_msg, assistant_msg)
        except Exception as e:
            logger.warning(f"LLM 实体提取失败，使用规则提取: {e}")
            entities = self._simple_entity_extraction(user_msg, assistant_msg)

        for name, entity_type, description in entities:
            entity = EntityEntity(
                name=name,
                type=entity_type,
                description=description,
                agent_id=agent_id,
            )
            try:
                self.entity_dao.upsert_by_name(entity)
            except Exception as e:
                logger.warning(f"实体存储失败: {e}")

    async def _llm_entity_extraction(
        self, user_msg: str, assistant_msg: str
    ) -> list[tuple[str, EntityType, str]]:
        """使用 LLM 提取实体。"""
        import openai
        from src.config.settings import get_settings

        settings = get_settings()
        if not settings.llm_api_key:
            return []

        client = openai.AsyncOpenAI(
            api_key=settings.llm_api_key.get_secret_value(),
            base_url=settings.llm_base_url,
        )

        prompt = f"""
请从以下对话中提取实体，并按照以下格式输出：
实体名称|实体类型|实体描述

实体类型可选值：person, preference, habit, fact, skill, location, organization, other

对话：
用户：{user_msg}
助手：{assistant_msg}

请只输出提取结果，不要输出其他内容。
"""

        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": "你是一个专业的命名实体识别工具。"},
                     {"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=500,
        )

        entities: list[tuple[str, EntityType, str]] = []
        content = response.choices[0].message.content or ""
        for line in content.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            parts = line.split('|')
            if len(parts) == 3:
                name, type_str, desc = parts
                try:
                    entity_type = EntityType(type_str)
                    entities.append((name.strip(), entity_type, desc.strip()))
                except ValueError:
                    pass
        return entities

    def _simple_entity_extraction(
        self, user_msg: str, assistant_msg: str
    ) -> list[tuple[str, EntityType, str]]:
        """简单的实体提取规则。

        Returns:
            [(name, type, description), ...] 列表。
        """
        entities: list[tuple[str, EntityType, str]] = []
        combined = f"{user_msg} {assistant_msg}"

        preference_keywords = ["喜欢", "偏好", "最爱", "讨厌", "不喜欢", "习惯"]
        for keyword in preference_keywords:
            if keyword in combined:
                idx = combined.index(keyword)
                snippet = combined[max(0, idx - 10):idx + 30]
                entities.append((
                    f"{keyword}_{snippet[:20]}",
                    EntityType.PREFERENCE,
                    f"用户{keyword}: {snippet}",
                ))
                break

        skill_keywords = ["我会", "我擅长", "我精通", "我的专业"]
        for keyword in skill_keywords:
            if keyword in combined:
                idx = combined.index(keyword)
                snippet = combined[max(0, idx - 5):idx + 30]
                entities.append((
                    f"技能_{snippet[:20]}",
                    EntityType.SKILL,
                    f"用户技能: {snippet}",
                ))
                break

        return entities

    def _auto_expire_memories(self, agent_id: int, expire_days: int) -> None:
        """自动标记过期记忆。"""
        try:
            import datetime
            threshold = now_beijing() - datetime.timedelta(days=expire_days)
            count = self.chunk_dao.mark_expired_batch(agent_id, threshold)
            if count > 0:
                logger.debug(f"自动过期标记: agent_id={agent_id}, count={count}")
        except Exception as e:
            logger.warning(f"自动过期标记失败: {e}")

    def retrieve(
        self,
        agent_id: int,
        query: str,
        top_k: int = 10,
    ) -> list[dict]:
        """检索记忆（返回结构化结果）。

        执行完整的五步召回流水线，返回最相关的记忆内容。

        Args:
            agent_id: Agent ID。
            query: 查询文本。
            top_k: 返回数量。

        Returns:
            记忆内容字典列表，包含 id, content, score, created_at, type 等。
        """
        try:
            embedding_util = get_embedding_util()
            query_vector = embedding_util.encode(query)
        except Exception as e:
            logger.warning(f"查询向量生成失败，降级为纯BM25: {e}")
            query_vector = np.zeros(512, dtype=np.float32)

        results = self.recall_engine.recall(
            agent_id=agent_id,
            query=query,
            query_vector=query_vector,
            top_k=top_k,
        )

        memory_contents: list[dict] = []
        if not results:
            return memory_contents

        chunk_ids = [chunk_id for chunk_id, _ in results]
        chunks = self.chunk_dao.select_by_ids(chunk_ids)
        chunk_map = {c.id: c for c in chunks if not c.is_expired}

        for chunk_id, score in results:
            chunk = chunk_map.get(chunk_id)
            if chunk is not None:
                memory_contents.append({
                    "id": chunk.id,
                    "content": chunk.content,
                    "score": score,
                    "created_at": chunk.created_at,
                    "type": chunk.chunk_type.value,
                    "merge_count": chunk.merge_count,
                    "access_count": chunk.access_count,
                })

        return memory_contents

    def clear(self, agent_id: int) -> tuple[int, int]:
        """清空指定 Agent 的所有记忆。

        Args:
            agent_id: Agent ID。

        Returns:
            (删除的记忆数, 删除的实体数)。
        """
        with self.db_manager.get_session():
            deleted_chunks = self.chunk_dao.delete_by_agent_id(agent_id)
            deleted_embeddings = self.embedding_dao.delete_by_agent_id(agent_id)
            deleted_entities = self.entity_dao.delete_by_agent_id(agent_id)

        logger.info(
            f"Agent 记忆清空: agent_id={agent_id}, "
            f"chunks={deleted_chunks}, entities={deleted_entities}"
        )
        return deleted_chunks, deleted_entities

    def delete_memory(self, memory_id: int) -> None:
        """删除单条记忆。

        Args:
            memory_id: Chunk ID。

        Raises:
            MemoryNotFoundError: 记忆不存在时抛出。
        """
        chunk = self.chunk_dao.select_by_id(memory_id)
        if chunk is None:
            raise MemoryNotFoundError(memory_id=memory_id)

        with self.db_manager.get_session():
            self.chunk_dao.delete_by_id(memory_id)
            self.embedding_dao.delete_by_chunk_id(memory_id)
        logger.info(f"记忆删除: memory_id={memory_id}")

    def get_memories_by_agent(
        self,
        agent_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ChunkEntity]:
        """获取指定 Agent 的记忆列表。"""
        return self.chunk_dao.select_by_agent_id(agent_id, limit, offset)

    def get_entities_by_agent(
        self,
        agent_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EntityEntity]:
        """获取指定 Agent 的实体列表。"""
        return self.entity_dao.select_by_agent_id(agent_id, limit, offset)

    def count_memories(self, agent_id: int) -> int:
        """统计指定 Agent 的记忆数量。"""
        return self.chunk_dao.count_by_agent_id(agent_id)

    def count_entities(self, agent_id: int) -> int:
        """统计指定 Agent 的实体数量。"""
        return self.entity_dao.count_by_agent_id(agent_id)
