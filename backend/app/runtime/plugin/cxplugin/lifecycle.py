"""CxPlugin 生命周期管理 — 启用/禁用/卸载/重载 + 状态持久化。

使用 lumi_config_store（SQLite config_items 表）持久化插件启用/禁用状态，
config_items 为唯一权威源；遗留 JSON 文件仅在迁移时读取一次，不删除文件本身。
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

from loguru import logger

from app.core.config import settings
from app.infrastructure.database.config_store import lumi_config_store
from app.models.plugin import CxPluginStatus
from app.runtime.plugin.cxplugin.loader import cx_plugin_loader
from app.runtime.plugin.cxplugin.registry import cx_plugin_registry

# DB 存储 key（config_items 为唯一权威源）
_DB_KEY = "plugins.states"

# 遗留 JSON 文件（DATA_DIR/store/）—— 收敛后仅在迁移时读取一次，不再写入，也不删除文件本身
_LEGACY_JSON_FILENAME = "cx_plugin_states.json"
# 遗留 JSON 文件（JsonStore 格式）中禁用插件 id 列表所在字段名
_LEGACY_JSON_FIELD = "disabled_plugins"
# _migration_meta 标记源名：与 json_to_sqlite_migrator 共用同一标记，谁先执行谁标记，避免重复合并
_MIGRATION_SOURCE = "plugin_states"


def _normalize_disabled_plugins(value: Any) -> list[str]:
    """将 config_items 中的值规范化为 list[str]。

    兼容两种历史形状：
    - list：运行时直接写入（CxPluginLifecycle._write_disabled_plugins）
    - dict：旧版迁移器写入的整个 JSON 文件内容（{"disabled_plugins": [...]}）
    """
    if isinstance(value, list):
        return [str(i) for i in value]
    if isinstance(value, dict):
        raw = value.get(_LEGACY_JSON_FIELD, [])
        return [str(i) for i in raw] if isinstance(raw, list) else []
    return []


class CxPluginLifecycle:
    """插件生命周期管理器 — 全局单例。"""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        # 遗留 JSON 合并完成标记：模块加载阶段 DB 可能尚未初始化，
        # 合并失败时保持 False，由后续首次读取时重试（_ensure_legacy_merged）
        self._legacy_merged = False
        self._merge_legacy_json()

    # ------------------------------------------------------------------
    # 内部读写辅助
    # ------------------------------------------------------------------

    def _read_disabled_plugins(self) -> list[str]:
        """从 config_items 读取禁用列表（唯一权威源）。"""
        self._ensure_legacy_merged()
        return _normalize_disabled_plugins(lumi_config_store.get(_DB_KEY))

    def _write_disabled_plugins(self, disabled: list[str]) -> None:
        """写入 config_items（唯一权威源）。"""
        lumi_config_store.set(_DB_KEY, disabled)

    def _ensure_legacy_merged(self) -> None:
        """确保遗留 JSON 合并至少成功执行过一次（幂等）。"""
        if not self._legacy_merged:
            self._merge_legacy_json()

    def _merge_legacy_json(self) -> None:
        """幂等合并遗留 JSON 文件（cx_plugin_states.json）到 config_items。

        参照 json_to_sqlite_migrator 的 _migration_meta 标记模式：
        - 已标记迁移 → 直接跳过（重跑不重复合并）
        - JSON 文件不存在 → 仅记录标记
        - JSON 文件存在 → 与 config_items 现有值取并集合并，不覆盖
        遗留 JSON 文件是用户数据：仅迁移时读取，不删除文件本身。
        """
        from app.infrastructure.database.migration.json_to_sqlite_migrator import (
            _is_migrated,
            _mark_migrated,
            _read_json_file,
        )

        try:
            if _is_migrated(_MIGRATION_SOURCE):
                self._legacy_merged = True
                return

            path = os.path.join(settings.DATA_DIR, "store", _LEGACY_JSON_FILENAME)
            data = _read_json_file(path)
            legacy_ids: list[str] = []
            if isinstance(data, dict):
                raw = data.get(_LEGACY_JSON_FIELD, [])
                if isinstance(raw, list):
                    legacy_ids = [str(i) for i in raw]

            if legacy_ids:
                existing = _normalize_disabled_plugins(lumi_config_store.get(_DB_KEY))
                merged = existing + [i for i in legacy_ids if i not in existing]
                self._write_disabled_plugins(merged)
                logger.info(
                    f"[CxPlugin] Merged legacy JSON into config_items: "
                    f"{len(merged)} disabled plugin(s)"
                )

            _mark_migrated(_MIGRATION_SOURCE, len(legacy_ids))
            self._legacy_merged = True
        except Exception as e:
            logger.warning(f"[CxPlugin] Legacy JSON merge skipped: {e}")

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
