"""LuomiNest 探索式工具发现（一切皆工具、一切皆插件）。

把原 5 个发现类工具（list/read_luominest_tool + list/read/use_luominest_skill）
合并为 2 个探索式工具，长尾能力按需拉取，压低 prompt 常驻占用：

- tool_explore：不带 query 返回工具索引（名称 + 一句话），带 query 走注册表
  加权检索并直接返回命中工具的完整 schema（省去 list→read 两次往返）。
- skill_explore：不带 query 返回技能索引；带 query 返回匹配技能摘要；
  带 name 返回单个技能完整指引（原 read/use 合一——技能 body 本身就是
  给 LLM 的行动指引，读取即"使用"）。

S1b 检索：tool 侧复用 ToolRegistry.search() 词项加权召回（远期可换向量）。
"""
from __future__ import annotations

import json
from typing import Any

from app.core.tools.registry import ToolBase, ToolResult, tool_registry


def _skill_registry():
    """延迟导入 luominest_skill_registry，避免模块级循环依赖。"""
    from app.runtime.plugin.skill.registry import luominest_skill_registry

    return luominest_skill_registry


class ToolExploreTool(ToolBase):
    """探索可用工具：索引概览 / 检索召回 + 完整 schema（meta-tool）。"""

    tier: str = "meta"
    scope: str = "shared"

    @property
    def name(self) -> str:
        return "tool_explore"

    @property
    def description(self) -> str:
        return (
            "探索 LuomiNest 的可用工具（一切皆工具）。不带 query 返回全部工具索引"
            "（名称+一句话）；带 query 按用户需求检索并直接返回命中工具的完整参数 "
            "schema。当用户需要文件搜索、浏览器、平台操作、应用启动、定时任务等"
            "能力时，先用此工具找到工具再调用。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "需求描述或关键词（如 '搜索本地文件' / '发布群公告' / '查看室内温度'）。"
                        "留空返回工具分类索引概览。"
                    ),
                },
                "category": {
                    "type": "string",
                    "enum": ["all", "memory", "browser", "platform", "iot", "schedule", "file", "basic"],
                    "description": "按分类筛选工具（如 'platform' 跨平台工具, 'memory' 记忆系统, 'browser' 浏览器）",
                },
                "tool_name": {
                    "type": "string",
                    "description": "精确拉取指定工具的完整调用参数 Schema（优先于 query）。",
                },
            },
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        tool_name = (arguments.get("tool_name") or "").strip()
        query = (arguments.get("query") or "").strip()
        category = (arguments.get("category") or "").strip().lower()

        # 精确读取：单工具完整 schema
        if tool_name:
            tool = tool_registry.get(tool_name)
            if tool is None:
                return ToolResult.fail(
                    f"工具 '{tool_name}' 不存在。可用工具名示例: {', '.join(sorted(tool_registry.list_names())[:15])}..."
                )
            return ToolResult.ok(self._tool_detail(tool))

        # 检索召回：命中即带完整 schema（省一次 read 往返）
        if query:
            hits = tool_registry.search(query, top_k=5)
            if not hits:
                return ToolResult.ok(
                    f"没有与 '{query}' 直接相关的工具。可调用本工具（不带参数或指定 category）查看分类工具索引。"
                )
            blocks = [self._tool_detail(t) for t in hits]
            header = f"检索 '{query}' 命中 {len(blocks)} 个工具（可直接按 schema 调用）："
            return ToolResult.ok(header + "\n\n" + "\n\n".join(blocks))

        # 分类归纳工具
        categorized: dict[str, list[str]] = {
            "memory": [],
            "browser": [],
            "platform": [],
            "iot": [],
            "schedule": [],
            "file": [],
            "basic": [],
            "other": [],
        }

        for tool in tool_registry.list_tools():
            t_name = tool.name.lower()
            desc_first = (tool.description or "").split("\n", 1)[0][:60]
            entry = f"- `{tool.name}`: {desc_first}"

            if "memory" in t_name:
                categorized["memory"].append(entry)
            elif "browser" in t_name:
                categorized["browser"].append(entry)
            elif any(p in t_name for p in ("platform", "qq", "wechat", "discord", "telegram", "mc.")):
                categorized["platform"].append(entry)
            elif "iot" in t_name or "mqtt" in t_name or "hardware" in t_name:
                categorized["iot"].append(entry)
            elif "schedule" in t_name or "task" in t_name:
                categorized["schedule"].append(entry)
            elif any(f in t_name for f in ("file", "search", "everything")):
                categorized["file"].append(entry)
            elif any(b in t_name for b in ("time", "weather", "cli")):
                categorized["basic"].append(entry)
            else:
                categorized["other"].append(entry)

        cat_names = {
            "memory": "🧠 记忆系统工具 (Memory)",
            "browser": "🌐 浏览器观察工具 (Browser)",
            "platform": "💬 跨平台操作工具 (QQ/微信/Discord/Telegram/MC)",
            "iot": "🏠 IoT 与智能硬件 (MQTT/传感器/终端)",
            "schedule": "⏰ 定时任务与调度 (Schedule)",
            "file": "📁 文件与路径检索 (File & Search)",
            "basic": "⚡ 日常轻量工具 (Time / Weather / CLI)",
            "other": "🔧 扩展与其它工具 (Other)",
        }

        if category and category in categorized:
            target_list = categorized[category]
            label = cat_names.get(category, category)
            if not target_list:
                return ToolResult.ok(f"分类 [{label}] 下暂无已注册工具。")
            return ToolResult.ok(f"### {label}\n" + "\n".join(target_list) + "\n\n（提示：如需参数定义，调用 `tool_explore(tool_name='xxx')`）")

        # 返回全部分类概览
        lines = ["# LuomiNest 工具分类索引概览"]
        for cat_key, items in categorized.items():
            if items:
                lines.append(f"\n### {cat_names.get(cat_key, cat_key)}")
                lines.extend(items)

        lines.append("\n> **使用方式**：如需具体工具参数 Schema，请传入 `tool_name`（如 `tool_explore(tool_name='memory_add')`）或 `query` 模糊搜索。")
        return ToolResult.ok("\n".join(lines))

    @staticmethod
    def _tool_detail(tool: ToolBase) -> str:
        schema_str = json.dumps(tool.parameters, indent=2, ensure_ascii=False)
        plat = ",".join(sorted(tool.platform)) if hasattr(tool, "platform") else "win,mac,linux"
        return (
            f"# {tool.name} [tier={tool.tier}, scope={tool.scope or 'shared'}, platform={plat}]\n\n"
            f"{tool.description}\n\n"
            f"## Parameters (JSON Schema)\n```json\n{schema_str}\n```"
        )


class SkillExploreTool(ToolBase):
    """探索 LuomiNest 技能：索引 / 检索 / 完整指引（meta-tool，读取即使用）。"""

    tier: str = "meta"
    scope: str = "shared"

    @property
    def name(self) -> str:
        return "skill_explore"

    @property
    def description(self) -> str:
        return (
            "探索 LuomiNest 技能库（一切皆插件：文档处理、设计、旅行规划、情感陪伴等）。"
            "不带参数返回技能索引；带 query 按需求检索匹配技能；带 name 返回单个技能的"
            "完整行动指引——拿到指引后直接按其内容执行即可。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "需求描述（如 '做一份旅行计划' / '做幻灯片'）。留空返回技能索引。",
                },
                "name": {
                    "type": "string",
                    "description": "精确读取指定技能 id 的完整行动指引（优先于 query）。",
                },
            },
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        registry = _skill_registry()
        name = (arguments.get("name") or "").strip()
        query = (arguments.get("query") or "").strip()

        if name:
            skill = registry.get(name)
            if skill is None or not skill.is_active or not registry.is_enabled(name):
                return ToolResult.fail(f"技能 '{name}' 不存在或未启用。")
            return ToolResult.ok(f"# 技能：{skill.name}\n\n{skill.body}")

        skills = registry.list_skills(active_only=True)
        if not skills:
            return ToolResult.ok("技能库为空。")

        if query:
            q = query.lower()
            hits = [
                s
                for s in skills
                if q in (s.name or "").lower()
                or q in (s.description or "").lower()
                or any(q in (k or "").lower() for k in (s.trigger_keywords or []))
            ]
            if not hits:
                return ToolResult.ok(
                    f"没有与 '{query}' 匹配的技能。可调用本工具（不带参数）查看技能索引。"
                )
            blocks = [
                f"- **{s.name}**（id={s.id}）：{(s.description or '')[:120]}"
                for s in hits
            ]
            return ToolResult.ok(
                f"匹配 {len(blocks)} 个技能，带 name={hits[0].id} 获取完整指引：\n" + "\n".join(blocks)
            )

        lines = [
            f"- {s.name}（id={s.id}）：{(s.description or '')[:100]}" for s in skills
        ]
        return ToolResult.ok(
            f"共 {len(lines)} 个技能。带 query 检索、或带 name 获取完整行动指引：\n" + "\n".join(lines)
        )
