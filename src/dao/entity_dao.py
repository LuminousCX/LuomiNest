"""实体知识数据访问对象。

基于 SQLAlchemy ORM 实现 Entity 的 CRUD 操作，
支持按 agent_id 隔离和名称/类型查询。
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.dao.database import DatabaseManager
from src.model.entity import EntityEntity, EntityModel, EntityType
from src.utils.datetime_utils import now_beijing
from src.utils.logger import get_logger

logger = get_logger()


class EntityDao:
    """实体知识 DAO。

    使用 SQLAlchemy ORM 进行数据库操作，
    支持按 agent_id 完全隔离实体空间。

    Attributes:
        db_manager: 数据库管理器。
    """

    def __init__(self, db_manager: DatabaseManager) -> None:
        self.db_manager = db_manager

    def insert(self, entity: EntityEntity) -> EntityEntity:
        """插入实体知识。"""
        with self.db_manager.get_session() as session:
            orm_model = entity.to_orm_model()
            session.add(orm_model)
            session.flush()
            result = EntityEntity.from_orm_model(orm_model)
            logger.debug(f"Entity 创建成功: id={result.id}, name={result.name}")
            return result

    def upsert_by_name(self, entity: EntityEntity) -> EntityEntity:
        """按名称和 agent_id 插入或更新实体。

        如果同名同类型实体已存在，则增加计数并更新描述。

        Args:
            entity: Entity 实体。

        Returns:
            更新后的 Entity 实体。
        """
        existing = self.select_by_name(entity.name, entity.agent_id, entity.type)
        if existing is not None:
            return self._update_existing_entity(existing, entity)
        return self.insert(entity)

    def _update_existing_entity(
        self, existing: EntityEntity, new_entity: EntityEntity
    ) -> EntityEntity:
        """更新已存在的实体。"""
        with self.db_manager.get_session() as session:
            orm_model = session.get(EntityModel, existing.id)
            if orm_model is None:
                return self.insert(new_entity)
            orm_model.count += 1
            orm_model.last_seen_at = now_beijing()
            if new_entity.description:
                orm_model.description = new_entity.description
            session.flush()
            return EntityEntity.from_orm_model(orm_model)

    def delete_by_id(self, entity_id: int) -> bool:
        """根据 ID 删除实体。"""
        with self.db_manager.get_session() as session:
            stmt = delete(EntityModel).where(EntityModel.id == entity_id)
            session.execute(stmt)
            return True

    def delete_by_agent_id(self, agent_id: int) -> int:
        """删除指定 Agent 的所有实体。"""
        with self.db_manager.get_session() as session:
            stmt = delete(EntityModel).where(EntityModel.agent_id == agent_id)
            result = session.execute(stmt)
            return result.rowcount

    def select_by_id(self, entity_id: int) -> Optional[EntityEntity]:
        """根据 ID 查询实体。"""
        with self.db_manager.get_session() as session:
            orm_model = session.get(EntityModel, entity_id)
            if orm_model is None:
                return None
            return EntityEntity.from_orm_model(orm_model)

    def select_by_name(
        self, name: str, agent_id: int, entity_type: Optional[EntityType] = None
    ) -> Optional[EntityEntity]:
        """根据名称和 Agent ID 查询实体。"""
        with self.db_manager.get_session() as session:
            conditions = [
                EntityModel.name == name,
                EntityModel.agent_id == agent_id,
            ]
            if entity_type is not None:
                conditions.append(EntityModel.type == entity_type.value)

            stmt = select(EntityModel).where(*conditions)
            result = session.execute(stmt).scalar_one_or_none()
            if result is None:
                return None
            return EntityEntity.from_orm_model(result)

    def select_by_agent_id(
        self,
        agent_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EntityEntity]:
        """查询指定 Agent 的所有实体。"""
        with self.db_manager.get_session() as session:
            stmt = (
                select(EntityModel)
                .where(EntityModel.agent_id == agent_id)
                .order_by(EntityModel.count.desc(), EntityModel.last_seen_at.desc())
                .limit(limit)
                .offset(offset)
            )
            results = session.execute(stmt).scalars().all()
            return [EntityEntity.from_orm_model(m) for m in results]

    def count_by_agent_id(self, agent_id: int) -> int:
        """统计指定 Agent 的实体数量。"""
        from sqlalchemy import func

        with self.db_manager.get_session() as session:
            stmt = select(func.count(EntityModel.id)).where(
                EntityModel.agent_id == agent_id,
            )
            return session.execute(stmt).scalar() or 0
