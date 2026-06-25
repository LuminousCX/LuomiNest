"""CxPlugin 系统 — LuomiNest 插件运行时核心。

公共 API 导出，供 app_factory 和 plugin_service 使用。
"""

from app.models.plugin import (
    CxEventType,
    CxHandlerEntry,
    CxPluginManifest,
    CxPluginMetadata,
    CxPluginStatus,
)
from app.runtime.plugin.cxplugin.base import CxPluginBase, CxPluginContext, cx_handler
from app.runtime.plugin.cxplugin.hot_reload import (
    cx_plugin_hot_reload,
    init_hot_reload,
    shutdown_hot_reload,
)
from app.runtime.plugin.cxplugin.lifecycle import cx_plugin_lifecycle
from app.runtime.plugin.cxplugin.loader import cx_plugin_loader
from app.runtime.plugin.cxplugin.registry import cx_plugin_registry

__all__ = [
    "CxPluginBase",
    "CxPluginContext",
    "CxEventType",
    "CxHandlerEntry",
    "CxPluginManifest",
    "CxPluginMetadata",
    "CxPluginStatus",
    "cx_handler",
    "cx_plugin_hot_reload",
    "cx_plugin_lifecycle",
    "cx_plugin_loader",
    "cx_plugin_registry",
    "init_hot_reload",
    "shutdown_hot_reload",
]
