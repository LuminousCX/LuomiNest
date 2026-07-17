"""CxPlugin 数据模型 — LuomiNest 插件元数据与状态定义。

所有类名/变量名使用 Cx 前缀（LuminousChenXi 品牌），与项目品牌对齐。

本模块定义插件系统的核心数据契约：
- 状态/类型/权限枚举（CxPluginStatus / CxPluginPlatform / CxPluginCategory / CxPermission / CxEventType）
- Manifest 数据模型（CxPluginManifest，含 platform/dependencies/settings/hooks 扩展字段）
- 运行时元数据（CxPluginMetadata）与事件处理器条目（CxHandlerEntry）
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


class CxPluginPlatform(str, Enum):
    """插件目标平台 — 区分后端/前端/硬件/全栈插件。"""

    BACKEND = "backend"        # 后端 Python 插件
    FRONTEND = "frontend"      # 前端 Vue 插件
    HARDWARE = "hardware"      # 硬件驱动插件
    FULLSTACK = "fullstack"    # 全栈插件（前后端一体）


class CxPluginCategory(str, Enum):
    """插件功能分类 — 用于市场分组与过滤。"""

    INTEGRATION = "integration"    # 第三方服务集成
    UI = "ui"                      # 前端 UI 增强
    TOOL = "tool"                  # 工具/能力扩展
    ADAPTER = "adapter"            # 平台适配器
    DEVICE = "device"              # 硬件设备驱动
    THEME = "theme"                # 主题/外观
    AUTOMATION = "automation"      # 自动化规则


class CxPermission(str, Enum):
    """插件权限级别 — 渐进式权限体系。

    BASIC / EVENT_LISTEN 为默认授予的基础权限；
    NETWORK / FILE_* / DATABASE / TOOL_REGISTER 为标准权限（manifest 声明后授予）；
    FILE_SYSTEM / SYSTEM_COMMAND / ADMIN_API 为高级权限（需额外审批）。
    """

    # 基础权限（默认授予）
    BASIC = "basic"                    # 基础运行能力
    EVENT_LISTEN = "event_listen"      # 监听事件

    # 标准权限（manifest 声明，用户确认）
    NETWORK = "network"                # 网络访问
    FILE_READ = "file_read"            # 文件读取（限插件目录）
    FILE_WRITE = "file_write"          # 文件写入（限插件数据目录）
    DATABASE = "database"              # 数据库访问
    TOOL_REGISTER = "tool_register"    # 注册工具

    # 高级权限（需额外审批）
    FILE_SYSTEM = "file_system"        # 完整文件系统访问
    SYSTEM_COMMAND = "system_command"  # 执行系统命令
    ADMIN_API = "admin_api"            # 管理级 API 访问


# 默认授予的权限集合（无需 manifest 声明）
CX_DEFAULT_PERMISSIONS: frozenset[CxPermission] = frozenset({
    CxPermission.BASIC,
    CxPermission.EVENT_LISTEN,
})


class CxEventType(str, Enum):
    """插件可监听的事件类型。

    事件类型按域分组：插件生命周期 / 消息与对话 / LLM 交互 / 平台与适配器 / 系统。
    硬件相关事件（ON_DEVICE_* / ON_MQTT_MESSAGE）暂不启用，待硬件扩展阶段再加入。
    """

    # === 插件生命周期 ===
    ON_PLUGIN_LOADED = "on_plugin_loaded"
    ON_PLUGIN_UNLOADED = "on_plugin_unloaded"
    ON_PLUGIN_ENABLED = "on_plugin_enabled"
    ON_PLUGIN_DISABLED = "on_plugin_disabled"

    # === 消息与对话 ===
    ON_CHAT_MESSAGE = "on_chat_message"
    ON_CHAT_RESPONSE = "on_chat_response"
    ON_MESSAGE_SENT = "on_message_sent"

    # === LLM 交互 ===
    ON_LLM_REQUEST = "on_llm_request"
    ON_LLM_RESPONSE = "on_llm_response"
    ON_TOOL_CALL = "on_tool_call"
    ON_TOOL_RESULT = "on_tool_result"

    # === 平台与适配器 ===
    ON_PLATFORM_MESSAGE = "on_platform_message"
    ON_PLATFORM_CONNECTED = "on_platform_connected"
    ON_PLATFORM_DISCONNECTED = "on_platform_disconnected"

    # === 系统 ===
    ON_SCHEDULED_TASK = "on_scheduled_task"
    ON_USER_ACTION = "on_user_action"
    ON_SYSTEM_STARTUP = "on_system_startup"
    ON_SYSTEM_SHUTDOWN = "on_system_shutdown"


@dataclass
class CxPluginManifest:
    """插件 manifest 解析后的数据模型。

    与 install_service.py 安装后的 manifest.json 对齐，扩展了以下字段：
    - platform: 目标平台（backend/frontend/hardware/fullstack）
    - dependencies: 运行时依赖（python 版本、pip 包）
    - settings: 插件可配置项声明（供前端 UI 渲染配置表单）
    - hooks: 生命周期钩子函数路径映射
    所有扩展字段均有默认值，保证旧版 manifest.json 向后兼容。
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

    # === 扩展字段（Phase 1 新增，向后兼容） ===
    platform: str = "backend"                         # CxPluginPlatform 值
    dependencies: dict[str, Any] = field(default_factory=dict)   # {python: ">=3.12", pip: [...]}
    settings: dict[str, dict[str, Any]] = field(default_factory=dict)  # 配置项声明
    hooks: dict[str, str] = field(default_factory=dict)          # {on_enable: "hooks.on_enable"}

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
            # 扩展字段：缺失时使用默认值，保证旧版 manifest 兼容
            platform=data.get("platform", "backend"),
            dependencies=data.get("dependencies", {}) or {},
            settings=data.get("settings", {}) or {},
            hooks=data.get("hooks", {}) or {},
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
            "platform": self.platform,
            "dependencies": self.dependencies,
            "settings": self.settings,
            "hooks": self.hooks,
        }

    def get_permissions(self) -> set[CxPermission]:
        """解析 manifest.permissions 字段为 CxPermission 集合。

        始终包含默认权限（BASIC + EVENT_LISTEN），
        再合并 manifest 声明的权限；非法权限字符串会被忽略并记录。
        """
        result: set[CxPermission] = set(CX_DEFAULT_PERMISSIONS)
        for perm_str in self.permissions:
            try:
                result.add(CxPermission(perm_str))
            except ValueError:
                # 非法权限字符串忽略；loader 层会记录警告
                pass
        return result


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
