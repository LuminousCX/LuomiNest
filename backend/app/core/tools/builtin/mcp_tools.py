"""LuomiNest MCP 工具。

提供主 Agent 查询与调用 MCP 服务器的能力：
- ListMcpServersTool：列出所有 MCP 服务器状态及可用工具（无参数）
- McpTool：通用 MCP 工具调用入口（备用，正常情况下 LLM 直接调用 `server__tool`）

设计说明：
    orchestrator.get_tools_for_llm() 已自动合并 MCP 工具（命名 `server__tool`），
    LLM 可直接调用。McpTool 作为备用入口，用于：
    1. 工具未自动暴露时（如服务器刚连接但工具列表未刷新）
    2. LLM 需要动态探索未知工具时
"""
import json
from typing import Any

from loguru import logger

from app.core.tools.registry import ToolBase, ToolResult


class ListMcpServersTool(ToolBase):
    """列出所有 MCP 服务器状态及可用工具"""

    @property
    def name(self) -> str:
        return "list_mcp_servers"

    @property
    def description(self) -> str:
        return (
            "列出所有已配置的 MCP 服务器及其连接状态、可用工具列表。"
            "用于了解当前可调用的 MCP 工具。无需参数。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        try:
            from app.core.tools.mcp.manager import mcp_manager

            servers = mcp_manager.list_servers()
            if not servers:
                return ToolResult.ok("当前未配置任何 MCP 服务器。")

            lines: list[str] = []
            connected_count = 0
            total_tools = 0
            for s in servers:
                status = s.get("status", "unknown")
                tool_count = s.get("tool_count", 0)
                tools = s.get("tools", [])
                desc = s.get("description", "")
                marker = "✓" if status == "connected" else "✗"
                lines.append(f"{marker} [{s['name']}] 状态={status}, 工具数={tool_count}")
                if desc:
                    lines.append(f"    描述: {desc}")
                if s.get("error"):
                    lines.append(f"    错误: {s['error']}")
                if tools:
                    lines.append(f"    工具: {', '.join(tools)}")
                if status == "connected":
                    connected_count += 1
                    total_tools += tool_count

            summary = f"共 {len(servers)} 个服务器，{connected_count} 个已连接，{total_tools} 个可用工具\n\n"
            return ToolResult.ok(
                summary + "\n".join(lines),
                metadata={"total_servers": len(servers), "connected": connected_count, "total_tools": total_tools},
            )
        except Exception as e:
            logger.error(f"[ListMcpServersTool] 查询失败: {e}", exc_info=True)
            return ToolResult.fail(f"查询 MCP 服务器失败: {e}")


class McpTool(ToolBase):
    """通用 MCP 工具调用入口（备用）

    正常情况下 LLM 直接调用 `server__tool`（由 orchestrator 路由）。
    本工具用于备用场景：动态调用未自动暴露的工具。
    """

    @property
    def name(self) -> str:
        return "mcp_call"

    @property
    def description(self) -> str:
        return (
            "调用指定 MCP 服务器上的工具。"
            "参数 tool_name 格式为 `server__tool`（如 `filesystem__read_file`）。"
            "正常情况下应直接调用 `server__tool`，本工具用于备用场景。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "tool_name": {
                    "type": "string",
                    "description": "工具全名，格式 `server__tool`（如 `filesystem__read_file`）",
                },
                "params": {
                    "type": "object",
                    "description": "工具参数（字典）",
                    "default": {},
                },
            },
            "required": ["tool_name"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        tool_name = arguments.get("tool_name", "").strip()
        if not tool_name:
            return ToolResult.fail("缺少 tool_name 参数")

        params = arguments.get("params") or {}
        if isinstance(params, str):
            try:
                params = json.loads(params) if params.strip() else {}
            except json.JSONDecodeError:
                return ToolResult.fail(f"params 不是有效的 JSON: {params}")

        try:
            from app.core.tools.mcp.manager import mcp_manager

            parsed = mcp_manager.parse_tool_name(tool_name)
            if parsed is None:
                return ToolResult.fail(
                    f"工具名格式无效，应为 `server__tool`，实际: {tool_name}"
                )

            server_name, real_tool_name = parsed
            result_text = await mcp_manager.call_tool(server_name, real_tool_name, params)

            # call_tool 失败时返回的文本以 [MCP 开头
            if result_text.startswith("[MCP"):
                return ToolResult.fail(result_text)
            return ToolResult.ok(result_text, metadata={"server": server_name, "tool": real_tool_name})
        except Exception as e:
            logger.error(f"[McpTool] 调用失败: {e}", exc_info=True)
            return ToolResult.fail(f"MCP 工具调用失败: {e}")
