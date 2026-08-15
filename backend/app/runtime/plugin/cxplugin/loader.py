"""CxPlugin 加载器 — 扫描、解析、导入、实例化插件。

负责从 PLUGIN_DIR 扫描插件目录，解析 manifest.json，动态导入入口模块，
实例化插件类，注入 PermissionGuard 与 CxPluginContext，收集事件处理器与
注册的工具/路由，注册到 CxPluginRegistry。

加载流程：
  扫描目录 → 解析 manifest → 校验版本/类型 → 构造 PermissionGuard
  → 动态导入入口模块 → 查找 CxPluginBase 子类 → 实例化（注入 context）
  → 调用 initialize() → 收集 handlers/tools/routes → 注册到 registry
"""
from __future__ import annotations

import contextlib
import importlib
import importlib.util
import json
import os
import sys
from typing import Any

from loguru import logger

from app.core.config import get_settings
from app.models.plugin import CxPermission, CxPluginManifest, CxPluginMetadata, CxPluginStatus
from app.runtime.plugin.cxplugin.base import CxPluginBase, CxPluginContext
from app.runtime.plugin.cxplugin.permission import PermissionGuard
from app.runtime.plugin.cxplugin.registry import luominest_plugin_registry


class CxPluginLoader:
    """插件加载器 — 扫描目录并加载所有合法插件。"""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._plugin_dir = self._settings.PLUGIN_DIR
        self._loaded: set[str] = set()
        # 运行中 FastAPI app 引用（apply_routes_to_app 时注入）
        self._app: Any = None
        # 已挂载路由的插件 ID 集合，防止重复 include_router
        self._applied_plugins: set[str] = set()

    async def load_all(self) -> int:
        """扫描 PLUGIN_DIR 并加载所有插件，返回成功加载数量。"""
        if not os.path.isdir(self._plugin_dir):
            logger.warning(f"[CxPlugin] Plugin directory not found: {self._plugin_dir}")
            return 0

        count = 0
        for entry in os.listdir(self._plugin_dir):
            entry_path = os.path.join(self._plugin_dir, entry)
            if not os.path.isdir(entry_path):
                continue
            if entry.startswith(".") or entry.startswith("_"):
                continue
            try:
                if await self.load_single(entry_path):
                    count += 1
            except Exception as e:
                logger.error(f"[CxPlugin] Failed to load plugin from {entry}: {e}")
        logger.info(f"[CxPlugin] Loaded {count} plugin(s) from {self._plugin_dir}")
        return count

    async def load_single(self, plugin_dir: str) -> bool:
        """加载单个插件目录，返回是否成功。"""
        manifest_path = os.path.join(plugin_dir, "manifest.json")
        if not os.path.isfile(manifest_path):
            logger.debug(f"[CxPlugin] No manifest.json in {plugin_dir}, skipping")
            return False

        manifest = self._parse_manifest(manifest_path)
        if manifest is None:
            return False

        # 仅加载 type=plugin 的条目（skill 类型由 skill_loader 处理）
        if manifest.type != "plugin":
            logger.debug(f"[CxPlugin] {manifest.id} type={manifest.type}, not a plugin, skipping")
            return False

        # 仅加载 backend/fullstack 平台插件（frontend/hardware 由各自加载器处理）
        if manifest.platform not in ("backend", "fullstack"):
            logger.debug(
                f"[CxPlugin] {manifest.id} platform={manifest.platform}, "
                f"skipped by backend loader"
            )
            return False

        if manifest.id in self._loaded:
            logger.warning(f"[CxPlugin] Plugin {manifest.id} already loaded, skipping")
            return False

        # 版本兼容性校验
        if not self._check_app_version(manifest):
            logger.warning(
                f"[CxPlugin] {manifest.id} requires app version "
                f"{manifest.min_app_version}, skipping"
            )
            return False

        # 动态导入入口模块
        entry_module = manifest.entry or "main"
        module_path = self._import_entry(plugin_dir, manifest.id, entry_module)
        if module_path is None:
            return False

        # 查找插件类
        plugin_cls = self._find_plugin_class(module_path)
        if plugin_cls is None:
            logger.error(f"[CxPlugin] No CxPluginBase subclass found in {manifest.id}")
            return False

        # 构造权限守卫（从 manifest.permissions 解析）
        permissions = manifest.get_permissions()
        self._warn_unknown_permissions(manifest)
        guard = PermissionGuard(manifest.id, permissions)

        # 实例化插件（注入 context + guard）
        context = CxPluginContext(
            plugin_id=manifest.id,
            plugin_dir=plugin_dir,
            config=manifest.raw,
            permission_guard=guard,
        )

        try:
            instance = plugin_cls(context)
        except Exception as e:
            logger.error(f"[CxPlugin] Failed to instantiate {manifest.id}: {e}")
            await context.cleanup()
            return False

        # 收集装饰器标记的处理器
        self._collect_decorated_handlers(manifest.id, instance, context)

        # 调用 initialize
        try:
            await instance.initialize()
        except Exception as e:
            logger.error(f"[CxPlugin] initialize() failed for {manifest.id}: {e}")
            # 清理已注册的工具与 context 资源
            await self._cleanup_plugin_resources(manifest.id, context)
            await context.cleanup()
            return False

        # 收集 context 中注册的处理器
        for entry in context.get_handlers():
            luominest_plugin_registry.register_handler(entry)

        # 注册到 registry
        metadata = CxPluginMetadata(
            manifest=manifest,
            module_path=module_path,
            plugin_dir=plugin_dir,
            status=CxPluginStatus.LOADED,
        )
        await luominest_plugin_registry.register_plugin(metadata, instance)
        self._loaded.add(manifest.id)

        logger.success(
            f"[CxPlugin] Loaded: {manifest.id} v{manifest.version} ({manifest.name}) "
            f"platform={manifest.platform} permissions={guard.list_granted()}"
        )
        return True

    def _parse_manifest(self, manifest_path: str) -> CxPluginManifest | None:
        """解析 manifest.json 文件。"""
        try:
            with open(manifest_path, encoding="utf-8") as f:
                data = json.load(f)
            return CxPluginManifest.from_dict(data)
        except json.JSONDecodeError as e:
            logger.error(f"[CxPlugin] Invalid manifest.json at {manifest_path}: {e}")
            return None
        except OSError as e:
            logger.error(f"[CxPlugin] Cannot read manifest at {manifest_path}: {e}")
            return None

    def _check_app_version(self, manifest: CxPluginManifest) -> bool:
        """校验 manifest.min_app_version 与当前应用版本兼容性。

        min_app_version 为空时视为兼容。使用简单版本字符串比较（major.minor.patch）。
        """
        if not manifest.min_app_version:
            return True
        from app import __version__ as app_version
        return _version_gte(app_version, manifest.min_app_version)

    def _warn_unknown_permissions(self, manifest: CxPluginManifest) -> None:
        """对 manifest 中无法识别的权限字符串记录警告。"""
        valid_values = {p.value for p in CxPermission}
        for perm_str in manifest.permissions:
            if perm_str not in valid_values:
                logger.warning(
                    f"[CxPlugin] {manifest.id} declares unknown permission: {perm_str}, ignored"
                )

    def _import_entry(self, plugin_dir: str, plugin_id: str, entry: str) -> str | None:
        """动态导入插件入口模块，返回模块路径。"""
        entry_file = os.path.join(plugin_dir, f"{entry}.py")
        if not os.path.isfile(entry_file):
            logger.error(f"[CxPlugin] Entry file not found: {entry_file}")
            return None

        module_name = f"cx_plugins.{plugin_id}.{entry}"
        spec = importlib.util.spec_from_file_location(module_name, entry_file)
        if spec is None or spec.loader is None:
            logger.error(f"[CxPlugin] Cannot create module spec for {plugin_id}")
            return None

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception as e:
            logger.error(f"[CxPlugin] Failed to execute {entry_file}: {e}")
            sys.modules.pop(module_name, None)
            return None

        return module_name

    def _find_plugin_class(self, module_path: str) -> type[CxPluginBase] | None:
        """从已导入的模块中查找 CxPluginBase 子类。"""
        module = sys.modules.get(module_path)
        if module is None:
            return None

        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if not isinstance(attr, type):
                continue
            if not issubclass(attr, CxPluginBase):
                continue
            if attr is CxPluginBase:
                continue
            return attr

        return None

    def _collect_decorated_handlers(
        self,
        plugin_id: str,
        instance: CxPluginBase,
        context: CxPluginContext,
    ) -> None:
        """收集用 @cx_handler 装饰器标记的方法。"""
        for attr_name in dir(instance):
            if attr_name.startswith("_"):
                continue
            method = getattr(instance, attr_name)
            if not callable(method):
                continue
            event_type = getattr(method, "_cx_event_type", None)
            if event_type is None:
                continue
            priority = getattr(method, "_cx_priority", 0)
            context.register_handler(event_type, method, priority)

    async def unload_single(self, plugin_id: str) -> bool:
        """卸载单个插件，返回是否成功。

        清理顺序：调用 terminate() → 注销工具 → 清理 context 资源 → 清理 sys.modules → 从 registry 移除
        """
        metadata = luominest_plugin_registry.get_plugin(plugin_id)
        if metadata is None:
            return False

        instance = luominest_plugin_registry.get_instance(plugin_id)
        context: CxPluginContext | None = None
        if instance is not None:
            context = getattr(instance, "context", None)
            try:
                await instance.terminate()
            except Exception as e:
                logger.warning(f"[CxPlugin] terminate() error for {plugin_id}: {e}")

        # 清理插件注册的工具与 context 资源
        if context is not None:
            await self._cleanup_plugin_resources(plugin_id, context)
            await context.cleanup()

        # 清理 sys.modules
        module_path = metadata.module_path
        to_remove = [k for k in sys.modules if k.startswith(module_path.split(".")[0] + "." + plugin_id)]
        for k in to_remove:
            sys.modules.pop(k, None)

        await luominest_plugin_registry.unregister_plugin(plugin_id)
        self._loaded.discard(plugin_id)
        # 从已挂载路由集合中移除，便于后续重新加载时重新挂载路由。
        # 注意：FastAPI 不支持移除已 include 的 router，因此 reload 场景下
        # app.router.routes 中可能残留旧路由，但 _applied_plugins 保证不会
        # 重复 include 同一插件的新 router。
        self._applied_plugins.discard(plugin_id)
        logger.info(f"[CxPlugin] Unloaded: {plugin_id}")
        return True

    async def _cleanup_plugin_resources(
        self,
        plugin_id: str,
        context: CxPluginContext,
    ) -> None:
        """清理插件注册的工具（从全局 tool_registry 注销）。"""
        from app.core.tools import tool_registry

        for tool_name in context.get_registered_tool_names():
            try:
                tool_registry.unregister(tool_name)
                logger.debug(f"[CxPlugin] Unregistered tool: {tool_name} (plugin={plugin_id})")
            except Exception as e:
                logger.warning(
                    f"[CxPlugin] Failed to unregister tool {tool_name} "
                    f"(plugin={plugin_id}): {e}"
                )

    def apply_routes_to_app(self, app: Any) -> int:
        """将所有已加载插件注册的 API 路由应用到 FastAPI app。

        在 app_factory lifespan 中、所有插件加载完成后调用。
        路由挂载到 /api/v1/plugins/{plugin_id}/{path}。

        调用时会缓存 app 引用，后续 apply_routes_for_plugin 可复用该引用
        动态挂载新安装插件的路由。

        Returns:
            成功应用的路由数量
        """
        self._app = app
        applied = 0
        for metadata in luominest_plugin_registry.list_plugins():
            applied += self._apply_plugin_routes(app, metadata.plugin_id)
        return applied

    def apply_routes_for_plugin(self, plugin_id: str) -> int:
        """动态挂载单个插件的路由到运行中的 FastAPI app。

        在 install_local_builtin_plugin 等场景下，新插件加载后调用此方法，
        使插件的 API 路由立即可用，无需重启服务。

        Args:
            plugin_id: 插件 ID

        Returns:
            成功应用的路由数量（0 表示无路由可挂载或 app 引用未就绪）
        """
        if self._app is None:
            logger.warning(
                f"[CxPlugin] Cannot apply routes for {plugin_id}: "
                f"app reference not initialized (apply_routes_to_app not called yet?)"
            )
            return 0
        return self._apply_plugin_routes(self._app, plugin_id)

    def _apply_plugin_routes(self, app: Any, plugin_id: str) -> int:
        """为指定插件挂载路由到 app（内部共享实现）。

        - 已挂载过的插件会被跳过，避免重复 include_router 导致路由重复
        - 插件未注册、未实例化、无 context、无路由时静默返回 0

        Args:
            app: FastAPI 实例
            plugin_id: 插件 ID

        Returns:
            成功应用的路由数量
        """
        if plugin_id in self._applied_plugins:
            logger.debug(f"[CxPlugin] Routes already applied for {plugin_id}, skip")
            return 0

        metadata = luominest_plugin_registry.get_plugin(plugin_id)
        if metadata is None:
            return 0

        instance = luominest_plugin_registry.get_instance(plugin_id)
        if instance is None:
            return 0

        context: CxPluginContext = getattr(instance, "context", None)
        if context is None:
            return 0

        routes = context.get_registered_routes()
        if not routes:
            return 0

        from fastapi import APIRouter

        # 为每个插件创建独立 APIRouter，挂载到 /api/v1/plugins/{plugin_id}
        plugin_router = APIRouter(
            prefix=f"/plugins/{plugin_id}",
            tags=[f"plugin-{plugin_id}"],
        )
        applied = 0
        for route_spec in routes:
            try:
                plugin_router.add_api_route(
                    path=f"/{route_spec['path']}",
                    endpoint=route_spec["handler"],
                    methods=route_spec["methods"],
                )
                applied += 1
            except Exception as e:
                logger.error(
                    f"[CxPlugin] Failed to apply route {route_spec['path']} "
                    f"for {plugin_id}: {e}"
                )

        if applied > 0:
            app.include_router(plugin_router, prefix="/api/v1")
            self._applied_plugins.add(plugin_id)
            # 清除 OpenAPI schema 缓存，使新路由在 /docs 中可见
            with contextlib.suppress(Exception):
                app.openapi_schema = None
            logger.info(f"[CxPlugin] Applied {applied} routes for {plugin_id}")

        return applied

    def get_loaded_ids(self) -> set[str]:
        return set(self._loaded)


def _version_gte(current: str, required: str) -> bool:
    """简单版本比较：current >= required，格式 major.minor.patch。

    解析失败时返回 True（宽容策略，避免阻断加载）。
    """
    try:
        cur_parts = [int(x) for x in current.split(".")[:3]]
        req_parts = [int(x) for x in required.split(".")[:3]]
        # 补齐到 3 段
        while len(cur_parts) < 3:
            cur_parts.append(0)
        while len(req_parts) < 3:
            req_parts.append(0)
        return cur_parts >= req_parts
    except (ValueError, IndexError):
        return True


# 全局单例
luominest_plugin_loader = CxPluginLoader()
