"""LuomiNest 显式记忆操作工具集（Mem0 / Claude Code 范式）。

供 Agent 在对话回路中主动操作长期记忆，实现「记得住你」的核心陪伴能力：
- memory_add: 主动记住用户的重要事实、偏好、习惯或约束
- memory_forget: 主动遗忘用户要求删除或已过期的记忆
- memory_update: 修正已发生变更的用户事实
- memory_search: 主动语义检索长期记忆（增强版，支持分类与置信度过滤）

所有操作均与 SQLite 单库持久化与向量索引联动（remember_fact / forget_facts）。
"""
from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from app.core.agents.memory_access import (
    MEMORY_ACCESS_NONE,
    get_luominest_memory_access,
)
from app.core.domain_policy import MAIN_AGENT_ID, is_main_agent_id
from app.core.tools.registry import ToolBase, ToolResult
from app.engines.memory.models import FactItem, FACT_CATEGORIES


def _get_engine(agent_id: str | None = None):
    """获取目标记忆引擎实例。"""
    from app.engines.memory import get_memory_engine, get_track_engine
    from app.core.domain_policy import TRACK_OWNER

    target_id = agent_id or MAIN_AGENT_ID
    if is_main_agent_id(target_id):
        return get_track_engine(TRACK_OWNER)
    return get_memory_engine(target_id)


class MemoryAddTool(ToolBase):
    """显式新增记忆工具（Mem0 范式）。"""

    tier: str = "core"
    scope: str = "shared"

    @property
    def name(self) -> str:
        return "memory_add"

    @property
    def description(self) -> str:
        return (
            "主动记录用户的长期记忆、偏好、习惯、关键事实或重要约定（Mem0 范式）。"
            "当用户主动透露「我喜欢/不喜欢...」「记住我的...」「我正在做...」或提供关键个人信息时使用。"
            "成功记录后，该记忆将沉淀到长期记忆库，并在后续对话中自动或按需检索呈现。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "要记住的事实或偏好描述，用客观简洁的陈述句（如「用户对海鲜过敏」「用户喜欢喝美式咖啡」）。",
                },
                "category": {
                    "type": "string",
                    "enum": list(FACT_CATEGORIES),
                    "description": (
                        "记忆类别：preference(喜好/习惯), knowledge(知识/技能), "
                        "context(背景/现状), goal(目标/计划), behavior(行为模式), correction(纠错)"
                    ),
                    "default": "preference",
                },
                "pinned": {
                    "type": "boolean",
                    "description": "是否置顶该记忆（生日、过敏源、极其重要的纪念日等建议设为 true，确保永不被预算裁剪）。",
                    "default": False,
                },
            },
            "required": ["content"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        content = (arguments.get("content") or "").strip()
        if not content:
            return ToolResult.fail("缺少 content 参数，无法记录空记忆")

        category = arguments.get("category", "preference")
        if category not in FACT_CATEGORIES:
            category = "preference"
        pinned = bool(arguments.get("pinned", False))

        try:
            engine = _get_engine()
            fact = FactItem(
                content=content[:500],
                category=category,
                confidence=0.9,
                source="agent_tool",
                pinned=pinned,
            )
            # 在写锁保护下写入 SQLite 并构建向量索引
            async with engine.write_lock:
                await engine.remember_fact(fact)

            logger.info(f"[MemoryAddTool] Added memory: fact_id={fact.id}, category={category}, pinned={pinned}")
            pin_hint = "（已置顶）" if pinned else ""
            return ToolResult.ok(
                f"已成功记住：[{category}] {content} {pin_hint}（事实ID: {fact.id}）",
                metadata={"fact_id": fact.id, "category": category, "pinned": pinned},
            )
        except Exception as e:
            logger.error(f"[MemoryAddTool] Failed to add memory: {e}", exc_info=True)
            return ToolResult.fail(f"记录记忆失败: {e}")


class MemoryForgetTool(ToolBase):
    """显式遗忘/删除记忆工具（Mem0 范式）。"""

    tier: str = "core"
    scope: str = "shared"

    @property
    def name(self) -> str:
        return "memory_forget"

    @property
    def description(self) -> str:
        return (
            "主动遗忘或删除关于某个主题的记忆，或按事实 ID 精确删除记忆。"
            "当用户要求「忘掉关于...的记忆」「不要记这个」「我不再喜欢...」时使用。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "要遗忘的主题关键词（如「猫」「吃香菜」），会模糊匹配相关事实并将其归档或标记失效。",
                },
                "fact_id": {
                    "type": "string",
                    "description": "要删除的精确事实 ID（优先于 query）。",
                },
            },
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        fact_id = (arguments.get("fact_id") or "").strip()
        query = (arguments.get("query") or "").strip().lower()

        if not fact_id and not query:
            return ToolResult.fail("请提供 query 或 fact_id 之一以指定要遗忘的记忆")

        try:
            engine = _get_engine()

            if fact_id:
                # 按 ID 精确删除事实与对应向量
                async with engine.write_lock:
                    success = await asyncio.to_thread(engine.remove_fact, fact_id)
                    if success:
                        await engine.forget_fact_vector(fact_id)

                if success:
                    return ToolResult.ok(f"已成功删除记忆（ID: {fact_id}）")
                return ToolResult.fail(f"未找到事实 ID 为 {fact_id} 的记忆")

            # 按 query 模糊遗忘
            def _apply_forget(data) -> int:
                count = 0
                for f in list(data.facts):
                    if query in f.content.lower() and f.is_latest:
                        f.is_latest = False
                        f.confidence = 0.05
                        count += 1
                return count

            async with engine.write_lock:
                removed_count = await asyncio.to_thread(engine.forget_facts, _apply_forget)

            if removed_count > 0:
                logger.info(f"[MemoryForgetTool] Forgot {removed_count} facts matching '{query}'")
                return ToolResult.ok(f"已遗忘关于「{query}」的记忆（共 {removed_count} 条相关事实已归档失效）")
            return ToolResult.ok(f"未找到与「{query}」相关的活跃记忆，无需遗忘。")

        except Exception as e:
            logger.error(f"[MemoryForgetTool] Failed to forget memory: {e}", exc_info=True)
            return ToolResult.fail(f"遗忘记忆失败: {e}")


class MemoryUpdateTool(ToolBase):
    """显式修正记忆工具（Mem0 范式）。"""

    tier: str = "core"
    scope: str = "shared"

    @property
    def name(self) -> str:
        return "memory_update"

    @property
    def description(self) -> str:
        return (
            "修正或更新某条既有记忆的内容或分类，维护事实版本链。"
            "当用户指出之前的记录有误或信息发生变更（如更换了工作或联系方式）时使用。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "fact_id": {
                    "type": "string",
                    "description": "要修改的事实 ID（通常先通过 memory_search 找到）。",
                },
                "content": {
                    "type": "string",
                    "description": "更新后的事实内容描述。",
                },
                "category": {
                    "type": "string",
                    "enum": list(FACT_CATEGORIES),
                    "description": "更新后的记忆分类（可选）。",
                },
            },
            "required": ["fact_id", "content"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        fact_id = (arguments.get("fact_id") or "").strip()
        content = (arguments.get("content") or "").strip()
        category = arguments.get("category")

        if not fact_id:
            return ToolResult.fail("缺少 fact_id 参数")
        if not content:
            return ToolResult.fail("缺少 content 参数")

        try:
            engine = _get_engine()
            async with engine.write_lock:
                success = await asyncio.to_thread(
                    engine.update_fact, fact_id, content=content, category=category, confidence=0.9
                )
                if success:
                    # 重新获取更新后的事实并同步向量
                    memory_data = await asyncio.to_thread(engine.load_data)
                    updated_fact = next((f for f in memory_data.facts if f.id == fact_id), None)
                    if updated_fact:
                        await engine.sync_fact_vector(updated_fact)

            if success:
                return ToolResult.ok(f"记忆已更新（ID: {fact_id}）：{content}")
            return ToolResult.fail(f"未找到事实 ID 为 {fact_id} 的记忆")
        except Exception as e:
            logger.error(f"[MemoryUpdateTool] Failed to update memory: {e}", exc_info=True)
            return ToolResult.fail(f"更新记忆失败: {e}")
