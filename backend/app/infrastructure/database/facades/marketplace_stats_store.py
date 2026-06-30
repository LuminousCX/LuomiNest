"""MarketplaceStatsStore Facade — 替代原 marketplace_stats_store 单例。

委托 MarketplaceStatRepository，保留 JsonStore 方法签名。
- mutate_async 委托 Repository.mutate_async（保留原 read-modify-write 语义）
- list_all() 返回 {item_id: stat} 映射
"""
import asyncio
from typing import Any, Callable, Optional

from app.infrastructure.database.repositories import MarketplaceStatRepository


class MarketplaceStatsFacade:
    """委托 MarketplaceStatRepository，接口与 JsonStore 一致。"""

    PK = "item_id"

    def __init__(self, repo: MarketplaceStatRepository):
        self._repo = repo

    # ── Read ──

    def get(self, key: str, default: Any = None) -> Any:
        result = self._repo.get(key)
        return result if result is not None else default

    def list_all(self) -> dict:
        return {item[self.PK]: item for item in self._repo.get_all()}

    def all(self) -> list:
        return self._repo.get_all()

    def values(self) -> list:
        return self._repo.get_all()

    def items(self) -> list:
        return [(item[self.PK], item) for item in self._repo.get_all()]

    def count(self) -> int:
        return len(self._repo.get_all())

    # ── Write ──

    def set(self, key: str, value: dict) -> None:
        self._repo.save(key, value)

    def delete(self, key: str) -> None:
        self._repo.delete(key)

    def clear(self) -> None:
        """删除全部统计记录（与 JsonStore.clear 接口对齐）。"""
        self._repo.delete_all()

    def update(self, key: str, updates: dict) -> None:
        """部分更新：读取旧值 → 合并 → 保存。"""
        existing = self._repo.get(key)
        if existing:
            merged = {**existing, **updates}
        else:
            merged = updates
        self._repo.save(key, merged)

    def mutate(self, key: str, updater_fn: Callable) -> Optional[dict]:
        """同步读-改-写。"""
        return self._repo.mutate(key, updater_fn)

    def invalidate(self) -> None:
        pass

    # ── Async wrappers ──

    async def get_async(self, key: str, default: Any = None) -> Any:
        return await asyncio.to_thread(self.get, key, default)

    async def set_async(self, key: str, value: dict) -> None:
        await asyncio.to_thread(self.set, key, value)

    async def delete_async(self, key: str) -> None:
        await asyncio.to_thread(self.delete, key)

    async def clear_async(self) -> None:
        await asyncio.to_thread(self.clear)

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

    async def mutate_async(self, key: str, updater_fn: Callable) -> Optional[dict]:
        """委托 Repository.mutate_async（原子读-改-写）。"""
        return await self._repo.mutate_async(key, updater_fn)


# ── 单例 ──

marketplace_stats_store = MarketplaceStatsFacade(MarketplaceStatRepository())
