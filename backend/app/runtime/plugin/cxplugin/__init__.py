"""CxPlugin 系统 — LuomiNest 插件运行时核心。

公共 API 导出，供 app_factory 和 plugin_service 使用。

模块组成：
- base：CxPluginBase（插件父类）+ CxPluginContext（运行时上下文）+ cx_handler 装饰器
- permission：PermissionGuard 权限守卫（进程内沙箱）
- kv_store：PluginKVStore 插件专属键值存储
- loader：CxPluginLoader 扫描/导入/实例化插件
- registry：CxPluginRegistry 全局注册表
- lifecycle：CxPluginLifecycle 启用/禁用/重载/卸载 + 状态持久化
- hot_reload：CxPluginHotReload 基于轮询的文件变化检测
"""

from app.models.plugin import (
    CX_DEFAULT_PERMISSIONS,
    CxEventType,
    CxHandlerEntry,
    CxPermission,
    CxPluginCategory,
    CxPluginManifest,
    CxPluginMetadata,
    CxPluginPlatform,
    CxPluginStatus,
)
from app.runtime.plugin.cxplugin.base import CxPluginBase, CxPluginContext, cx_handler
from app.runtime.plugin.cxplugin.hot_reload import (
    luominest_plugin_hot_reload,
    init_hot_reload,
    shutdown_hot_reload,
)
from app.runtime.plugin.cxplugin.kv_store import PluginKVStore
from app.runtime.plugin.cxplugin.lifecycle import luominest_plugin_lifecycle
from app.runtime.plugin.cxplugin.loader import luominest_plugin_loader
from app.runtime.plugin.cxplugin.permission import PermissionGuard
from app.runtime.plugin.cxplugin.registry import luominest_plugin_registry

__all__ = [
    # 枚举与数据模型
    "CX_DEFAULT_PERMISSIONS",
    "CxEventType",
    "CxHandlerEntry",
    "CxPermission",
    "CxPluginCategory",
    "CxPluginManifest",
    "CxPluginMetadata",
    "CxPluginPlatform",
    "CxPluginStatus",
    # 基类与上下文
    "CxPluginBase",
    "CxPluginContext",
    "cx_handler",
    # 权限与存储
    "PermissionGuard",
    "PluginKVStore",
    # 运行时组件
    "luominest_plugin_hot_reload",
    "luominest_plugin_lifecycle",
    "luominest_plugin_loader",
    "luominest_plugin_registry",
    # 生命周期辅助
    "init_hot_reload",
    "shutdown_hot_reload",
]
