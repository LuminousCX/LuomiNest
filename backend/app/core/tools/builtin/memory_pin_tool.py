"""LuomiNest 记忆置顶工具（W5-2：关键信息 pin/unpin，陪伴场景核心）。

置顶事实在注入时绕过置信度与过期闸门并恒排最前（生日、纪念日、过敏源等
关键信息不因预算截断而丢失），且在 MAX_FACTS 挤出时受保护（W5-6）。
逻辑与 HTTP 端点 POST /memory/facts/{fact_id}/pin 完全同款：
engine.set_fact_pinned（store 锁内原子改写）+ 引擎写锁串行化。
"""
from __future__ import annotations

from typing import Any

from loguru import logger

from app.core.tools.registry import ToolBase, ToolResult


class MemoryPinTool(ToolBase):
    """对已有记忆事实置顶 / 取消置顶的工具。"""

    tier: str = "core"
    scope: str = "shared"

    @property
    def name(self) -> str:
        return "memory_pin"

    @property
    def description(self) -> str:
        return (
            "置顶或取消置顶一条已有记忆（先通过 memory_search 找到事实ID）。"
            "置顶的记忆在上下文注入时永远优先且不会被裁剪，适用于生日、纪念日、"
            "过敏源等绝对不能遗忘的关键信息；也可用于取消之前的置顶。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "fact_id": {
                    "type": "string",
                    "description": "要操作的事实 ID（通常先通过 memory_search 获取）",
                },
                "pinned": {
                    "type": "boolean",
                    "description": "true=置顶（默认），false=取消置顶",
                    "default": True,
                },
            },
            "required": ["fact_id"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        fact_id = str(arguments.get("fact_id") or "").strip()
        if not fact_id:
            return ToolResult.fail("缺少 fact_id 参数")
        pinned = bool(arguments.get("pinned", True))

        try:
            from .memory_tools import _get_engine

            engine = _get_engine()
        except Exception as e:
            logger.error(f"[MemoryPin] 获取记忆引擎失败: {e}", exc_info=True)
            return ToolResult.fail(f"记忆引擎不可用: {e}")

        try:
            import asyncio

            async with engine.write_lock:
                changed = await asyncio.to_thread(engine.set_fact_pinned, fact_id, pinned)
            if not changed:
                return ToolResult.fail(f"未找到事实 ID 为 {fact_id} 的记忆")

            # 回读事实内容用于确认展示（找不到不阻断，pin 已生效）
            data = await asyncio.to_thread(engine.load_data)
            fact = next((f for f in data.facts if f.id == fact_id), None)
            content = fact.content if fact is not None else ""
            action = "已置顶" if pinned else "已取消置顶"
            logger.info(f"[MemoryPin] {action}: fact_id={fact_id}")
            return ToolResult.ok(
                f"{action}记忆（ID: {fact_id}）：{content or '（内容未知）'}",
                metadata={"fact_id": fact_id, "pinned": pinned},
            )
        except Exception as e:
            logger.error(f"[MemoryPin] 操作失败: {e}", exc_info=True)
            return ToolResult.fail(f"置顶操作失败: {e}")
