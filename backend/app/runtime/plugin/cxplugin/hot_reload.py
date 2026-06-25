"""CxPlugin 热重载 — 基于轮询的文件变化检测。

由于项目未安装 watchfiles 依赖，使用 asyncio 轮询实现轻量级热重载。
检测到插件 .py 文件变化后自动重载对应插件。
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

from loguru import logger

from app.runtime.plugin.cxplugin.lifecycle import cx_plugin_lifecycle
from app.runtime.plugin.cxplugin.loader import cx_plugin_loader
from app.runtime.plugin.cxplugin.registry import cx_plugin_registry


class CxPluginHotReload:
    """插件热重载管理器 — 轮询检测文件变化。"""

    POLL_INTERVAL_SECONDS = 2.0
    _instance: CxPluginHotReload | None = None

    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None
        self._file_mtimes: dict[str, float] = {}
        self._running = False

    @classmethod
    def get_instance(cls) -> CxPluginHotReload:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def start(self) -> None:
        """启动热重载轮询。"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("[CxPlugin] Hot reload watcher started")

    async def stop(self) -> None:
        """停止热重载轮询。"""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                # 任务已显式取消；这是预期控制流，无需额外处理。
                pass
            self._task = None
        logger.info("[CxPlugin] Hot reload watcher stopped")

    async def _poll_loop(self) -> None:
        """轮询主循环。"""
        while self._running:
            try:
                await self._check_changes()
            except Exception as e:
                logger.error(f"[CxPlugin] Hot reload check error: {e}")
            await asyncio.sleep(self.POLL_INTERVAL_SECONDS)

    async def _check_changes(self) -> None:
        """检查所有已加载插件的 .py 文件变化。"""
        for metadata in cx_plugin_registry.list_plugins():
            if not metadata.is_active:
                continue
            changed = self._detect_file_changes(metadata.plugin_dir, metadata.plugin_id)
            if changed:
                logger.info(f"[CxPlugin] Detected changes in {metadata.plugin_id}, reloading...")
                await cx_plugin_lifecycle.reload_plugin(metadata.plugin_id)
                # 重载后更新 mtime 缓存
                self._scan_mtimes(metadata.plugin_dir, metadata.plugin_id)

    def _detect_file_changes(self, plugin_dir: str, plugin_id: str) -> bool:
        """检测插件目录下 .py 文件是否有变化。"""
        if not os.path.isdir(plugin_dir):
            return False

        changed = False
        prefix = f"{plugin_id}:"

        for root, _dirs, files in os.walk(plugin_dir):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                key = prefix + fpath
                try:
                    mtime = os.path.getmtime(fpath)
                except OSError:
                    continue
                old_mtime = self._file_mtimes.get(key)
                if old_mtime is not None and mtime > old_mtime:
                    changed = True
                self._file_mtimes[key] = mtime

        return changed

    def _scan_mtimes(self, plugin_dir: str, plugin_id: str) -> None:
        """扫描并缓存插件目录下所有 .py 文件的修改时间。"""
        prefix = f"{plugin_id}:"
        for root, _dirs, files in os.walk(plugin_dir):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                key = prefix + fpath
                try:
                    self._file_mtimes[key] = os.path.getmtime(fpath)
                except OSError as e:
                    # 文件可能在扫描期间被删除/替换；忽略该文件并继续扫描其他文件。
                    logger.debug(f"[CxPlugin] Skip mtime snapshot for {fpath}: {e}")

    def snapshot_loaded_plugins(self) -> None:
        """为所有已加载插件建立 mtime 快照（加载完成后调用）。"""
        for metadata in cx_plugin_registry.list_plugins():
            self._scan_mtimes(metadata.plugin_dir, metadata.plugin_id)


# 全局单例
cx_plugin_hot_reload = CxPluginHotReload.get_instance()


def init_hot_reload() -> None:
    """初始化热重载（在所有插件加载完成后调用）。"""
    cx_plugin_hot_reload.snapshot_loaded_plugins()
    cx_plugin_hot_reload.start()


async def shutdown_hot_reload() -> None:
    """关闭热重载（在应用关闭时调用）。"""
    await cx_plugin_hot_reload.stop()
