"""CxPlugin 注册表 — 管理插件元数据和事件处理器。

参照 InternalToolRegistry 的异步锁 + 全局单例模式，使用 Cx 品牌前缀。
"""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from app.models.plugin import (
    CxEventType,
    CxHandlerEntry,
    CxPluginMetadata,
    CxPluginStatus,
)


class CxPluginRegistry:
    """插件注册表 — 全局单例。

    存储已加载的插件元数据和事件处理器，提供查询和分发能力。
    """

    def __init__(self) -> None:
        self._plugins: dict[str, CxPluginMetadata] = {}
        self._handlers: list[CxHandlerEntry] = []
        self._instances: dict[str, Any] = {}
        self._lock = asyncio.Lock()

    async def register_plugin(self, metadata: CxPluginMetadata, instance: Any | None = None) -> None:
        """注册插件元数据和实例。"""
        async with self._lock:
            self._plugins[metadata.plugin_id] = metadata
            if instance is not None:
                self._instances[metadata.plugin_id] = instance
            logger.debug(f"[CxPlugin] Registered plugin: {metadata.plugin_id}")

    async def unregister_plugin(self, plugin_id: str) -> None:
        """注销插件及其所有处理器。"""
        async with self._lock:
            self._plugins.pop(plugin_id, None)
            self._instances.pop(plugin_id, None)
            self._handlers = [h for h in self._handlers if h.plugin_id != plugin_id]
            logger.debug(f"[CxPlugin] Unregistered plugin: {plugin_id}")

    def register_handler(self, entry: CxHandlerEntry) -> None:
        """注册事件处理器（同步，在插件 initialize 阶段调用）。"""
        self._handlers.append(entry)
        self._handlers.sort(key=lambda h: h.priority, reverse=True)

    def get_plugin(self, plugin_id: str) -> CxPluginMetadata | None:
        return self._plugins.get(plugin_id)

    def get_instance(self, plugin_id: str) -> Any | None:
        return self._instances.get(plugin_id)

    def list_plugins(self, active_only: bool = False) -> list[CxPluginMetadata]:
        if active_only:
            return [m for m in self._plugins.values() if m.is_active]
        return list(self._plugins.values())

    def list_handlers(self, event_type: CxEventType) -> list[CxHandlerEntry]:
        return [h for h in self._handlers if h.event_type == event_type]

    def update_status(self, plugin_id: str, status: CxPluginStatus, error: str = "") -> None:
        meta = self._plugins.get(plugin_id)
        if meta:
            meta.status = status
            meta.error_message = error

    async def dispatch_event(self, event_type: CxEventType, event_data: dict[str, Any]) -> None:
        """分发事件到所有匹配的处理器。"""
        handlers = self.list_handlers(event_type)
        for entry in handlers:
            instance = self._instances.get(entry.plugin_id)
            if instance is None:
                continue
            try:
                await entry.handler(instance, event_data)
            except Exception as e:
                logger.error(f"[CxPlugin] Handler error in plugin {entry.plugin_id}: {e}")

    def clear(self) -> None:
        """清空所有注册数据（热重载时使用）。"""
        self._plugins.clear()
        self._handlers.clear()
        self._instances.clear()


# 全局单例
luominest_plugin_registry = CxPluginRegistry()
