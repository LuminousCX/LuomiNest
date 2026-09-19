"""晨间简报 / 主动关心服务（陪伴定位：记忆的消费形态）。

把记忆系统的"记录"变成"关心"：基于每日记忆、置顶/高置信事实与待办
定时任务，用 LLM 合成一段有温度的晨间问候（LLM 失败时降级为模板拼接，
保证永远有产出）。

生成策略（桌面应用形态下最可靠的方式）：
- 懒生成 + 当日缓存：GET /memory/briefing 时若当日尚未生成且已过晨间时点
  （Settings.PROACTIVE_BRIEFING_HOUR，默认 6 点）则现场生成并缓存于
  config_items；前端在应用启动/回到前台时拉取展示。
- POST /memory/briefing/refresh 强制重新生成。
- 说明：真正的"主动推送"依赖 avatar_drive WS 通道成熟后接入；当前为
  拉取式，不引入额外调度器任务。

隐私：全部数据来自本地记忆库与本地调度器，不经云端。
"""
import asyncio
from datetime import datetime, timedelta

from loguru import logger

from app.core.config import settings
from app.core.utils import utc_now, utc_now_dt

# 简报缓存键前缀（config_items）：proactive.briefing.{YYYY-MM-DD}
_BRIEFING_KEY_PREFIX = "proactive.briefing."
# 简报时效：超过 20 小时视为过期（跨天兜底）
_BRIEFING_TTL_HOURS = 20


class ProactiveCareService:
    """晨间简报与主动关心。"""

    def __init__(self) -> None:
        self._inflight: asyncio.Task | None = None

    # ── 数据收集 ──────────────────────────────────────────────────

    def _collect_context(self, agent_id: str | None) -> dict:
        """从本地记忆库与调度器收集简报素材（全部同步 SQLite，调用方放线程池）。"""
        from app.engines.memory import get_memory_engine

        engine = get_memory_engine(agent_id)
        data = engine.load_data()
        now = utc_now_dt()

        # 置顶事实（最高优先）+ 其余高置信事实（截断）
        pinned = [f.content for f in data.facts if f.is_latest and f.pinned]
        others = [
            f.content
            for f in sorted(
                (f for f in data.facts if f.is_latest and not f.pinned),
                key=lambda f: f.confidence,
                reverse=True,
            )
            if f.confidence >= 0.7
        ][:8]

        # 近两日每日记忆（昨天 + 今天）
        daily: list[str] = []
        for offset in (1, 0):
            day = (now - timedelta(days=offset)).strftime("%Y-%m-%d")
            content = engine.load_daily(date=day)
            if content and content.strip():
                daily.append(f"[{day}] {content.strip()[:600]}")

        # 待办定时任务（运行中调度器的活跃任务 + 数据库持久化任务）
        tasks: list[str] = []
        try:
            from app.core.scheduler.manager import luominest_scheduler

            for t in luominest_scheduler.list_tasks():
                status = getattr(t, "status", "")
                if status in ("completed", "removed"):
                    continue
                name = getattr(t, "name", "") or ""
                if name:
                    tasks.append(name)
        except Exception as e:
            logger.debug(f"[Proactive] 调度器任务收集失败（忽略）: {e}")
        tasks = tasks[:5]

        return {
            "now": now,
            "pinned": pinned[:5],
            "facts": others,
            "daily": daily,
            "tasks": tasks,
        }

    # ── 生成 ─────────────────────────────────────────────────────

    async def get_briefing(self, agent_id: str | None = None) -> dict:
        """获取当日简报：当日已生成直接返回缓存；否则懒生成。"""
        today = utc_now_dt().strftime("%Y-%m-%d")
        cached = self._load_cached(today)
        if cached is not None:
            return {**cached, "cached": True}

        return await self.generate_briefing(agent_id)

    async def refresh_briefing(self, agent_id: str | None = None) -> dict:
        """强制重新生成当日简报。"""
        return await self.generate_briefing(agent_id)

    async def generate_briefing(self, agent_id: str | None = None) -> dict:
        now = utc_now_dt()
        today = now.strftime("%Y-%m-%d")
        # 收集素材放线程池（同步 SQLite）
        ctx = await asyncio.to_thread(self._collect_context, agent_id)
        content = await self._compose(agent_id, ctx)
        payload = {
            "date": today,
            "content": content,
            "generated_at": utc_now(),
            "sources": {
                "pinned_count": len(ctx["pinned"]),
                "facts_count": len(ctx["facts"]),
                "daily_count": len(ctx["daily"]),
                "tasks_count": len(ctx["tasks"]),
            },
        }
        self._save_cached(payload)
        return {**payload, "cached": False}

    async def _compose(self, agent_id: str | None, ctx: dict) -> str:
        """LLM 合成晨间问候；失败降级为模板拼接。"""
        now: datetime = ctx["now"]
        weekday = "一二三四五六日"[now.weekday()]
        context_lines = self._render_context(ctx)
        prompt = (
            "你是 LuomiNest，一个以陪伴为优先、隐私优先的桌面 AI 伙伴。"
            "今天是 {date}（周{weekday}），请基于以下来自你长期记忆的素材，"
            "写一段 80 字以内的晨间问候：语气自然温暖、像老朋友，"
            "自然地融入 1-2 条你记得的关于对方的事（不要罗列全部，不要像报告），"
            "如有待办任务可轻轻提一句。不要使用 markdown 标题，直接输出问候正文。\n\n"
            "记忆素材：\n{context}"
        ).format(date=now.strftime("%Y-%m-%d"), weekday=weekday, context=context_lines)

        try:
            from app.runtime.provider.llm.adapter import llm_adapter
            from app.core.utils import extract_llm_text
            from app.runtime.provider.llm.types import RouteHint

            result = await llm_adapter.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=200,
                route_hint=RouteHint.CHAT,
                provider_name=None,
                model=None,
            )
            text = (extract_llm_text(result) or "").strip()
            if text:
                return text[:500]
        except Exception as e:
            logger.warning(f"[Proactive] LLM 合成简报失败，降级模板: {e}")

        return self._fallback_text(ctx)

    def _render_context(self, ctx: dict) -> str:
        lines: list[str] = []
        if ctx["pinned"]:
            lines.append("置顶（对方特别在意的事）: " + "；".join(ctx["pinned"]))
        if ctx["facts"]:
            lines.append("近期事实: " + "；".join(ctx["facts"]))
        if ctx["daily"]:
            lines.append("\n".join(ctx["daily"]))
        if ctx["tasks"]:
            lines.append("待办任务: " + "；".join(ctx["tasks"]))
        return "\n".join(lines) if lines else "（暂无记忆素材，写一段简单友好的问候即可）"

    @staticmethod
    def _fallback_text(ctx: dict) -> str:
        now: datetime = ctx["now"]
        weekday = "一二三四五六日"[now.weekday()]
        parts = [f"早上好，今天是周{weekday}。"]
        if ctx["tasks"]:
            parts.append(f"你还有 {len(ctx['tasks'])} 个待办任务，需要我帮你安排吗？")
        if ctx["pinned"]:
            parts.append(f"对了，我一直记得：{ctx['pinned'][0]}。")
        if not ctx["daily"] and not ctx["facts"] and not ctx["tasks"]:
            parts.append("今天想聊点什么吗？")
        return "".join(parts)

    # ── 缓存 ─────────────────────────────────────────────────────

    @staticmethod
    def _load_cached(date: str) -> dict | None:
        try:
            from app.infrastructure.database.config_store import luominest_config_store

            payload = luominest_config_store.get(f"{_BRIEFING_KEY_PREFIX}{date}")
            if not payload:
                return None
            generated_at = payload.get("generated_at", "")
            if generated_at:
                gen_dt = datetime.fromisoformat(generated_at)
                if utc_now_dt() - gen_dt > timedelta(hours=_BRIEFING_TTL_HOURS):
                    return None
            return payload
        except Exception as e:
            logger.debug(f"[Proactive] 读取简报缓存失败（忽略）: {e}")
            return None

    @staticmethod
    def _save_cached(payload: dict) -> None:
        try:
            from app.infrastructure.database.config_store import luominest_config_store

            luominest_config_store.set(
                f"{_BRIEFING_KEY_PREFIX}{payload.get('date', utc_now()[:10])}", payload
            )
        except Exception as e:
            logger.debug(f"[Proactive] 写入简报缓存失败（忽略）: {e}")


proactive_care_service = ProactiveCareService()
