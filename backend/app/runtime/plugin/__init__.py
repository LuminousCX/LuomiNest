"""LuomiNest 插件运行时 — CxPlugin 系统。

公共 API 导出，供 app_factory 和其他模块使用。
"""

from app.runtime.plugin.cxplugin import (
    CxPluginBase,
    CxPluginContext,
    CxEventType,
    cx_handler,
    cx_plugin_hot_reload,
    cx_plugin_lifecycle,
    cx_plugin_loader,
    cx_plugin_registry,
    init_hot_reload,
    shutdown_hot_reload,
)

__all__ = [
    "CxPluginBase",
    "CxPluginContext",
    "CxEventType",
    "cx_handler",
    "cx_plugin_hot_reload",
    "cx_plugin_lifecycle",
    "cx_plugin_loader",
    "cx_plugin_registry",
    "init_hot_reload",
    "shutdown_hot_reload",
]
