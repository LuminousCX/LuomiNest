"""LuomiNest 对话模式定义。

两种顶层模式：
- NORMAL: 普通模式，function calling + 工具白名单（任务视图操作 + CLI），上下文最轻
- STANDARD: 专业模式，internal_tool_registry（JSON 计划）+ 全量工具，适合复杂长任务

上下文隔离：切换模式需新建对话，不同模式的对话各自独立，避免上下文膨胀。

工具系统路由：
- NORMAL → tool_registry（function calling）+ tool_whitelist 过滤
- STANDARD → internal_tool_registry（JSON 计划）；长尾工具经服务端检索（S1b）+ meta-tool 按需拉取

历史说明：曾存在 ULTRA 超长模式（全量工具 + 高迭代预算），已移除；
存量 ultra 会话由启动迁移归一为 standard。
"""
from enum import Enum
from typing import Any


class ChatMode(str, Enum):
    """对话模式枚举（normal=普通，standard=专业）"""
    NORMAL = "normal"
    STANDARD = "standard"


# 各模式的工具配置
CHAT_MODE_TOOL_CONFIGS: dict[ChatMode, dict[str, Any]] = {
    ChatMode.NORMAL: {
        "registry": "tool_registry",
        "whitelist": [
            "create_scheduled_task",
            "list_scheduled_tasks",
            "get_scheduled_task",
            "delete_scheduled_task",
            "cli",
            # 工具发现 meta-tool（S1b：长尾工具靠检索召回 + meta 按需拉取）
            "list_luominest_tools",
            "read_luominest_tool",
        ],
        "is_workflow": False,
    },
    ChatMode.STANDARD: {
        "registry": "internal",
        "is_workflow": True,
    },
}


def get_tool_config(mode: ChatMode) -> dict[str, Any]:
    """获取指定模式的工具配置"""
    return CHAT_MODE_TOOL_CONFIGS.get(mode, CHAT_MODE_TOOL_CONFIGS[ChatMode.STANDARD])


def is_workflow_mode(mode: ChatMode) -> bool:
    """判断是否为专业模式（底层仍使用工作流引擎）"""
    return CHAT_MODE_TOOL_CONFIGS.get(mode, {}).get("is_workflow", False)


def is_professional_mode(mode: ChatMode) -> bool:
    """判断是否为专业模式（standard）"""
    return mode == ChatMode.STANDARD


def chat_mode_to_workflow_mode(mode: ChatMode):
    """将 ChatMode 映射到 WorkflowMode（仅 STANDARD 有效）"""
    from app.core.workflow.models import WorkflowMode
    return WorkflowMode.STANDARD
