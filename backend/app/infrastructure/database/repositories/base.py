"""Repository 基类与通用工具。

设计要点：
- 所有方法返回 plain dict（非 ORM 对象），保留消费者 in-place mutation 语义
- sync 方法为核心实现，async 方法通过 asyncio.to_thread 包装（与现有 store 模式一致）
- save() 为 upsert（存在则更新，不存在则插入），跳过主键字段
- mutate() 在单事务内完成读-改-写，保证原子性
"""
import asyncio
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.infrastructure.database.session import sync_session_factory


def orm_to_dict(obj) -> Optional[dict]:
    """将 ORM 对象转为 plain dict（剥离 SQLAlchemy 内部状态）。"""
    if obj is None:
        return None
    d = obj.__dict__.copy()
    d.pop("_sa_instance_state", None)
    return d


def utcnow_iso() -> str:
    """当前 UTC 时间的 ISO 8601 字符串（与现有数据格式一致）。"""
    return datetime.now(timezone.utc).isoformat()


class BaseRepository:
    """通用 CRUD 基类。

    子类需指定：
    - model: ORM 模型类
    - pk: 主键字段名（默认 "id"）
    """

    model = None
    pk = "id"

    # ── Read ──

    def get(self, key: str) -> Optional[dict]:
        with sync_session_factory() as session:
            obj = session.get(self.model, key)
            return orm_to_dict(obj)

    def get_all(self) -> list[dict]:
        with sync_session_factory() as session:
            objs = session.execute(select(self.model)).scalars().all()
            return [orm_to_dict(o) for o in objs]

    def count(self) -> int:
        with sync_session_factory() as session:
            return session.execute(select(func.count()).select_from(self.model)).scalar() or 0

    # ── Write ──

    def save(self, key: str, data: dict) -> dict:
        """upsert：存在则更新全部字段，不存在则插入。"""
        with sync_session_factory() as session:
            obj = session.get(self.model, key)
            if obj is None:
                obj = self.model(**{self.pk: key})
                session.add(obj)
            for k, v in data.items():
                if k != self.pk:
                    setattr(obj, k, v)
            session.commit()
            session.refresh(obj)
            return orm_to_dict(obj)

    def update(self, key: str, updates: dict) -> Optional[dict]:
        """部分更新：仅更新 updates 中的字段。"""
        with sync_session_factory() as session:
            obj = session.get(self.model, key)
            if obj is None:
                return None
            for k, v in updates.items():
                if k != self.pk:
                    setattr(obj, k, v)
            session.commit()
            session.refresh(obj)
            return orm_to_dict(obj)

    def delete(self, key: str) -> bool:
        with sync_session_factory() as session:
            obj = session.get(self.model, key)
            if obj is None:
                return False
            session.delete(obj)
            session.commit()
            return True

    def delete_all(self) -> int:
        """删除全部记录，返回删除数量。"""
        from sqlalchemy import delete as sa_delete
        with sync_session_factory() as session:
            count = session.execute(select(func.count()).select_from(self.model)).scalar() or 0
            session.execute(sa_delete(self.model))
            session.commit()
            return count

    def mutate(self, key: str, updater_fn: Callable[[Optional[dict]], Optional[dict]]) -> Optional[dict]:
        """原子读-改-写（单事务内完成）。updater_fn 接收旧值（可为 None）返回新值。"""
        with sync_session_factory() as session:
            obj = session.get(self.model, key)
            current = orm_to_dict(obj)
            new_value = updater_fn(current)
            if new_value is None:
                return None
            if obj is None:
                obj = self.model(**{self.pk: key})
                session.add(obj)
            for k, v in new_value.items():
                if k != self.pk:
                    setattr(obj, k, v)
            session.commit()
            session.refresh(obj)
            return orm_to_dict(obj)

    # ── Async wrappers（与现有 store 的 asyncio.to_thread 模式一致）──

    async def get_async(self, key: str) -> Optional[dict]:
        return await asyncio.to_thread(self.get, key)

    async def get_all_async(self) -> list[dict]:
        return await asyncio.to_thread(self.get_all)

    async def count_async(self) -> int:
        return await asyncio.to_thread(self.count)

    async def save_async(self, key: str, data: dict) -> dict:
        return await asyncio.to_thread(self.save, key, data)

    async def update_async(self, key: str, updates: dict) -> Optional[dict]:
        return await asyncio.to_thread(self.update, key, updates)

    async def delete_async(self, key: str) -> bool:
        return await asyncio.to_thread(self.delete, key)

    async def delete_all_async(self) -> int:
        return await asyncio.to_thread(self.delete_all)

    async def mutate_async(self, key: str, updater_fn: Callable) -> Optional[dict]:
        return await asyncio.to_thread(self.mutate, key, updater_fn)
