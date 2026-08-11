"""CxPlugin 专属 KV 存储 — 每个插件独立持久化命名空间。

基于 config_items 表（SQLite，具备 AES 加密与统一备份链路）实现，
键以命名空间前缀 `plugins.kv.<plugin_id>.` 存储；插件通过
context.get_kv_store() 获取实例。公开方法签名与旧 JsonStore 实现保持一致，
插件开发者无感知。

遗留迁移：旧 JSON 文件（{DATA_DIR}/store/cx_plugin_kv_{plugin_id}.json）
在首次访问时幂等合并（并集，不覆盖已有键），由 _migration_meta 按
`plugin_kv.<plugin_id>` 标记，重跑不重复合并；旧文件是用户数据，不删除。
"""
from __future__ import annotations

from typing import Any

from app.infrastructure.database.config_namespace_store import ConfigNamespaceStore

# namespace → (_migration_meta 源名, 遗留 JSON 文件名模板)
_NAMESPACE_META: dict[str, tuple[str, str]] = {
    "kv": ("plugin_kv", "cx_plugin_kv_{plugin_id}.json"),
    "settings": ("plugin_settings", "cx_plugin_settings_{plugin_id}.json"),
}


class PluginKVStore:
    """插件专属键值存储 — 命名空间隔离，避免插件间数据冲突。

    存储位置：config_items 表，键形如 `plugins.kv.<plugin_id>.<key>`
    （settings 命名空间为 `plugins.settings.<plugin_id>.<key>`）。
    """

    def __init__(self, plugin_id: str, namespace: str = "kv") -> None:
        self._plugin_id = plugin_id
        self._namespace = namespace
        source, filename_tmpl = _NAMESPACE_META.get(
            namespace,
            (f"plugin_{namespace}", f"cx_plugin_{namespace}_{{plugin_id}}.json"),
        )
        # 每个插件独立 config_items 命名空间；遗留 JSON 首次访问时幂等合并
        self._store = ConfigNamespaceStore(
            f"plugins.{namespace}.{plugin_id}",
            legacy_source=f"{source}.{plugin_id}",
            legacy_filename=filename_tmpl.format(plugin_id=plugin_id),
        )

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
