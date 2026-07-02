"""通用 JsonStore Facade — 替代原 JsonStore 单例。

委托 BaseRepository 子类，保留 JsonStore 方法签名（消费者零改动）。
- list_all() 返回 dict（按 PK 索引），与 JsonStore 一致
- all()/values() 返回 list[dict]
- update() 自动设置 updated_at（与 JsonStore 一致）
- invalidate() 为 no-op（SQL 始终读取最新）
"""
import asyncio
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from app.infrastructure.database.repositories.base import BaseRepository


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class JsonStoreFacade:
    """通用 Facade，委托任意 BaseRepository 子类。

    对应原 JsonStore 单例（agents/groups/platforms/repo_sources）。
    """

    def __init__(self, repo: BaseRepository):
        self._repo = repo
        self._pk = repo.pk

    # ── Read ──

    def get(self, key: str, default: Any = None) -> Any:
        result = self._repo.get(key)
        return result if result is not None else default

    def list_all(self) -> dict:
        """返回 {pk: dict} 映射（与 JsonStore.list_all 一致）。"""
        return {item[self._pk]: item for item in self._repo.get_all()}

    def all(self) -> list:
        return self._repo.get_all()

    def values(self) -> list:
        return self._repo.get_all()

    def items(self) -> list:
        return [(item[self._pk], item) for item in self._repo.get_all()]

    def count(self) -> int:
        return self._repo.count()

    # ── Write ──

    def set(self, key: str, value: dict) -> None:
        self._repo.save(key, value)

    def delete(self, key: str) -> None:
        self._repo.delete(key)

    def clear(self) -> None:
        self._repo.delete_all()

    def update(self, key: str, updates: dict) -> None:
        """部分更新，自动设置 updated_at（与 JsonStore 一致）。"""
        updates_with_ts = {**updates, "updated_at": _utcnow_iso()}
        self._repo.update(key, updates_with_ts)

    def mutate(self, key: str, updater_fn: Callable) -> Optional[dict]:
        return self._repo.mutate(key, updater_fn)

    def invalidate(self) -> None:
        """SQL 始终读取最新数据，此方法为兼容保留。"""
        pass

    # ── Async wrappers ──

    async def get_async(self, key: str, default: Any = None) -> Any:
        return await asyncio.to_thread(self.get, key, default)

    async def set_async(self, key: str, value: dict) -> None:
        await asyncio.to_thread(self.set, key, value)

    async def delete_async(self, key: str) -> None:
        await asyncio.to_thread(self.delete, key)

    async def list_all_async(self) -> dict:
        return await asyncio.to_thread(self.list_all)

    async def all_async(self) -> list:
        return await asyncio.to_thread(self.all)

    async def update_async(self, key: str, updates: dict) -> None:
        await asyncio.to_thread(self.update, key, updates)

    async def values_async(self) -> list:
        return await asyncio.to_thread(self.values)

    async def items_async(self) -> list:
        return await asyncio.to_thread(self.items)

    async def count_async(self) -> int:
        return await asyncio.to_thread(self.count)

    async def clear_async(self) -> None:
        await asyncio.to_thread(self.clear)

    async def mutate_async(self, key: str, updater_fn: Callable) -> Optional[dict]:
        return await asyncio.to_thread(self.mutate, key, updater_fn)


# ── 单例（与原 json_store.py 中的单例名一致）──

from app.infrastructure.database.repositories import (
    AgentRepository,
    GroupRepository,
    PlatformRepository,
    RepoSourceRepository,
)

agents_store = JsonStoreFacade(AgentRepository())
groups_store = JsonStoreFacade(GroupRepository())
platforms_store = JsonStoreFacade(PlatformRepository())
repo_sources_store = JsonStoreFacade(RepoSourceRepository())
