"""CxPlugin 数据模型 — LuomiNest 插件元数据与状态定义。

所有类名/变量名使用 Cx 前缀（LuminousChenXi 品牌），与项目品牌对齐。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.core.utils import utc_now


class CxPluginStatus(str, Enum):
    """插件运行时状态。"""

    LOADED = "loaded"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"
    UNLOADED = "unloaded"


class CxEventType(str, Enum):
    """插件可监听的事件类型。"""

    ON_PLUGIN_LOADED = "on_plugin_loaded"
    ON_PLUGIN_UNLOADED = "on_plugin_unloaded"
    ON_CHAT_MESSAGE = "on_chat_message"
    ON_LLM_REQUEST = "on_llm_request"
    ON_LLM_RESPONSE = "on_llm_response"
    ON_TOOL_CALL = "on_tool_call"


@dataclass
class CxPluginManifest:
    """插件 manifest 解析后的数据模型。

    与 install_service.py 安装后的 manifest.json 对齐，扩展了 entry/minAppVersion 等字段。
    """

    id: str
    type: str = "plugin"
    name: str = ""
    version: str = "0.0.0"
    description: str = ""
    author: str = ""
    entry: str = "main"
    min_app_version: str = ""
    capabilities: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    icon: str = ""
    category: str = ""
    tags: list[str] = field(default_factory=list)
    license: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CxPluginManifest:
        return cls(
            id=data.get("id", ""),
            type=data.get("type", "plugin"),
            name=data.get("name", ""),
            version=data.get("version", "0.0.0"),
            description=data.get("description", ""),
            author=data.get("author", ""),
            entry=data.get("entry", "main"),
            min_app_version=data.get("minAppVersion", ""),
            capabilities=data.get("capabilities", []) or [],
            permissions=data.get("permissions", []) or [],
            icon=data.get("icon", ""),
            category=data.get("category", ""),
            tags=data.get("tags", []) or [],
            license=data.get("license", ""),
            raw=data,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "entry": self.entry,
            "minAppVersion": self.min_app_version,
            "capabilities": self.capabilities,
            "permissions": self.permissions,
            "icon": self.icon,
            "category": self.category,
            "tags": self.tags,
            "license": self.license,
        }


@dataclass
class CxPluginMetadata:
    """插件运行时元数据 — 注册表中存储的条目。"""

    manifest: CxPluginManifest
    module_path: str
    plugin_dir: str
    status: CxPluginStatus = CxPluginStatus.UNLOADED
    loaded_at: str = field(default_factory=utc_now)
    error_message: str = ""
    reserved: bool = False

    @property
    def plugin_id(self) -> str:
        return self.manifest.id

    @property
    def is_active(self) -> bool:
        return self.status in (CxPluginStatus.LOADED, CxPluginStatus.ENABLED)


@dataclass
class CxHandlerEntry:
    """事件处理器注册条目。"""

    plugin_id: str
    event_type: CxEventType
    handler: Any
    priority: int = 0
    registered_at: str = field(default_factory=utc_now)
