"""CxPlugin 基类与上下文 — 所有 LuomiNest 插件的运行时基础。

设计参考了业界插件系统的自动注册模式（__init_subclass__）和生命周期钩子模式，
但所有实现均为原创，使用 Cx 品牌前缀，与 LuomiNest 项目对齐。

本模块提供：
- CxPluginContext：插件运行时上下文，暴露事件/工具/路由/KV/配置/HTTP/日志等 API
- CxPluginBase：所有插件的父类，提供 __init_subclass__ 自动注册与生命周期钩子
- cx_handler：装饰器，标记方法为事件处理器
"""
from __future__ import annotations

import os
from abc import ABC
from typing import Any

import httpx
from loguru import logger as root_logger

from app.models.plugin import CxEventType, CxHandlerEntry, CxPermission
from app.runtime.plugin.cxplugin.kv_store import PluginKVStore
from app.runtime.plugin.cxplugin.permission import PermissionGuard


class CxPluginContext:
    """插件运行时上下文 — 暴露给插件使用的 API 接口。

    由 loader 在实例化插件时注入，插件通过 self.context 访问系统能力。
    所有敏感操作（工具注册、API 路由、HTTP 客户端、配置写入、KV 存储）
    均通过 PermissionGuard 校验权限，未授权时抛 PermissionError。

    事件处理器注册与事件发射不要求额外权限（默认 EVENT_LISTEN 即可）。
    """

    def __init__(
        self,
        plugin_id: str,
        plugin_dir: str,
        config: dict[str, Any] | None = None,
        permission_guard: PermissionGuard | None = None,
    ) -> None:
        self.plugin_id = plugin_id
        self.plugin_dir = plugin_dir
        # config 为 manifest.raw 全量字段（向后兼容：旧调用方仅传 config）
        self.config = config or {}
        # 权限守卫：未提供时使用仅默认权限的守卫（安全降级）
        self._guard = permission_guard or PermissionGuard(
            plugin_id, set()  # 仅默认权限
        )
        # 插件专属 logger（绑定 plugin_id 维度）
        self._logger = root_logger.bind(component="CxPlugin", plugin_id=plugin_id)
        # 事件处理器收集列表（loader 实例化后收集）
        self._handlers: list[CxHandlerEntry] = []
        # 插件注册的工具名称列表（卸载时用于清理）
        self._registered_tool_names: list[str] = []
        # 插件注册的 API 路由规格列表（loader 应用到 FastAPI app）
        self._registered_routes: list[dict[str, Any]] = []
        # 插件专属 KV 存储
        self._kv_store = PluginKVStore(plugin_id)
        # 共享 HTTP 客户端（懒创建，需 NETWORK 权限）
        self._http_client: httpx.AsyncClient | None = None
        # 用户可变的 settings 配置（独立于 manifest.raw，持久化到 config_items）
        self._settings_store = None  # 懒创建，避免 import 时副作用

    # ===================================================================
    # 事件系统
    # ===================================================================

    def register_handler(
        self,
        event_type: CxEventType,
        handler: Any,
        priority: int = 0,
    ) -> None:
        """注册事件处理器（EVENT_LISTEN 权限，默认授予）。"""
        entry = CxHandlerEntry(
            plugin_id=self.plugin_id,
            event_type=event_type,
            handler=handler,
            priority=priority,
        )
        self._handlers.append(entry)

    def emit_event(self, event_type: CxEventType, data: dict[str, Any]) -> None:
        """主动发射事件到全局事件总线（同步触发，非阻塞）。

        通过 luominest_plugin_registry.dispatch_event 异步分发，此处用 asyncio.create_task
        触发，不等待完成。需要 EVENT_LISTEN 权限（默认授予）。
        """
        import asyncio

        # 懒导入避免循环依赖
        from app.runtime.plugin.cxplugin.registry import luominest_plugin_registry

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(luominest_plugin_registry.dispatch_event(event_type, data))
        except RuntimeError:
            # 无运行中的事件循环（如同步上下文），降级为同步调用
            self._logger.warning(
                f"[CxPlugin] No running loop for emit_event({event_type.value}), "
                f"event dropped"
            )

    def get_handlers(self) -> list[CxHandlerEntry]:
        """获取已注册的处理器列表（供 loader 收集）。"""
        return list(self._handlers)

    # ===================================================================
    # 工具注册（需 TOOL_REGISTER 权限）
    # ===================================================================

    def register_tool(self, tool: Any) -> None:
        """向全局 ToolRegistry 注册自定义工具（需 TOOL_REGISTER 权限）。

        Args:
            tool: ToolBase 子类实例

        Raises:
            PermissionError: 插件未声明 tool_register 权限
        """
        self._guard.check(CxPermission.TOOL_REGISTER)
        from app.core.tools import tool_registry

        tool_registry.register(tool)
        self._registered_tool_names.append(tool.name)
        self._logger.debug(f"[CxPlugin] Tool registered: {tool.name}")

    def unregister_tool(self, name: str) -> bool:
        """从全局 ToolRegistry 注销工具（需 TOOL_REGISTER 权限）。"""
        self._guard.check(CxPermission.TOOL_REGISTER)
        from app.core.tools import tool_registry

        removed = tool_registry.unregister(name)
        if name in self._registered_tool_names:
            self._registered_tool_names.remove(name)
        return removed

    def get_registered_tool_names(self) -> list[str]:
        """获取本插件注册的工具名称列表（供 loader 卸载时清理）。"""
        return list(self._registered_tool_names)

    # ===================================================================
    # API 路由注册（需 ADMIN_API 权限，挂载到 /api/v1/plugins/{plugin_id}/）
    # ===================================================================

    def register_api_route(
        self,
        path: str,
        handler: Any,
        methods: list[str] | None = None,
    ) -> None:
        """注册额外的 API 路由（需 ADMIN_API 权限）。

        路由最终挂载到 /api/v1/plugins/{plugin_id}/{path}。
        loader 在加载完成后统一应用到 FastAPI app。

        Args:
            path: 路由相对路径（如 "status"），不含前导斜杠
            handler: FastAPI 路由处理函数（async def）
            methods: HTTP 方法列表，默认 ["GET"]

        Raises:
            PermissionError: 插件未声明 admin_api 权限
        """
        self._guard.check(CxPermission.ADMIN_API)
        if methods is None:
            methods = ["GET"]
        # 校验 path 不含路径遍历
        if ".." in path or path.startswith("/"):
            raise ValueError(f"Invalid route path: {path}")
        self._registered_routes.append({
            "path": path,
            "handler": handler,
            "methods": methods,
        })
        self._logger.debug(f"[CxPlugin] API route registered: {path} {methods}")

    def get_registered_routes(self) -> list[dict[str, Any]]:
        """获取本插件注册的路由规格列表（供 loader 应用到 app）。"""
        return list(self._registered_routes)

    # ===================================================================
    # 数据存储
    # ===================================================================

    def get_data_dir(self) -> str:
        """获取插件专属数据目录（自动创建）。

        位于 {plugin_dir}/data/ 下，插件可自由读写，无需额外权限。
        """
        data_dir = os.path.join(self.plugin_dir, "data")
        os.makedirs(data_dir, exist_ok=True)
        return data_dir

    def get_kv_store(self) -> PluginKVStore:
        """获取插件专属 KV 存储（持久化，命名空间隔离）。"""
        return self._kv_store

    # ===================================================================
    # 配置管理
    # ===================================================================

    def get_config(self, key: str, default: Any = None) -> Any:
        """读取插件配置项。

        优先读取用户通过 set_config 写入的可变 settings；
        其次读取 manifest.raw 中的静态配置（含 manifest.settings 默认值）。
        """
        # 1. 用户可变 settings 优先
        if self._settings_store is not None:
            user_val = self._settings_store.get(key, _SENTINEL)
            if user_val is not _SENTINEL:
                return user_val
        # 2. manifest.raw 静态配置
        if key in self.config:
            return self.config[key]
        # 3. manifest.settings 声明的默认值
        settings_decl = self.config.get("settings", {})
        if key in settings_decl and isinstance(settings_decl[key], dict):
            return settings_decl[key].get("default", default)
        return default

    def set_config(self, key: str, value: Any) -> None:
        """写入插件配置项（持久化，需 FILE_WRITE 权限）。

        写入用户可变 settings 存储，不修改 manifest.raw。
        读取时通过 get_config 自动合并（settings 优先于 manifest）。

        Raises:
            PermissionError: 插件未声明 file_write 权限
        """
        self._guard.check(CxPermission.FILE_WRITE)
        self._ensure_settings_store()
        self._settings_store.set(key, value)  # type: ignore[union-attr]
        self._logger.debug(f"[CxPlugin] Config updated: {key}")

    def _ensure_settings_store(self) -> None:
        """懒创建插件 settings 持久化存储。

        存储于 config_items 命名空间 plugins.settings.<plugin_id>
        （唯一权威源）；遗留 JSON 文件首次访问时幂等合并，旧文件保留不删除。
        """
        if self._settings_store is None:
            self._settings_store = PluginKVStore(self.plugin_id, namespace="settings")

    # ===================================================================
    # 系统能力
    # ===================================================================

    def get_http_client(self) -> httpx.AsyncClient:
        """获取共享的 HTTP 客户端（需 NETWORK 权限）。

        返回插件专属的 httpx.AsyncClient 实例，在插件卸载时由 loader 关闭。
        客户端配置了合理超时与连接限制，避免插件耗尽连接池。

        Raises:
            PermissionError: 插件未声明 network 权限
        """
        self._guard.check(CxPermission.NETWORK)
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
        return self._http_client

    def get_logger(self):
        """获取插件专属 logger（已绑定 plugin_id 维度）。"""
        return self._logger

    # ===================================================================
    # 生命周期辅助（供 loader 调用）
    # ===================================================================

    async def cleanup(self) -> None:
        """插件卸载时清理资源（关闭 HTTP 客户端等）。由 loader 调用。"""
        if self._http_client is not None:
            try:
                await self._http_client.aclose()
            except Exception as e:
                self._logger.warning(f"[CxPlugin] HTTP client close error: {e}")
            self._http_client = None


class CxPluginBase(ABC):
    """所有 CxPlugin 的父类。

    子类通过继承此类并实现 initialize/terminate 方法来定义插件生命周期。
    使用 __init_subclass__ 自动收集插件类，供 loader 发现。
    """

    # 子类可覆盖的元数据（也可来自 manifest）
    plugin_name: str = ""
    plugin_version: str = ""
    plugin_description: str = ""
    plugin_author: str = ""

    # 全局已注册的插件类（module_path -> class）
    _cx_registered_classes: dict[str, type[CxPluginBase]] = {}

    def __init__(self, context: CxPluginContext):
        self.context = context
        # 暴露 logger 为实例属性，方便插件直接 self.logger 使用
        self.logger = context.get_logger()

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # 记录子类，key 为 module.qualname
        module = getattr(cls, "__module__", "")
        qualname = getattr(cls, "__qualname__", "")
        key = f"{module}.{qualname}"
        CxPluginBase._cx_registered_classes[key] = cls

    async def initialize(self) -> None:
        """插件激活时调用 — 子类覆盖此方法初始化资源、注册 Handler。"""

    async def terminate(self) -> None:
        """插件停用时调用 — 子类覆盖此方法释放资源。"""

    @classmethod
    def clear_registered_classes(cls) -> None:
        """清空已注册的插件类记录（热重载时使用）。"""
        cls._cx_registered_classes.clear()


def cx_handler(event_type: CxEventType, priority: int = 0) -> Any:
    """装饰器 — 标记方法为事件处理器。

    使用方式:
        class MyPlugin(CxPluginBase):
            @cx_handler(CxEventType.ON_CHAT_MESSAGE)
            async def on_message(self, event):
                ...
    """

    def decorator(func: Any) -> Any:
        func._cx_event_type = event_type
        func._cx_priority = priority
        return func

    return decorator


class _Sentinel:
    """内部哨兵，用于区分 None 值与键不存在。"""


_SENTINEL = _Sentinel()
