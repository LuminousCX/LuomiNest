"""CxPlugin 业务服务层 — 连接 API 层与运行时核心。

提供插件列表查询、启用/禁用/重载/卸载等业务操作，供 API 端点调用。
"""

from __future__ import annotations

from typing import Any

from app.models.plugin import CxPluginMetadata, CxPluginStatus
from app.runtime.plugin.cxplugin.lifecycle import luominest_plugin_lifecycle
from app.runtime.plugin.cxplugin.loader import luominest_plugin_loader
from app.runtime.plugin.cxplugin.registry import luominest_plugin_registry


class CxPluginService:
    """插件业务服务 — 全局单例。"""

    async def initialize(self) -> int:
        """加载所有插件（应用启动时调用）。"""
        count = await luominest_plugin_loader.load_all()
        # 应用禁用状态
        for plugin_id in luominest_plugin_lifecycle.get_disabled_plugins():
            metadata = luominest_plugin_registry.get_plugin(plugin_id)
            if metadata and metadata.status == CxPluginStatus.LOADED:
                luominest_plugin_registry.update_status(plugin_id, CxPluginStatus.DISABLED)
        return count

    def list_plugins(self) -> list[dict[str, Any]]:
        """列出所有已加载的插件信息。"""
        result: list[dict[str, Any]] = []
        for metadata in luominest_plugin_registry.list_plugins():
            result.append(self._to_dict(metadata))
        return result

    def get_plugin(self, plugin_id: str) -> dict[str, Any] | None:
        """获取单个插件信息。"""
        metadata = luominest_plugin_registry.get_plugin(plugin_id)
        if metadata is None:
            return None
        return self._to_dict(metadata)

    async def enable_plugin(self, plugin_id: str) -> bool:
        """启用插件。"""
        return await luominest_plugin_lifecycle.enable_plugin(plugin_id)

    async def disable_plugin(self, plugin_id: str) -> bool:
        """禁用插件。"""
        return await luominest_plugin_lifecycle.disable_plugin(plugin_id)

    async def reload_plugin(self, plugin_id: str) -> bool:
        """重载插件。"""
        return await luominest_plugin_lifecycle.reload_plugin(plugin_id)

    async def unload_plugin(self, plugin_id: str) -> bool:
        """卸载插件。"""
        return await luominest_plugin_lifecycle.unload_plugin(plugin_id)

    async def reload_all(self) -> int:
        """重载所有插件。"""
        return await luominest_plugin_lifecycle.reload_all()

    def _to_dict(self, metadata: CxPluginMetadata) -> dict[str, Any]:
        """将插件元数据转为 API 响应字典。"""
        return {
            "id": metadata.manifest.id,
            "name": metadata.manifest.name,
            "version": metadata.manifest.version,
            "description": metadata.manifest.description,
            "author": metadata.manifest.author,
            "status": metadata.status.value,
            "is_active": metadata.is_active,
            "is_enabled": luominest_plugin_lifecycle.is_enabled(metadata.plugin_id),
            "loaded_at": metadata.loaded_at,
            "error": metadata.error_message,
            "capabilities": metadata.manifest.capabilities,
            "permissions": metadata.manifest.permissions,
            "icon": metadata.manifest.icon,
            "category": metadata.manifest.category,
        }


# 全局单例
luominest_plugin_service = CxPluginService()
