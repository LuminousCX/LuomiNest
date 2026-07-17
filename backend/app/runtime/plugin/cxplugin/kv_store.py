"""CxPlugin 专属 KV 存储 — 每个插件独立持久化命名空间。

基于 JsonStore 实现，每个插件对应一个 JSON 文件（cx_plugin_kv_{plugin_id}.json），
提供同步 + 异步 API。插件通过 context.get_kv_store() 获取实例。
"""
from __future__ import annotations

from typing import Any

from app.infrastructure.database.json_store import JsonStore


class PluginKVStore:
    """插件专属键值存储 — 命名空间隔离，避免插件间数据冲突。

    文件位置：{DATA_DIR}/store/cx_plugin_kv_{plugin_id}.json
    """

    def __init__(self, plugin_id: str) -> None:
        self._plugin_id = plugin_id
        # 每个插件独立文件，避免多插件并发写入互相阻塞
        self._store = JsonStore(f"cx_plugin_kv_{plugin_id}.json")

    @property
    def plugin_id(self) -> str:
        return self._plugin_id

    def get(self, key: str, default: Any = None) -> Any:
        """读取键值。"""
        return self._store.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """写入键值（持久化）。"""
        self._store.set(key, value)

    def delete(self, key: str) -> None:
        """删除键值。"""
        self._store.delete(key)

    def has(self, key: str) -> bool:
        """判断键是否存在。"""
        return self._store.get(key, _SENTINEL) is not _SENTINEL

    def keys(self) -> list[str]:
        """列出所有键。"""
        return list(self._store.list_all().keys())

    def list_all(self) -> dict[str, Any]:
        """返回所有键值对（副本）。"""
        return self._store.list_all()

    def clear(self) -> None:
        """清空所有键值（危险操作，仅插件卸载时调用）。"""
        self._store.clear()

    # ── 异步 API（供 async 插件使用） ──

    async def get_async(self, key: str, default: Any = None) -> Any:
        return await self._store.get_async(key, default)

    async def set_async(self, key: str, value: Any) -> None:
        await self._store.set_async(key, value)

    async def delete_async(self, key: str) -> None:
        await self._store.delete_async(key)

    async def list_all_async(self) -> dict[str, Any]:
        return await self._store.list_all_async()


class _Sentinel:
    """内部哨兵，用于区分 None 值与键不存在。"""


_SENTINEL = _Sentinel()
