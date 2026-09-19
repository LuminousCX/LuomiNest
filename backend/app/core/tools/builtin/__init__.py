"""LuomiNest 内置工具集。

提供主 Agent 的核心工具能力：
- cli_tool：CliTool（命令行执行，含危险命令过滤）
- file_tools：ReadFileTool / WriteFileTool / ListFilesTool / SearchFilesTool
- search_everything_tool：SearchEverythingTool（文件搜索，Everything/OsWalk 适配器）
- mcp_tools：McpTool（MCP 工具调用）/ ListMcpServersTool（MCP 服务器状态）
- subagent_tool：DelegateToSubagentTool（子 Agent 委派）
- collaboration_tool：LuomiNestStartCollaborationTool（工作台多 Agent 协作）
- memory_search_tool：LuomiNestMemorySearchTool（记忆主动搜索，群聊 Agent 查主 Agent 记忆）
- scheduler_tool：CreateScheduledTaskTool（定时任务创建）
- explore_tools：ToolExploreTool / SkillExploreTool（探索式工具与技能发现，tier=meta，
  原 list/read/use 技能三件套 + list/read 工具二件套合并而来，一切皆工具/插件）

所有工具继承 ToolBase，统一使用 `arguments: dict[str, Any]` 签名。
在 app_factory lifespan 中注册到 tool_registry。
"""
from app.core.tools.builtin.cli_tool import CliTool
from app.core.tools.builtin.collaboration_tool import LuomiNestStartCollaborationTool
from app.core.tools.builtin.file_tools import (
    ListFilesTool,
    ReadFileTool,
    SearchFilesTool,
    WriteFileTool,
)
from app.core.tools.builtin.mcp_tools import ListMcpServersTool, McpTool
from app.core.tools.builtin.memory_search_tool import LuomiNestMemorySearchTool
from app.core.tools.builtin.scheduler_tool import (
    CreateScheduledTaskTool,
    DeleteScheduledTaskTool,
    GetScheduledTaskTool,
    ListScheduledTasksTool,
)
from app.core.tools.builtin.explore_tools import SkillExploreTool, ToolExploreTool
from app.core.tools.builtin.search_everything_tool import SearchEverythingTool
from app.core.tools.builtin.subagent_tool import DelegateToSubagentTool

__all__ = [
    "CliTool",
    "ToolExploreTool",
    "SkillExploreTool",
    "ReadFileTool",
    "WriteFileTool",
    "ListFilesTool",
    "SearchFilesTool",
    "McpTool",
    "ListMcpServersTool",
    "DelegateToSubagentTool",
    "LuomiNestStartCollaborationTool",
    "LuomiNestMemorySearchTool",
    "CreateScheduledTaskTool",
    "ListScheduledTasksTool",
    "GetScheduledTaskTool",
    "DeleteScheduledTaskTool",


    "SearchEverythingTool",
]
