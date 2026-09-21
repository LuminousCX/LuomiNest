"""LuomiNest 记忆时间线查询工具（W5-2 情景记忆=memory_daily 时间线）。

供对话回路 Agent 主动回溯某日/最近 N 天的经历时间线与事实轨迹（Mem0 / Letta
的 episodic memory 检索范式）。工作流内部已有 memory.get_daily/memory.list_dailies
（tool_domains/memory_tools.py），本工具按对话回路工具协议桥接同一引擎调用，
不复制存取逻辑：

- memory_get_daily(date?, days?, conversation_id?) →
  engine.list_dailies() 解析日期窗口 → engine.load_daily(date) 逐日读取
  （store 层按时间升序返回当日记录）→ 附按时间倒序的最近事实清单。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from zoneinfo import ZoneInfo

from loguru import logger

from app.core.tools.registry import ToolBase, ToolResult
from app.engines.memory.models import FACT_CATEGORY_LABELS

# 每日记录展示时区（与 store.MemoryStore._TZ 一致）
_TZ = ZoneInfo("Asia/Shanghai")

_DATE_RE = __import__("re").compile(r"^\d{4}-\d{2}-\d{2}$")


class MemoryGetDailyTool(ToolBase):
    """查询某日 / 最近 N 天的记忆时间线工具。"""

    tier: str = "core"
    scope: str = "shared"

    @property
    def name(self) -> str:
        return "memory_get_daily"

    @property
    def description(self) -> str:
        return (
            "查询记忆库的每日时间线（情景记忆），回顾某一天或最近几天发生了什么、"
            "聊过什么、做过什么，并附最近记录的事实清单。"
            "适用于：1. 用户问「我们昨天/前几天聊了什么」「帮我回顾一下今天的事」；"
            "2. 需要回忆某段时期共同经历的场景。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "起始日期（YYYY-MM-DD，默认今天）。窗口为该日期起往过去回溯 days 天",
                },
                "days": {
                    "type": "integer",
                    "description": "回溯天数（默认 1 = 只看 date 当天；最大 30）",
                    "default": 1,
                },
                "conversation_id": {
                    "type": "string",
                    "description": "限定某个对话的每日记录（可选，默认查全部对话）",
                },
            },
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        date_arg = str(arguments.get("date") or "").strip()
        try:
            days = int(arguments.get("days", 1) or 1)
        except (TypeError, ValueError):
            days = 1
        days = max(1, min(days, 30))
        conversation_id = str(arguments.get("conversation_id") or "").strip() or None

        if date_arg and not _DATE_RE.match(date_arg):
            return ToolResult.fail(f"date 格式应为 YYYY-MM-DD，收到: {date_arg!r}")

        try:
            from .memory_tools import _get_engine

            engine = _get_engine()
        except Exception as e:
            logger.error(f"[MemoryGetDaily] 获取记忆引擎失败: {e}", exc_info=True)
            return ToolResult.fail(f"记忆引擎不可用: {e}")

        try:
            # 解析日期窗口：有记录日期（升序）∩ [date-(days-1), date]
            recorded = engine.list_dailies()
            if date_arg:
                anchor = date_arg
            else:
                anchor = datetime.now(_TZ).strftime("%Y-%m-%d")
            window_dates = self._resolve_window_dates(recorded, anchor, days)

            # 逐日读取（store.load_daily 内部按 conversation_id, id 升序 = 时间序）
            sections: list[str] = []
            for d in window_dates:
                content = engine.load_daily(d, conversation_id)
                if content.strip():
                    sections.append(content.strip())

            # 附最近事实清单（按创建时间倒序，语义记忆轨迹）
            facts = engine.get_facts()
            facts_sorted = sorted(facts, key=lambda f: f.created_at, reverse=True)[:20]

            output_parts: list[str] = []
            if sections:
                output_parts.append("【每日时间线】\n" + "\n\n".join(sections))
            else:
                output_parts.append(f"【每日时间线】{anchor} 起回溯 {days} 天内没有每日记录。")

            if facts_sorted:
                fact_lines = [
                    f"- [{f.created_at[:16].replace('T', ' ')}] "
                    f"[{FACT_CATEGORY_LABELS.get(f.category, f.category)}|{f.confidence:.1f}]"
                    f"{' [置顶]' if f.pinned else ''} {f.content}"
                    for f in facts_sorted
                ]
                output_parts.append(
                    f"【最近记忆事实（按时间倒序，至多 20 条）】\n" + "\n".join(fact_lines)
                )

            return ToolResult.ok(
                "\n\n".join(output_parts),
                metadata={
                    "date": anchor,
                    "days": days,
                    "dates_with_records": window_dates,
                    "fact_count": len(facts_sorted),
                },
            )
        except Exception as e:
            logger.error(f"[MemoryGetDaily] 查询时间线失败: {e}", exc_info=True)
            return ToolResult.fail(f"查询时间线失败: {e}")

    @staticmethod
    def _resolve_window_dates(recorded: list[str], anchor: str, days: int) -> list[str]:
        """日期窗口解析：锚点日起往过去 days 个自然日，与有记录日期取交集（倒序返回）。

        日期以字符串 ISO 比较为准（store 侧保证 YYYY-MM-DD）；非法记录日期跳过。
        """
        try:
            anchor_dt = datetime.strptime(anchor, "%Y-%m-%d")
        except ValueError:
            return []
        window: set[str] = set()
        for offset in range(days):
            window.add((anchor_dt - timedelta(days=offset)).strftime("%Y-%m-%d"))
        return sorted((d for d in recorded if d in window), reverse=True)
