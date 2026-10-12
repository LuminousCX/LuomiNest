"""dispatch 派发网关中间件（辰汐生态打通 W3，分册 10 §18.3 派发自律三关）。

职责链（三关中的第二、三关；第一关 SYSTEM 自律已由 W2 注入提示词完成）：
- 第二关 网关轻量检测：task 去空白后 < DISPATCH_TASK_MIN_CHARS（默认 6）字符，
  或既不含工具动词又无检索意图特征 → 丢弃派发（不发事件、垫话照常、计数留痕）；
- 第三关 防环兜底：单次会话轮派发执行深度上限（TASK_DISPATCH_MAX_DEPTH=10）
  + task 文本指纹判重（同轮重复 task 直接丢弃）。

执行链：读取 ctx.state 挂点（TASK_DISPATCH_DETECTED_KEY，W2 解析层写入的
phase="detected" 事件）→ 过滤 → 生成 task_id → 下发 phase="start" → 复用
subagent_executor（完整 AgentRunner 管道：PermissionGate/LoopGuard 等安全中间件
全部在位，不绕开权限闸门）以慢脑 provider/model 跑工具循环 → phase="done"
（summary=结果摘要，完整结果按 TaskResultDispatcher 惯例回填来源会话）或
phase="error"（无慢脑 / 执行异常，不抛出中断流）。

挂载位置（见 tools/orchestrator.build_default_pipeline）：仅 scene="chat" 且
is_stream=True 时挂载，位置在 SSEEmitMiddleware 之后、ToolExecutionMiddleware
之前——
- after_model 钩子在流式模型输出结束后执行，此时 W2 解析层已把 detected 事件
  写入 ctx.state 挂点，可整段读取；
- runner 在 after_model 返回后立即排水 sse buffer（run_stream 步骤边界），
  本中间件经 ctx.sse_emitter 下发的 start/done/error 事件可达前端；
- after_agent 不可用：runner 在 finally 中先把 sse_emitter 恢复为原值再执行
  after_agent，且循环结束后 buffer 不再排水，事件会丢失。
"""
from __future__ import annotations

import hashlib
from typing import Any
from uuid import uuid4

from loguru import logger

from app.core.agents.middleware.base import AgentContext, AgentMiddleware
from app.core.tags.definitions import (
    TASK_DISPATCH_CONSUMED_KEY,
    TASK_DISPATCH_DEPTH_KEY,
    TASK_DISPATCH_DETECTED_KEY,
    TASK_DISPATCH_FINGERPRINTS_KEY,
    TASK_DISPATCH_MAX_DEPTH,
    TASK_DISPATCH_STATS_KEY,
)
from app.core.utils import sse_data

# 结果回填的元信息标记（对齐 task_result_dispatcher 的 "[定时任务]" 惯例）
_DISPATCH_RESULT_PREFIX = "[派发任务]"
# 慢脑任务附加上下文里携带的来源会话快照长度上限（字符）
_CONTEXT_SNIPPET_MAX = 400
# done 事件 summary 摘要长度上限（一段话口径）
_SUMMARY_MAX = 200


# ──────────────────────────────────────────────────────────────
# 第二关：网关轻量检测启发式
# ──────────────────────────────────────────────────────────────


def _csv_set(raw: str) -> frozenset[str]:
    """逗号分隔 CSV 配置 → 去空白集合（空项忽略）。"""
    return frozenset(item.strip() for item in (raw or "").split(",") if item.strip())


def _load_heuristic_tables() -> tuple[int, frozenset[str], frozenset[str]]:
    """读取阈值与动词/意图特征表（分册 10 §18.3：均为消费端配置项）。"""
    from app.core.config import settings

    min_chars = int(getattr(settings, "DISPATCH_TASK_MIN_CHARS", 6) or 6)
    verbs = _csv_set(getattr(settings, "DISPATCH_TOOL_VERBS", "") or "")
    markers = _csv_set(getattr(settings, "DISPATCH_INTENT_MARKERS", "") or "")
    return max(1, min_chars), verbs, markers


def heuristic_filter(task: str) -> str | None:
    """第二关两道启发式。返回丢弃原因（"short"/"intent"）；None = 放行。

    - 长度关：task 去空白后 < 配置阈值 → 判空派发，丢弃；
    - 意图关：不含工具动词且无检索意图特征 → 丢弃。
    纯启发式、不报错不抛异常（快脑直接作答，垫话照常）。
    """
    min_chars, verbs, markers = _load_heuristic_tables()
    compact = "".join(str(task or "").split())
    if len(compact) < min_chars:
        return "short"
    for verb in verbs:
        if verb and verb in compact:
            return None
    for marker in markers:
        if marker and marker in compact:
            return None
    return "intent"


def task_fingerprint(task: str) -> str:
    """task 文本指纹（第三关判重）：去空白 + 小写归一后取 sha1 前 16 位。"""
    normalized = "".join(str(task or "").split()).lower()
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]


def _bump_stats(ctx: AgentContext, key: str) -> None:
    """派发计数留痕（ctx.state，随回合结束消亡；仅内部诊断与测试可见）。"""
    stats = ctx.state.setdefault(TASK_DISPATCH_STATS_KEY, {})
    if isinstance(stats, dict):
        stats[key] = stats.get(key, 0) + 1


# ──────────────────────────────────────────────────────────────
# 慢脑解析（槽位不绑定模型：model_config.slow_brain → reasoner 槽 → 云端默认）
# ──────────────────────────────────────────────────────────────


def resolve_slow_brain() -> dict | None:
    """按既定顺序解析慢脑 (provider, model)，未配置返回 None。

    1. model_config.slow_brain（settings.SLOW_BRAIN，"provider_id/model_id"，
       model_id 自身可含 "/" 故按首个 "/" 切分；无 "/" 时视为 model 名、
       provider 用默认——与 fast_brain 同一寻址约定）；
    2. 既有 reasoner 槽（adapter.get_reasoner_provider，专业模式推理模型配置）；
    3. 云端 CloudProxy 默认：云令牌已注入且 routingMode=all 时，provider/model
       均交由 adapter 的云路由钩子按云端目录解析（provider/model 返回 None，
       不在本层复刻云目录匹配逻辑）。

    代码不出现任何具体模型名（硬约束 3）。任何一步 provider 不存在按未配置
    顺延（优雅降级），三处都没有 → None（调用方下发 error 事件，不抛异常）。
    """
    from app.core.config import settings
    from app.runtime.provider.llm.adapter import llm_adapter

    # 1) model_config.slow_brain
    target = (getattr(settings, "SLOW_BRAIN", "") or "").strip()
    if target:
        if "/" in target:
            provider, model = target.split("/", 1)
        else:
            provider, model = "", target
        try:
            provider_inst = llm_adapter.get_provider(provider or None)
            return {
                "provider": provider or llm_adapter.default_provider,
                "model": model or provider_inst.default_model,
                "source": "slow_brain",
            }
        except Exception as e:
            logger.warning(f"[Dispatch] slow_brain 指向的 provider 不可用，顺延 reasoner 槽: {e}")

    # 2) 既有 reasoner 槽
    try:
        reasoner = llm_adapter.get_reasoner_provider()
    except Exception as e:
        logger.debug(f"[Dispatch] reasoner 槽读取失败: {e}")
        reasoner = None
    if reasoner:
        r_provider, r_model, _temp, _maxtok, _effort = reasoner
        try:
            provider_inst = llm_adapter.get_provider(r_provider)
            return {
                "provider": r_provider,
                "model": r_model or provider_inst.default_model,
                "source": "reasoner",
            }
        except Exception as e:
            logger.warning(f"[Dispatch] reasoner 槽 provider 不可用，顺延云端默认: {e}")

    # 3) 云端 CloudProxy 默认（adapter._maybe_route_to_cloud 同款判定条件）
    try:
        from app.runtime.provider.llm.cloud_store import cloud_token_store

        snapshot = cloud_token_store.get()
        if cloud_token_store.configured and snapshot.get("routingMode") == "all":
            return {"provider": None, "model": None, "source": "cloud"}
    except Exception as e:
        logger.debug(f"[Dispatch] 云路由状态读取失败: {e}")

    return None


# ──────────────────────────────────────────────────────────────
# 中间件
# ──────────────────────────────────────────────────────────────


class DispatchMiddleware(AgentMiddleware):
    """派发网关：detected 挂点消费 → 三关过滤 → 慢脑执行 → start/done/error 下发。"""

    def __init__(self, max_depth: int = TASK_DISPATCH_MAX_DEPTH) -> None:
        self._max_depth = max_depth

    async def after_model(
        self, ctx: AgentContext, response: Any
    ) -> None:
        """流式模型输出后消费本户新增的 detected 事件（游标推进防重复消费）。"""
        if ctx.extra.get("scene", "chat") not in ("", "chat"):
            return  # 仅主对话场景派发（subagent/group 由各自管道约束）

        detected = ctx.state.get(TASK_DISPATCH_DETECTED_KEY) or []
        consumed = ctx.state.get(TASK_DISPATCH_CONSUMED_KEY, 0)
        if not isinstance(detected, list) or consumed >= len(detected):
            return
        batch = detected[consumed:]
        ctx.state[TASK_DISPATCH_CONSUMED_KEY] = len(detected)

        for item in batch:
            if not isinstance(item, dict):
                continue
            _bump_stats(ctx, "detected")
            try:
                await self._process_one(ctx, item)
            except Exception as e:
                # 派发链路任何异常都不中断主对话流（优雅降级硬条款）
                logger.error(f"[Dispatch] 派发处理异常（已降级丢弃）: {e}", exc_info=True)
                _bump_stats(ctx, "errors")

    # ── 单个派发事件处理 ──────────────────────────────────────────

    async def _process_one(self, ctx: AgentContext, item: dict[str, Any]) -> None:
        task = str(item.get("task") or "").strip()
        if not task:
            _bump_stats(ctx, "dropped_short")
            return

        # 第二关：启发式过滤（丢弃不发事件、垫话照常、计数留痕）
        reason = heuristic_filter(task)
        if reason:
            _bump_stats(ctx, f"dropped_{reason}")
            logger.info(f"[Dispatch] 第二关丢弃派发（{reason}）: {task[:60]!r}")
            return

        # 第三关：task 指纹判重（同轮重复 task 直接丢弃）
        fingerprints = ctx.state.setdefault(TASK_DISPATCH_FINGERPRINTS_KEY, set())
        fp = task_fingerprint(task)
        if isinstance(fingerprints, set) and fp in fingerprints:
            _bump_stats(ctx, "dropped_dup")
            logger.info(f"[Dispatch] 第三关丢弃重复派发（指纹 {fp}）: {task[:60]!r}")
            return

        # 第三关：单轮派发深度上限
        depth = ctx.state.get(TASK_DISPATCH_DEPTH_KEY, 0)
        if depth >= self._max_depth:
            _bump_stats(ctx, "dropped_limit")
            logger.warning(
                f"[Dispatch] 第三关熔断：本轮派发已达上限 {self._max_depth}，"
                f"丢弃: {task[:60]!r}"
            )
            return

        # 慢脑解析：三处都没有 → 下发 error（summary 说明未配置慢脑），不抛异常
        slow = resolve_slow_brain()
        if slow is None:
            _bump_stats(ctx, "errors")
            await self._emit(
                ctx, task, "error", None,
                "未配置慢脑模型（model_config.slow_brain / 推理模型 / 云端均不可用），无法执行该任务。",
            )
            return

        if isinstance(fingerprints, set):
            fingerprints.add(fp)
        ctx.state[TASK_DISPATCH_DEPTH_KEY] = depth + 1
        _bump_stats(ctx, "executed")

        task_id = f"dispatch_{uuid4().hex[:12]}"
        await self._emit(ctx, task, "start", task_id, None)

        result = await self._run_slow_brain(ctx, task, slow)
        if result is None:
            _bump_stats(ctx, "errors")
            await self._emit(ctx, task, "error", task_id, "任务执行失败，请稍后重试或直接让助手处理。")
            return

        summary = self._summarize(result)
        await self._emit(ctx, task, "done", task_id, summary)
        await self._backfill_result(ctx, task_id, task, result)

    # ── 慢脑执行（复用既有子 Agent 路径，安全中间件全部在位）──────────

    async def _run_slow_brain(self, ctx: AgentContext, task: str, slow: dict) -> str | None:
        """以慢脑 provider/model 跑完整工具循环；失败返回 None（不抛出）。

        复用 subagent_executor（AgentRunner.run_non_stream + scene=subagent 管道）：
        PermissionGate / LoopGuard / SubagentCancel / UsageTrack 等既有安全中间件
        全部生效，工具在慢脑侧正常注入；快脑零原生工具拦截按 ctx 的 provider/model
        判定，慢脑寻址不受影响。
        """
        from app.core.agents.subagent_executor import subagent_executor

        try:
            result = await subagent_executor.execute(
                task=task,
                context=self._context_snapshot(ctx),
                depth=0,
                provider=slow.get("provider"),
                model=slow.get("model"),
                event_callback=None,  # 过程事件本期不下发，仅 start/done/error 三事件
                task_id=None,  # 不进全局任务注册表：生命周期随本回合 SSE 链路
            )
            return result or None
        except Exception as e:
            logger.error(f"[Dispatch] 慢脑执行异常: {e}", exc_info=True)
            return None

    @staticmethod
    def _context_snapshot(ctx: AgentContext) -> str:
        """必要上下文快照：来源会话最近一条 user 消息节选（慢脑无父对话历史）。"""
        for msg in reversed(ctx.messages):
            if not isinstance(msg, dict) or msg.get("role") != "user":
                continue
            content = msg.get("content")
            if isinstance(content, str) and content.strip():
                text = content.strip()
                if len(text) > _CONTEXT_SNIPPET_MAX:
                    text = text[:_CONTEXT_SNIPPET_MAX] + "…"
                return f"来源会话用户最近消息：{text}"
            break  # 多模态 content parts：W3 不做快照，保持空上下文
        return ""

    @staticmethod
    def _summarize(result: str) -> str:
        """结果一段话摘要（done 事件 summary 字段；换行折叠、截断到上限）。"""
        text = " ".join(str(result or "").split())
        if len(text) > _SUMMARY_MAX:
            text = text[:_SUMMARY_MAX] + "…"
        return text

    # ── 结果回填（下轮可见）────────────────────────────────────────

    async def _backfill_result(
        self, ctx: AgentContext, task_id: str, task: str, result: str,
    ) -> None:
        """完整结果按 TaskResultDispatcher 惯例回填来源会话（assistant 消息）。

        载体：conversation_store.append_message_async 追加一条带
        "[派发任务]《任务》" 前缀的 assistant 消息（metadata 携带
        task_dispatch.task_id/phase），下一轮会话从库加载即可见。
        conv_id 缺失（/chat/completions 等无会话来源）时跳过，结果仅随事件下发。
        """
        conv_id = str(ctx.extra.get("conv_id") or "").strip()
        if not conv_id:
            logger.debug("[Dispatch] 无来源会话（conv_id 为空），结果不回填，仅随事件下发")
            return
        try:
            from app.infrastructure.database.conversation_store import conversation_store

            title = task if len(task) <= 40 else task[:40] + "…"
            message = {
                "role": "assistant",
                "content": f"{_DISPATCH_RESULT_PREFIX}《{title}》执行完成：\n{result}",
                "id": str(uuid4()),
                "model": "task-dispatch",
                "task_dispatch": {"task_id": task_id, "task": task, "phase": "done"},
            }
            appended = await conversation_store.append_message_async(conv_id, message)
            if appended:
                logger.info(f"[Dispatch] 任务 {task_id} 结果已回填会话 {conv_id}")
            else:
                logger.warning(f"[Dispatch] 会话 {conv_id} 不存在，任务 {task_id} 结果未回填")
        except Exception as e:
            # 回填失败不影响事件下发（结果已在 done 事件 summary 中可见）
            logger.warning(f"[Dispatch] 结果回填失败: {e}", exc_info=True)

    # ── 事件下发 ──────────────────────────────────────────────────

    async def _emit(
        self,
        ctx: AgentContext,
        task: str,
        phase: str,
        task_id: str | None,
        summary: str | None,
    ) -> None:
        """下发 task_dispatch SSE 事件（phase=start/done/error；detected 永不下发）。

        无 sse_emitter（异常路径）时静默跳过；发射失败仅告警不中断。
        """
        if not ctx.sse_emitter:
            return
        try:
            from app.schemas.chat import ChatStreamChunk

            chunk = ChatStreamChunk(
                id=ctx.state.get("chat_id", ""),
                model=ctx.state.get("model", ""),
                provider=ctx.state.get("provider", ""),
                task_dispatch={
                    "task": task,
                    "phase": phase,
                    "task_id": task_id,
                    "summary": summary,
                },
                iteration=ctx.iteration,
            )
            await ctx.sse_emitter(sse_data(chunk))
        except Exception as e:
            logger.warning(f"[Dispatch] task_dispatch {phase} 事件发射失败: {e}")


# ──────────────────────────────────────────────────────────────
# 快脑零原生工具拦截（D3 口径，W3 补 W2 挂账）
# ──────────────────────────────────────────────────────────────


def is_fast_brain_ctx(ctx: AgentContext) -> bool:
    """判断当前执行上下文的会话模型是否命中快脑寻址（供工具注入面调用）。"""
    try:
        from app.services.context_service import ContextService

        return ContextService.is_fast_brain_model(
            ctx.state.get("provider"), ctx.state.get("model"),
        )
    except Exception:
        return False


# 系统提示中长尾工具摘要块（_select_tools_for_turn 注入），快脑会话整块剥除，
# 避免文本协议之外诱导快脑发起原生工具调用
_TOOL_INDEX_BLOCK_RE = None


def strip_tool_index_block(text: str) -> str:
    """剥除系统消息里的 <tool_index>…</tool_index> 长尾摘要块（快脑专用）。"""
    global _TOOL_INDEX_BLOCK_RE
    if _TOOL_INDEX_BLOCK_RE is None:
        import re

        _TOOL_INDEX_BLOCK_RE = re.compile(r"<tool_index>.*?</tool_index>", re.DOTALL)
    return _TOOL_INDEX_BLOCK_RE.sub("", text)


def apply_fast_brain_zero_tools(ctx: AgentContext) -> bool:
    """快脑会话清空原生工具注入面（D3：快脑只走文本标签协议）。

    返回是否发生了清空（供日志/测试）。处理三件事：
    1. ctx.tools 置 None（LLM 请求不带任何原生工具）；
    2. 清掉探索收获缓存（防 before_model 动态加回）；
    3. 剥除系统提示中的 <tool_index> 长尾摘要块。
    """
    changed = bool(ctx.tools)
    ctx.tools = None
    ctx.state.pop("dynamic_tool_schemas", None)
    for msg in ctx.messages:
        if isinstance(msg, dict) and msg.get("role") == "system":
            content = msg.get("content")
            if isinstance(content, str) and "<tool_index>" in content:
                msg["content"] = strip_tool_index_block(content)
                changed = True
    return changed
