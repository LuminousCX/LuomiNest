"""LuomiNest 对话模式定义。

三种对话模式，语义分离工作流与非工作流：
- NORMAL: 普通对话模式（非工作流），工具最少，仅任务视图操作 + 表情操控
- STANDARD: 标准工作流模式，均衡裁剪，排除细粒度浏览器自动化工具
- ULTRA: 超长工作流模式，全部工具传给 LLM

工具系统路由：
- NORMAL → tool_registry（function calling）+ tool_whitelist 过滤
- STANDARD/ULTRA → internal_tool_registry（JSON 计划）+ get_filtered_module_summary 过滤
"""
from enum import Enum
from typing import Any


class ChatMode(str, Enum):
    """对话模式枚举（顶层，涵盖工作流与非工作流）"""
    NORMAL = "normal"
    STANDARD = "standard"
    ULTRA = "ultra"


# 27 个细粒度浏览器自动化工具名（STANDARD 模式排除，ULTRA 模式包含）
# 来源：browser_automation.py BROWSER_ACTION_SPECS
BROWSER_AUTOMATION_TOOL_NAMES: frozenset[str] = frozenset({
    "browser_navigate",
    "browser_go_back",
    "browser_go_forward",
    "browser_reload",
    "browser_get_url",
    "browser_get_page_title",
    "browser_click",
    "browser_double_click",
    "browser_right_click",
    "browser_hover",
    "browser_type",
    "browser_clear_input",
    "browser_press_key",
    "browser_select_option",
    "browser_scroll",
    "browser_get_dom_tree",
    "browser_get_text",
    "browser_get_attribute",
    "browser_get_html",
    "browser_screenshot",
    "browser_wait_for_load",
    "browser_wait_for_element",
    "browser_wait_for_url",
    "browser_execute_js",
    "browser_get_history",
    "browser_get_tabs",
    "browser_switch_tab",
})


# 各模式的工具配置
CHAT_MODE_TOOL_CONFIGS: dict[ChatMode, dict[str, Any]] = {
    ChatMode.NORMAL: {
        "registry": "tool_registry",
        "whitelist": [
            "create_scheduled_task",
            "list_scheduled_tasks",
            "get_scheduled_task",
            "delete_scheduled_task",
        ],
        "is_workflow": False,
    },
    ChatMode.STANDARD: {
        "registry": "internal",
        "exclude_tools": BROWSER_AUTOMATION_TOOL_NAMES,
        "is_workflow": True,
    },
    ChatMode.ULTRA: {
        "registry": "internal",
        "exclude_tools": frozenset(),
        "is_workflow": True,
    },
}


def get_tool_config(mode: ChatMode) -> dict[str, Any]:
    """获取指定模式的工具配置"""
    return CHAT_MODE_TOOL_CONFIGS.get(mode, CHAT_MODE_TOOL_CONFIGS[ChatMode.STANDARD])


def is_workflow_mode(mode: ChatMode) -> bool:
    """判断是否为工作流模式"""
    return CHAT_MODE_TOOL_CONFIGS.get(mode, {}).get("is_workflow", False)


def chat_mode_to_workflow_mode(mode: ChatMode):
    """将 ChatMode 映射到 WorkflowMode（仅 STANDARD/ULTRA 有效）"""
    from app.core.workflow.models import WorkflowMode
    if mode == ChatMode.ULTRA:
        return WorkflowMode.ULTRA
    return WorkflowMode.STANDARD
