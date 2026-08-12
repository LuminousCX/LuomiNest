"""LuomiNest 工具发现 meta-tool（L1 主动发现，对齐 onion §6.1 ② / tool-opt §4.2.1）。

提供两个 tier=meta 的发现式工具：
- list_luominest_tools：列出全部已注册工具的名称 + 一句话描述 + tier/scope（~50 token/个），
  LLM 据此判断是否需要进一步拉取完整 schema
- read_luominest_tool：按名称拉取单个工具的完整 description + parameters schema

设计动机：
    工具越多（40+）LLM 上下文膨胀越严重（每工具 10~15KB schema），选择准确率越低
    （业界 2026 Tool Search / ScaleKit 验证）。meta-tier 工具仅注入「名称 + 一句话」，
    完整 schema 由 LLM 按需拉取，Token 消耗可降低 80%+。
"""
from __future__ import annotations

from typing import Any

from app.core.tools.registry import ToolBase, ToolResult, tool_registry


class ListLuomiNestToolsTool(ToolBase):
    """列出 LuomiNest 已注册工具概览（meta-tool，L1 主动发现）。"""

    # tier=meta：发现式，完整 schema 按需拉取
    tier: str = "meta"
    scope: str = "shared"

    @property
    def name(self) -> str:
        return "list_luominest_tools"

    @property
    def description(self) -> str:
        return (
            "列出当前可用的所有 LuomiNest 工具概览（名称 + 一句话描述 + 层级/场景）。"
            "使用此工具快速了解有哪些工具可用，再通过 read_luominest_tool 拉取指定工具的完整 schema。"
            "当用户请求复杂能力（文件搜索、浏览器、平台操作、应用启动等）但你不清楚具体工具时调用。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "tier": {
                    "type": "string",
                    "description": (
                        "按层级过滤：'core'（常驻核心）/ 'domain'（领域）/ 'meta'（发现式）/ "
                        "'all'（全部，默认）。"
                    ),
                    "enum": ["core", "domain", "meta", "all"],
                    "default": "all",
                },
                "scope": {
                    "type": "string",
                    "description": "按场景过滤：'shared'（共享，默认）/ 'platform'（平台专用）/ 'all'。",
                    "enum": ["shared", "platform", "all"],
                    "default": "all",
                },
            },
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        tier_filter = (arguments.get("tier") or "all").lower()
        scope_filter = (arguments.get("scope") or "all").lower()

        tools = tool_registry.list_tools()
        lines: list[str] = []
        for tool in tools:
            # tier 过滤
            if tier_filter != "all" and (tool.tier or "domain") != tier_filter:
                continue
            # scope 过滤
            tool_scope = tool.scope or "shared"
            if scope_filter != "all" and tool_scope != scope_filter:
                continue

            # 一行格式：- name [tier=domain, scope=shared, platform=win/mac/linux]: description（首行）
            desc_first = (tool.description or "").split("\n", 1)[0][:80]
            plat = ",".join(sorted(tool.platform)) if hasattr(tool, "platform") else "win,mac,linux"
            lines.append(
                f"- {tool.name} [tier={tool.tier}, scope={tool_scope}, platform={plat}]: {desc_first}"
            )

        if not lines:
            return ToolResult.ok("没有匹配的工具。")

        header = f"共 {len(lines)} 个工具（用 read_luominest_tool 按 name 拉取完整 schema）："
        return ToolResult.ok(header + "\n" + "\n".join(lines))


class ReadLuomiNestToolTool(ToolBase):
    """读取指定工具的完整 schema（meta-tool，L1 主动发现）。"""

    tier: str = "meta"
    scope: str = "shared"

    @property
    def name(self) -> str:
        return "read_luominest_tool"

    @property
    def description(self) -> str:
        return (
            "读取指定 LuomiNest 工具的完整描述与参数 schema。"
            "通常先调用 list_luominest_tools 找到候选工具名，再用此工具查看详细参数，"
            "然后决定是否调用该工具完成任务。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "tool_name": {
                    "type": "string",
                    "description": "要查看完整 schema 的工具名称（必须是已注册的工具名）。",
                },
            },
            "required": ["tool_name"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        tool_name = (arguments.get("tool_name") or "").strip()
        if not tool_name:
            return ToolResult.fail("缺少 tool_name 参数")

        tool = tool_registry.get(tool_name)
        if tool is None:
            available = ", ".join(sorted(tool_registry.list_names()))
            return ToolResult.fail(
                f"工具 '{tool_name}' 不存在。可用工具: {available}"
            )

        # 输出完整描述 + 参数 schema + 声明字段
        import json
        schema_str = json.dumps(tool.parameters, indent=2, ensure_ascii=False)
        output = (
            f"# {tool.name}\n\n"
            f"**tier**: {tool.tier}  |  **scope**: {tool.scope}  |  "
            f"**platform**: {','.join(sorted(tool.platform))}\n\n"
            f"## Description\n{tool.description}\n\n"
            f"## Parameters (JSON Schema)\n```json\n{schema_str}\n```"
        )
        return ToolResult.ok(output)
