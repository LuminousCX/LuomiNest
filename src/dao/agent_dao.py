"""Agent 人格数据访问对象。

基于 SQLAlchemy ORM 实现 Agent 人格的 CRUD 操作。
使用 DatabaseManager 共享数据库引擎。
"""

from __future__ import annotations

import threading
from typing import Optional

from sqlalchemy import func, select

from src.dao.database import DatabaseManager
from src.exceptions import AgentNotFoundError, DaoError
from src.model.agent import AgentEntity, AgentModel, AgentStatus, AgentType
from src.utils.logger import get_logger

logger = get_logger()

_AGENT_CACHE_LOCK = threading.Lock()
_AGENT_CACHE: dict[int, AgentEntity] = {}
_AGENT_CACHE_MAX = 32


class AgentDao:
    """Agent 人格 DAO。

    使用 DatabaseManager 共享引擎进行数据库操作。

    Attributes:
        db_manager: 数据库管理器。
    """

    def __init__(self, db_manager: DatabaseManager) -> None:
        """初始化 DAO。

        Args:
            db_manager: 数据库管理器实例。
        """
        self.db_manager = db_manager
        logger.info("Agent DAO 初始化完成（使用共享 DatabaseManager）")

    def insert(self, entity: AgentEntity) -> AgentEntity:
        """插入 Agent 人格记录。"""
        with self.db_manager.get_session() as session:
            orm_model = entity.to_orm_model()
            session.add(orm_model)
            session.flush()

            result = AgentEntity.from_orm_model(orm_model)
            self._cache_put(result.id, result)
            logger.info(f"Agent 创建成功: id={result.id}, name={result.name}")
            return result

    def update(self, agent_id: int, update_data: dict) -> bool:
        """更新 Agent 人格记录。"""
        with self.db_manager.get_session() as session:
            orm_model = session.get(AgentModel, agent_id)
            if orm_model is None:
                raise AgentNotFoundError(agent_id=str(agent_id))

            for key, value in update_data.items():
                if hasattr(orm_model, key) and value is not None:
                    setattr(orm_model, key, value)

            self._cache_evict(agent_id)
            logger.info(f"Agent 更新成功: id={agent_id}")
            return True

    def delete(self, agent_id: int) -> bool:
        """删除 Agent 人格记录。"""
        with self.db_manager.get_session() as session:
            orm_model = session.get(AgentModel, agent_id)
            if orm_model is not None:
                session.delete(orm_model)
                self._cache_evict(agent_id)
                logger.info(f"Agent 删除成功: id={agent_id}")
            return True

    def select_by_id(self, agent_id: int) -> Optional[AgentEntity]:
        """根据 ID 查询 Agent 人格。"""
        cached = self._cache_get(agent_id)
        if cached is not None:
            return cached

        with self.db_manager.get_session() as session:
            orm_model = session.get(AgentModel, agent_id)
            if orm_model is None:
                return None
            entity = AgentEntity.from_orm_model(orm_model)
            self._cache_put(agent_id, entity)
            return entity

    def select_all(self) -> list[AgentEntity]:
        """查询所有活跃的 Agent 人格。"""
        with self.db_manager.get_session() as session:
            stmt = (
                select(AgentModel)
                .where(AgentModel.status == AgentStatus.ACTIVE.value)
                .order_by(AgentModel.updated_at.desc())
            )
            results = session.execute(stmt).scalars().all()
            return [AgentEntity.from_orm_model(m) for m in results]

    def select_by_type(self, agent_type: AgentType) -> list[AgentEntity]:
        """根据类型查询 Agent 人格。"""
        with self.db_manager.get_session() as session:
            stmt = (
                select(AgentModel)
                .where(
                    AgentModel.agent_type == agent_type.value,
                    AgentModel.status == AgentStatus.ACTIVE.value,
                )
                .order_by(AgentModel.updated_at.desc())
            )
            results = session.execute(stmt).scalars().all()
            return [AgentEntity.from_orm_model(m) for m in results]

    def select_by_name(self, name: str) -> Optional[AgentEntity]:
        """根据名称查询 Agent 人格。"""
        with self.db_manager.get_session() as session:
            stmt = (
                select(AgentModel)
                .where(
                    AgentModel.name == name,
                    AgentModel.status == AgentStatus.ACTIVE.value,
                )
            )
            result = session.execute(stmt).scalar_one_or_none()
            if result is None:
                return None
            return AgentEntity.from_orm_model(result)

    def count(self) -> int:
        """统计 Agent 人格总数。"""
        with self.db_manager.get_session() as session:
            stmt = select(func.count(AgentModel.id))
            return session.execute(stmt).scalar() or 0

    @staticmethod
    def _cache_get(agent_id: int) -> Optional[AgentEntity]:
        with _AGENT_CACHE_LOCK:
            return _AGENT_CACHE.get(agent_id)

    @staticmethod
    def _cache_put(agent_id: int, entity: AgentEntity) -> None:
        with _AGENT_CACHE_LOCK:
            if len(_AGENT_CACHE) >= _AGENT_CACHE_MAX:
                oldest_key = next(iter(_AGENT_CACHE))
                del _AGENT_CACHE[oldest_key]
            _AGENT_CACHE[agent_id] = entity

    @staticmethod
    def _cache_evict(agent_id: int) -> None:
        with _AGENT_CACHE_LOCK:
            _AGENT_CACHE.pop(agent_id, None)
