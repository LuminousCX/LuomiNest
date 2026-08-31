"""配置存储 — 委托 ConfigRepository + config_items 表（SQLite）。

替代原 user_config.json：
- 敏感字段（api_key/secret_key）自动 AES 加解密，fnmatch 模式判定
- list_all() 中加密字段返回 "***"
"""
import asyncio
from typing import Any, Callable

from app.infrastructure.database.repositories import ConfigRepository


class LumiConfigFacade:
    """委托 ConfigRepository，接口与原 LumiConfigStore 一致。"""

    def __init__(self, repo: ConfigRepository):
        self._repo = repo

    # ── Core operations ──

    def get(self, key: str, default: Any = None) -> Any:
        return self._repo.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._repo.set(key, value)

    def delete(self, key: str) -> bool:
        return self._repo.delete(key)

    def delete_namespace(self, prefix: str) -> int:
        return self._repo.delete_namespace(prefix)

    def get_namespace(self, prefix: str) -> dict[str, Any]:
        return self._repo.get_namespace(prefix)

    def list_all(self) -> dict[str, Any]:
        return self._repo.list_all()

    def clear(self) -> None:
        self._repo.clear()

    def invalidate(self) -> None:
        self._repo.invalidate()

    # ── Async wrappers ──

    async def get_async(self, key: str, default: Any = None) -> Any:
        return await asyncio.to_thread(self.get, key, default)

    async def set_async(self, key: str, value: Any) -> None:
        await asyncio.to_thread(self.set, key, value)

    async def delete_async(self, key: str) -> bool:
        return await asyncio.to_thread(self.delete, key)

    async def get_namespace_async(self, prefix: str) -> dict[str, Any]:
        return await asyncio.to_thread(self.get_namespace, prefix)

    async def list_all_async(self) -> dict[str, Any]:
        return await asyncio.to_thread(self.list_all)


# ── 单例 ──

luominest_config_store = LumiConfigFacade(ConfigRepository())
