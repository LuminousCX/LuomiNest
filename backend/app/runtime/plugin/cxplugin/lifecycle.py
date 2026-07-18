"""CxPlugin 生命周期管理 — 启用/禁用/卸载/重载 + 状态持久化。

使用 lumi_config_store（SQLite config_items 表）持久化插件启用/禁用状态，
保留 JsonStore 作为 fallback / 备份（过渡期兼容）。
"""

from __future__ import annotations

import asyncio

from loguru import logger

from app.infrastructure.database.config_store import lumi_config_store
from app.infrastructure.database.json_store import JsonStore
from app.models.plugin import CxPluginStatus
from app.runtime.plugin.cxplugin.loader import cx_plugin_loader
from app.runtime.plugin.cxplugin.registry import cx_plugin_registry

# DB 存储 key
_DB_KEY = "plugins.states"


class CxPluginLifecycle:
    """插件生命周期管理器 — 全局单例。"""

    def __init__(self) -> None:
        self._store = JsonStore("cx_plugin_states.json")
        self._lock = asyncio.Lock()
        self._init_store()

    # ------------------------------------------------------------------
    # 内部读写辅助
    # ------------------------------------------------------------------

    def _read_disabled_plugins(self) -> list[str]:
        """从 DB 读取禁用列表，DB 无数据时 fallback 到 JSON 文件。"""
        data = lumi_config_store.get(_DB_KEY)
        if data is not None:
            return data if isinstance(data, list) else []
        # fallback: JSON 文件
        return self._store.get("disabled_plugins", [])

    def _write_disabled_plugins(self, disabled: list[str]) -> None:
        """写入 DB，同时保留 JSON 文件备份。"""
        lumi_config_store.set(_DB_KEY, disabled)
        try:
            self._store.set("disabled_plugins", disabled)
        except Exception as e:
            logger.warning(f"[CxPlugin] Failed to write JSON backup: {e}")

    def _init_store(self) -> None:
        """初始化持久化存储。"""
        disabled = self._read_disabled_plugins()
        self._write_disabled_plugins(disabled)

    def get_disabled_plugins(self) -> list[str]:
        """获取已禁用的插件 ID 列表。"""
        return self._read_disabled_plugins()

    async def enable_plugin(self, plugin_id: str) -> bool:
        """启用插件。"""
        async with self._lock:
            metadata = cx_plugin_registry.get_plugin(plugin_id)
            if metadata is None:
                logger.warning(f"[CxPlugin] Cannot enable {plugin_id}: not loaded")
                return False

            disabled = self.get_disabled_plugins()
            if plugin_id in disabled:
                disabled.remove(plugin_id)
                self._write_disabled_plugins(disabled)

            cx_plugin_registry.update_status(plugin_id, CxPluginStatus.ENABLED)
            logger.info(f"[CxPlugin] Enabled: {plugin_id}")
            return True

    async def disable_plugin(self, plugin_id: str) -> bool:
        """禁用插件（不卸载，仅标记为禁用状态）。"""
        async with self._lock:
            metadata = cx_plugin_registry.get_plugin(plugin_id)
            if metadata is None:
                return False

            disabled = self.get_disabled_plugins()
            if plugin_id not in disabled:
                disabled.append(plugin_id)
                self._write_disabled_plugins(disabled)

            cx_plugin_registry.update_status(plugin_id, CxPluginStatus.DISABLED)
            logger.info(f"[CxPlugin] Disabled: {plugin_id}")
            return True

    async def reload_plugin(self, plugin_id: str) -> bool:
        """重载插件 — 卸载后重新加载。"""
        async with self._lock:
            await cx_plugin_loader.unload_single(plugin_id)
            metadata = cx_plugin_registry.get_plugin(plugin_id)
            plugin_dir = metadata.plugin_dir if metadata else None
            if plugin_dir is None:
                return False
            return await cx_plugin_loader.load_single(plugin_dir)

    async def unload_plugin(self, plugin_id: str) -> bool:
        """卸载插件。"""
        async with self._lock:
            return await cx_plugin_loader.unload_single(plugin_id)

    async def reload_all(self) -> int:
        """重载所有插件。"""
        async with self._lock:
            loaded_ids = cx_plugin_loader.get_loaded_ids()
            for plugin_id in list(loaded_ids):
                await cx_plugin_loader.unload_single(plugin_id)
            cx_plugin_registry.clear()
            return await cx_plugin_loader.load_all()

    def is_enabled(self, plugin_id: str) -> bool:
        """检查插件是否启用。"""
        metadata = cx_plugin_registry.get_plugin(plugin_id)
        if metadata is None:
            return False
        return plugin_id not in self.get_disabled_plugins()


# 全局单例
cx_plugin_lifecycle = CxPluginLifecycle()
