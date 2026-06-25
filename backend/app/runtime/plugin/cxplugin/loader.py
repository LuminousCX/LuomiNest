"""CxPlugin 加载器 — 扫描、解析、导入、实例化插件。

负责从 PLUGIN_DIR 扫描插件目录，解析 manifest.json，动态导入入口模块，
实例化插件类，收集事件处理器，注册到 CxPluginRegistry。
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
import sys
from typing import Any

from loguru import logger

from app.core.config import get_settings
from app.models.plugin import CxPluginManifest, CxPluginMetadata, CxPluginStatus
from app.runtime.plugin.cxplugin.base import CxPluginBase, CxPluginContext
from app.runtime.plugin.cxplugin.registry import cx_plugin_registry


class CxPluginLoader:
    """插件加载器 — 扫描目录并加载所有合法插件。"""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._plugin_dir = self._settings.PLUGIN_DIR
        self._loaded: set[str] = set()

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

        if manifest.type != "plugin":
            logger.debug(f"[CxPlugin] {manifest.id} type={manifest.type}, not a plugin, skipping")
            return False

        if manifest.id in self._loaded:
            logger.warning(f"[CxPlugin] Plugin {manifest.id} already loaded, skipping")
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

        # 实例化插件
        context = CxPluginContext(
            plugin_id=manifest.id,
            plugin_dir=plugin_dir,
            config=manifest.raw,
        )

        try:
            instance = plugin_cls(context)
        except Exception as e:
            logger.error(f"[CxPlugin] Failed to instantiate {manifest.id}: {e}")
            return False

        # 收集装饰器标记的处理器
        self._collect_decorated_handlers(manifest.id, instance, context)

        # 调用 initialize
        try:
            await instance.initialize()
        except Exception as e:
            logger.error(f"[CxPlugin] initialize() failed for {manifest.id}: {e}")
            return False

        # 收集 context 中注册的处理器
        for entry in context.get_handlers():
            cx_plugin_registry.register_handler(entry)

        # 注册到 registry
        metadata = CxPluginMetadata(
            manifest=manifest,
            module_path=module_path,
            plugin_dir=plugin_dir,
            status=CxPluginStatus.LOADED,
        )
        await cx_plugin_registry.register_plugin(metadata, instance)
        self._loaded.add(manifest.id)

        logger.success(f"[CxPlugin] Loaded: {manifest.id} v{manifest.version} ({manifest.name})")
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
        """卸载单个插件，返回是否成功。"""
        metadata = cx_plugin_registry.get_plugin(plugin_id)
        if metadata is None:
            return False

        instance = cx_plugin_registry.get_instance(plugin_id)
        if instance is not None:
            try:
                await instance.terminate()
            except Exception as e:
                logger.warning(f"[CxPlugin] terminate() error for {plugin_id}: {e}")

        # 清理 sys.modules
        module_path = metadata.module_path
        to_remove = [k for k in sys.modules if k.startswith(module_path.split(".")[0] + "." + plugin_id)]
        for k in to_remove:
            sys.modules.pop(k, None)

        await cx_plugin_registry.unregister_plugin(plugin_id)
        self._loaded.discard(plugin_id)
        logger.info(f"[CxPlugin] Unloaded: {plugin_id}")
        return True

    def get_loaded_ids(self) -> set[str]:
        return set(self._loaded)


# 全局单例
cx_plugin_loader = CxPluginLoader()
