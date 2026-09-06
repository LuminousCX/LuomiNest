"""Repository 基类与通用工具。

设计要点：
- 所有方法返回 plain dict（非 ORM 对象），保留消费者 in-place mutation 语义
- sync 方法为核心实现，async 方法通过 asyncio.to_thread 包装（与现有 store 模式一致）
- save() 为 upsert（存在则更新，不存在则插入），跳过主键字段
- upsert()/upsert_async() 为通用 SQLite ON CONFLICT upsert（插入值与更新字段集可不同）
- mutate() 在单事务内完成读-改-写，保证原子性
"""
import asyncio
from typing import Any, Callable, Optional

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.core.utils import utc_now
from app.infrastructure.database.session import sync_session_factory


def orm_to_dict(obj) -> Optional[dict]:
    """将 ORM 对象转为 plain dict（剥离 SQLAlchemy 内部状态）。"""
    if obj is None:
        return None
    d = obj.__dict__.copy()
    d.pop("_sa_instance_state", None)
    return d


def build_upsert_stmt(model, *, index_elements: list[str], values: dict, update_set: dict):
    """构造 SQLite upsert 语句：INSERT ... ON CONFLICT(index_elements) DO UPDATE SET update_set。

    统一原先各持久化模块手写的 sqlite_insert(...).on_conflict_do_update(...) 模式：
    - index_elements：冲突目标（唯一索引列名）
    - values：插入值；update_set：冲突时的更新字段集（两者允许不同）
    - update_set 的值在调用时绑定（不引用 excluded），也可传 SQL 表达式（如 model.col + 1）
    - 不返回行；需要读取结果时由调用方自行 SELECT

    多语句需要共享同一事务时（如批量写入），调用方可自管 session 并直接执行本函数返回的语句。
    """
    stmt = sqlite_insert(model).values(**values)
    return stmt.on_conflict_do_update(
        index_elements=list(index_elements),
        set_=dict(update_set),
    )


# Re-export for backward compatibility
utcnow_iso = utc_now


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

    @staticmethod
    def upsert(model, *, index_elements: list[str], values: dict, update_set: dict) -> None:
        """通用 SQLite upsert（单语句单事务，不返回行）。

        与 save() 的整行 upsert 不同：插入值（values）与冲突时的更新字段集
        （update_set）允许不同，冲突目标由 index_elements 指定。
        原 scheduled_task / workflow / template 持久化模块的手写 upsert 收口于此；
        多语句需共享事务时改用 build_upsert_stmt + 自管 session。
        """
        with sync_session_factory() as session:
            session.execute(
                build_upsert_stmt(
                    model, index_elements=index_elements, values=values, update_set=update_set,
                )
            )
            session.commit()

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

    def delete_by_provider(self, provider_id: str) -> int:
        """删除 provider_id 字段匹配的所有记录，返回删除数量。

        供带 provider_id 列的模型复用（ProviderCredential / ProviderModel），
        原两仓储各自手写的同义实现收口于此（逐对象删除，语义与原凭证仓储实现一致）。
        """
        with sync_session_factory() as session:
            objs = session.execute(
                select(self.model).where(self.model.provider_id == provider_id)  # type: ignore[attr-defined]
            ).scalars().all()
            count = len(objs)
            for obj in objs:
                session.delete(obj)
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

    @staticmethod
    async def upsert_async(model, *, index_elements: list[str], values: dict, update_set: dict) -> None:
        """通用 SQLite upsert 的 async 包装（与基类 to_thread 模式一致）。"""
        await asyncio.to_thread(
            BaseRepository.upsert,
            model,
            index_elements=index_elements,
            values=values,
            update_set=update_set,
        )

    async def update_async(self, key: str, updates: dict) -> Optional[dict]:
        return await asyncio.to_thread(self.update, key, updates)

    async def delete_async(self, key: str) -> bool:
        return await asyncio.to_thread(self.delete, key)

    async def delete_all_async(self) -> int:
        return await asyncio.to_thread(self.delete_all)

    async def delete_by_provider_async(self, provider_id: str) -> int:
        return await asyncio.to_thread(self.delete_by_provider, provider_id)

    async def mutate_async(self, key: str, updater_fn: Callable) -> Optional[dict]:
        return await asyncio.to_thread(self.mutate, key, updater_fn)
