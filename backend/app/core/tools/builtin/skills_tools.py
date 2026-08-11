"""LuomiNest 技能工具（洋葱架构 §11.2 / B10）。

各场景通用的三个技能工具入口：

| 工具                    | 参数                    | 行为                                             |
| --------------------- | --------------------- | ---------------------------------------------- |
| list_luominest_skills | category?, keyword?   | 返回已启用技能列表（id/name/description/category/version） |
| read_luominest_skill  | skill_id              | 返回 SKILL.md 完整内容（body 全文）                      |
| use_luominest_skill   | skill_id, input       | 返回「技能指令 + 任务」拼接文本，供 LLM 按技能流程执行                |

数据来源为 cx_skill_registry（运行时缓存层，§11.1 三位一体中的第三层，
"供 prompt 注入与工具读取"）；skills 表是附加持久化索引，不参与运行时读取。
技能 body 只读注入（§11.5：技能禁止注册工具/路由，仅允许注入 Prompt）。
"""
from __future__ import annotations

from typing import Any

from loguru import logger

from app.core.tools.registry import ToolBase, ToolResult


def _get_registry():
    """延迟导入 cx_skill_registry，避免模块级循环依赖。"""
    from app.runtime.plugin.skill.registry import cx_skill_registry
    return cx_skill_registry


class LuomiNestListSkillsTool(ToolBase):
    """列出已启用技能（支持 category / keyword 过滤）。"""

    @property
    def name(self) -> str:
        return "list_luominest_skills"

    @property
    def description(self) -> str:
        return (
            "列出当前已启用的技能（skill）。"
            "可选按 category（技能分类，精确匹配）与 keyword（关键词，匹配 id/名称/描述/标签）过滤。"
            "返回每个技能的 id、名称、描述、分类与版本，"
            "可配合 read_luominest_skill / use_luominest_skill 使用具体技能。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "按技能分类过滤（如 lifestyle / productivity，可选）",
                },
                "keyword": {
                    "type": "string",
                    "description": "关键词过滤（匹配技能 id/名称/描述/标签，可选）",
                },
            },
            "required": [],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        category = str(arguments.get("category") or "").strip()
        keyword = str(arguments.get("keyword") or "").strip()

        try:
            registry = _get_registry()
        except Exception as e:
            logger.error(f"[SkillsTools] 导入技能注册表失败: {e}")
            return ToolResult.fail(f"技能系统不可用: {e}")

        skills = registry.list_skills(active_only=True)

        if category:
            category_lower = category.casefold()
            skills = [s for s in skills if (s.category or "").casefold() == category_lower]
        if keyword:
            kw = keyword.casefold()

            def _hit(s) -> bool:
                return (
                    kw in s.id.casefold()
                    or kw in (s.name or "").casefold()
                    or kw in (s.description or "").casefold()
                    or any(kw in str(t).casefold() for t in s.tags)
                )

            skills = [s for s in skills if _hit(s)]

        if not skills:
            return ToolResult.ok(
                "没有匹配的已启用技能。",
                metadata={"count": 0, "category": category, "keyword": keyword},
            )

        lines: list[str] = []
        for s in skills:
            cat_part = f" | 分类: {s.category}" if s.category else ""
            lines.append(f"- {s.id} | {s.name} v{s.version}{cat_part} | {s.description}")

        result_text = f"共 {len(skills)} 个已启用技能：\n" + "\n".join(lines)
        return ToolResult.ok(
            result_text,
            metadata={"count": len(skills), "category": category, "keyword": keyword},
        )


class LuomiNestReadSkillTool(ToolBase):
    """读取单个技能的 SKILL.md 完整内容（body 全文）。"""

    @property
    def name(self) -> str:
        return "read_luominest_skill"

    @property
    def description(self) -> str:
        return (
            "读取指定技能的完整指令内容（SKILL.md body 全文）。"
            "传入 skill_id（可通过 list_luominest_skills 获取），返回该技能的完整指令体，"
            "用于了解技能的具体执行流程与规范。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "skill_id": {
                    "type": "string",
                    "description": "技能 id（kebab-case，如 travel-planner）",
                },
            },
            "required": ["skill_id"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        skill_id = str(arguments.get("skill_id") or "").strip()
        if not skill_id:
            return ToolResult.fail("缺少 skill_id 参数")

        try:
            registry = _get_registry()
        except Exception as e:
            logger.error(f"[SkillsTools] 导入技能注册表失败: {e}")
            return ToolResult.fail(f"技能系统不可用: {e}")

        skill = registry.get(skill_id)
        if skill is None:
            return ToolResult.fail(f"技能不存在: {skill_id}")
        if not registry.is_enabled(skill_id) or not skill.is_active:
            return ToolResult.fail(f"技能已禁用: {skill_id}")
        if not skill.body:
            return ToolResult.fail(f"技能内容为空: {skill_id}")

        return ToolResult.ok(
            skill.body,
            metadata={"skill_id": skill.id, "name": skill.name, "version": skill.version},
        )


class LuomiNestUseSkillTool(ToolBase):
    """应用技能：返回「技能指令 + 用户任务」拼接文本，供 LLM 按技能流程执行。"""

    @property
    def name(self) -> str:
        return "use_luominest_skill"

    @property
    def description(self) -> str:
        return (
            "应用指定技能处理用户任务。传入 skill_id 与用户任务描述 input，"
            "返回「技能指令 + 任务」的拼接文本；随后应严格按照技能指令的流程与规范完成任务。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "skill_id": {
                    "type": "string",
                    "description": "技能 id（kebab-case，如 travel-planner）",
                },
                "input": {
                    "type": "string",
                    "description": "用户任务描述（将交给技能处理的具体需求）",
                },
            },
            "required": ["skill_id", "input"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        skill_id = str(arguments.get("skill_id") or "").strip()
        user_input = str(arguments.get("input") or "").strip()
        if not skill_id:
            return ToolResult.fail("缺少 skill_id 参数")
        if not user_input:
            return ToolResult.fail("缺少 input 参数")

        try:
            registry = _get_registry()
        except Exception as e:
            logger.error(f"[SkillsTools] 导入技能注册表失败: {e}")
            return ToolResult.fail(f"技能系统不可用: {e}")

        skill = registry.get(skill_id)
        if skill is None:
            return ToolResult.fail(f"技能不存在: {skill_id}")
        if not registry.is_enabled(skill_id) or not skill.is_active:
            return ToolResult.fail(f"技能已禁用: {skill_id}")
        if not skill.body:
            return ToolResult.fail(f"技能内容为空: {skill_id}")

        combined = (
            f"【技能指令：{skill.name}（{skill.id} v{skill.version}）】\n"
            f"{skill.body}\n\n"
            f"【用户任务】\n{user_input}\n\n"
            f"请严格按照上述技能指令的流程与规范，完成用户任务。"
        )
        logger.info(f"[SkillsTools] use_luominest_skill: {skill_id}, input_len={len(user_input)}")
        return ToolResult.ok(
            combined,
            metadata={"skill_id": skill.id, "name": skill.name, "version": skill.version},
        )


def get_luominest_skills_tools() -> list[ToolBase]:
    """返回三个技能工具实例（供 app_factory 批量注册）。"""
    return [
        LuomiNestListSkillsTool(),
        LuomiNestReadSkillTool(),
        LuomiNestUseSkillTool(),
    ]
