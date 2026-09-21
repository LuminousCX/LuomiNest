"""LuomiNest 内置中间件。

基于现有 4 处工具循环（stream_chat / stream_response / subagent / group_chat）的逻辑提取，
实现 8 个内置中间件：

1. ToolFilterMiddleware: before_agent，按 disable_tools/白名单过滤工具
2. ToolExecutionMiddleware: wrap_tool_call，调用 orchestrator 执行工具 + 异常兜底
3. SpecialToolMiddleware: wrap_tool_call，转发 delegate/scheduler/collaboration 事件
4. LoopGuardMiddleware: after_model，检测 max_iterations 边界
5. SubagentCancelMiddleware: before_model，检查 cancel_event 取消信号
6. MemoryAccessMiddleware: before_agent/after_agent，设置/重置记忆访问 contextvar
7. SSEEmitMiddleware: after_model/after_tool_call，发射 ChatStreamChunk SSE 事件
8. UsageTrackMiddleware: after_agent，记录 usage_tracker
"""
from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

from loguru import logger

from app.core.utils import sse_data

from app.core.agents.middleware.base import AgentContext, AgentMiddleware
from app.runtime.provider.llm.types import LLMResponse
from app.schemas.chat import ChatStreamChunk


# ──────────────────────────────────────────────────────────────
# 1. ToolFilterMiddleware
# ──────────────────────────────────────────────────────────────


class ToolFilterMiddleware(AgentMiddleware):
    """按 disable_tools / tool_whitelist 过滤工具列表。

    对应现有逻辑：
    - chat_service.stream_chat 的 disable_tools 过滤
    - subagent_executor._get_tools_for_subagent 的 forbidden_names
    - group_chat 的 GROUP_CHAT_TOOL_WHITELIST 白名单

    W2「探索即可调用」：tool_explore/skill_explore 命中的工具 schema 由
    ToolExecutionMiddleware 收获进 ctx.state["dynamic_tool_schemas"]，本中间件
    在每轮 before_model 把它们追加进 ctx.tools 并并入白名单放行集——
    模型经探索拿到完整定义的工具，下一轮即可真正发起 function call。
    """

    async def before_agent(self, ctx: AgentContext) -> None:
        if not ctx.tools:
            return

        disable_tools = ctx.extra.get("disable_tools")
        if disable_tools:
            disable_set = set(disable_tools)
            ctx.tools = [
                t for t in ctx.tools
                if t.get("function", {}).get("name") not in disable_set
            ]

        whitelist = ctx.extra.get("tool_whitelist")
        if whitelist:
            wl_set = set(whitelist)
            ctx.tools = [
                t for t in ctx.tools
                if t.get("function", {}).get("name") in wl_set
            ]

        if ctx.tools is not None and not ctx.tools:
            ctx.tools = None
            logger.debug("[ToolFilter] 工具过滤后为空，本次以纯对话模式运行")

    async def before_model(self, ctx: AgentContext) -> None:
        # 1) 探索收获：把 tool_explore/skill_explore 返回的工具 schema 追加进可调用集
        dynamic = [
            t for t in (ctx.state.get("dynamic_tool_schemas") or [])
            if isinstance(t, dict) and t.get("function", {}).get("name")
        ]
        if dynamic:
            existing = {t.get("function", {}).get("name") for t in (ctx.tools or [])}
            added = [t for t in dynamic if t["function"]["name"] not in existing]
            if added:
                ctx.tools = (ctx.tools or []) + added
                logger.info(
                    f"[ToolFilter] 探索发现的工具已加入可调用集: "
                    f"{[t['function']['name'] for t in added]}"
                )

        # 2) 白名单放行集 = 静态白名单 ∪ 探索发现的工具名（每轮重过滤，NORMAL 模式生效）
        whitelist = ctx.extra.get("tool_whitelist")
        if whitelist and ctx.tools:
            dynamic_names = {t["function"]["name"] for t in dynamic}
            allowed = set(whitelist) | dynamic_names
            ctx.tools = [
                t for t in ctx.tools
                if t.get("function", {}).get("name") in allowed
            ]


# ──────────────────────────────────────────────────────────────
# 1.5 ContextTrimMiddleware（W2-4 工具循环内逐轮兜底裁剪）
# ──────────────────────────────────────────────────────────────


class ContextTrimMiddleware(AgentMiddleware):
    """工具循环内每轮 LLM 调用前检查 token 占用，超阈值时按「user 消息边界」
    从最旧处丢弃整轮历史（assistant 与其 tool 结果成对保留，避免上游校验失败）。

    进入 runner 前 ContextManager 的压缩只在回合开始执行一次；长工具循环中
    assistant/tool 消息持续增长没有兜底（W2-4 缺口），本中间件填补该缺口。
    裁剪只重赋 ctx.messages，不触碰调用方的原始列表。
    """

    async def before_model(self, ctx: AgentContext) -> None:
        try:
            from app.core.config import settings
            if not settings.LLM_CONTEXT_TRIM_ENABLED:
                return
            window = self._resolve_window()
            if window <= 0:
                return
            used = self._estimate_tokens(ctx.messages)
            trigger = window * settings.LLM_CONTEXT_TRIM_THRESHOLD
            if used <= trigger:
                return
            trimmed = self._trim_at_user_boundaries(
                ctx.messages, int(window * settings.LLM_COMPRESSION_THRESHOLD),
            )
            if len(trimmed) < len(ctx.messages):
                dropped = len(ctx.messages) - len(trimmed)
                logger.warning(
                    f"[ContextTrim] 工具循环内裁剪: ~{used} tokens 超过阈值 {trigger:.0f}，"
                    f"按 user 边界丢弃最旧 {dropped} 条消息"
                )
                ctx.messages = trimmed
        except Exception:
            logger.debug("[ContextTrim] 裁剪检查失败（不阻断工具循环）", exc_info=True)

    @staticmethod
    def _resolve_window() -> int:
        from app.core.config import settings
        if settings.LLM_CONTEXT_WINDOW_SIZE > 0:
            return settings.LLM_CONTEXT_WINDOW_SIZE
        try:
            from app.runtime.provider.llm.adapter import llm_adapter
            caps = llm_adapter.get_capabilities(None, None)
            if caps and caps.default_context_window > 0:
                return caps.default_context_window
        except Exception:
            pass
        from app.core.context.constants import FALLBACK_CONTEXT_WINDOW
        return FALLBACK_CONTEXT_WINDOW

    @staticmethod
    def _estimate_tokens(messages: list[dict[str, Any]]) -> int:
        from app.core.context.constants import (
            IMAGE_TOKEN_ESTIMATE,
            TOKEN_WEIGHT_CHINESE,
            TOKEN_WEIGHT_OTHER,
        )
        total = 0
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            content = msg.get("content")
            if isinstance(content, list):  # 多模态 content parts
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "image_url":
                        total += IMAGE_TOKEN_ESTIMATE
                    elif isinstance(part, dict):
                        total += int(len(str(part.get("text", ""))) * TOKEN_WEIGHT_OTHER)
                continue
            text = str(content or "")
            chinese = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
            total += int(chinese * TOKEN_WEIGHT_CHINESE + (len(text) - chinese) * TOKEN_WEIGHT_OTHER)
        return total

    @classmethod
    def _trim_at_user_boundaries(cls, messages: list[dict[str, Any]], target_tokens: int) -> list[dict[str, Any]]:
        if not messages:
            return messages
        sys_count = 0
        while sys_count < len(messages) and messages[sys_count].get("role") == "system":
            sys_count += 1
        body = list(messages[sys_count:])
        # 保底：至少保留最近 6 条不裁
        while len(body) > 6:
            if cls._estimate_tokens(messages[:sys_count] + body) <= target_tokens:
                break
            cut = 0
            for i in range(1, len(body)):
                if body[i].get("role") == "user":
                    cut = i
                    break
            if cut <= 0:
                break
            body = body[cut:]
        return messages[:sys_count] + body


# ──────────────────────────────────────────────────────────────
# 2. ToolExecutionMiddleware
# ──────────────────────────────────────────────────────────────


class ToolExecutionMiddleware(AgentMiddleware):
    """执行工具调用 + 统一输出截断 + 异常兜底 + 发射 tool_event SSE。

    洋葱式位置：在 SpecialToolMiddleware 外层（先进入、后退出）。
    - 进入时：通过 ctx.sse_emitter 发射 tool_event "started"（如有）
    - 调用 next_fn（内层 SpecialTool 或 execute_fn）
    - 输出治理：content 超阈值时走 tool_call_records 落盘 + 占位符替换（T5，对齐 §4.4）
    - 退出时：通过 ctx.sse_emitter 发射 tool_event "completed"（如有）
    - 异常时：返回兜底 tool message，不中断循环
    """

    async def wrap_tool_call(
        self,
        ctx: AgentContext,
        tool_call: dict[str, Any],
        next_fn: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
    ) -> dict[str, Any]:
        tool_name = tool_call.get("function", {}).get("name", "")
        tool_call_id = tool_call.get("id", "")

        if ctx.sse_emitter:
            try:
                await ctx.sse_emitter(
                    SSEEmitMiddleware.format_tool_event_sse(
                        ctx, tool_name, "started", None,
                    )
                )
            except Exception as emit_err:
                logger.warning(f"[ToolExec] tool_event started 发射失败: {emit_err}")

        try:
            result = await next_fn(tool_call)
        except Exception as e:
            logger.error(
                f"[ToolExec] 工具 {tool_name} 执行失败: {e}", exc_info=True,
            )
            result = {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "name": tool_name,
                "content": f"[工具执行失败] {e}",
            }

        # ── W2 探索收获：探索类工具命中的 schema 进入动态可调用集 ──
        if isinstance(result, dict) and tool_name in ("tool_explore", "skill_explore"):
            try:
                discovered = (result.get("metadata") or {}).get("discovered_tools")
                if discovered:
                    stash = ctx.state.setdefault("dynamic_tool_schemas", [])
                    for schema in discovered:
                        if isinstance(schema, dict) and schema not in stash:
                            stash.append(schema)
            except Exception:
                logger.debug("[ToolExec] 探索收获失败（不影响工具结果）", exc_info=True)

        # ── T5 统一输出治理：超阈值落盘 + 占位符替换 ──────────
        # 复用 services/tool_call_recorder 的 LUMINOUS_PERSIST_THRESHOLD 机制，
        # 各工具不再各自为政；落盘结果前端 ConsoleView 仍可查看完整内容。
        if isinstance(result, dict) and result.get("role") == "tool":
            content = result.get("content", "")
            if isinstance(content, str) and len(content) > 2000:
                try:
                    from app.services.tool_call_recorder import record_tool_call

                    # 从 ctx.extra 获取会话标识（对齐 tool_call_records 表结构）
                    conv_id = ctx.extra.get("conv_id") or ctx.extra.get("conversation_id")
                    session_id = ctx.extra.get("session_id") or ctx.extra.get("chat_id")

                    # 解析 arguments（JSON 字符串或 dict）
                    import json
                    raw_args = tool_call.get("function", {}).get("arguments", "{}")
                    try:
                        arguments = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
                    except (json.JSONDecodeError, TypeError):
                        arguments = {}

                    # 记录并替换为占位符（异步写入 DB，失败不中断）
                    persisted = await record_tool_call(
                        session_id=session_id,
                        tool_name=tool_name,
                        arguments=arguments,
                        result=content,
                        success=not content.startswith("[工具执行失败]"),
                        conversation_id=conv_id,
                    )
                    # 占位符替换 content（仅当 record_tool_call 返回占位符时）
                    if persisted.startswith("<luminous-persisted-output"):
                        result["content"] = (
                            f"[工具输出已落盘，共 {len(content)} 字符，可在控制台查看完整内容]\n"
                            f"{persisted}"
                        )
                        logger.debug(
                            f"[ToolExec] 工具 {tool_name} 输出超阈值已落盘 "
                            f"(原始 {len(content)} 字符)"
                        )
                except Exception as persist_err:
                    # 落盘失败不中断工具循环，仅记录警告
                    logger.warning(
                        f"[ToolExec] 工具 {tool_name} 输出落盘失败: {persist_err}"
                    )

        if ctx.sse_emitter:
            output = ""
            if isinstance(result, dict):
                output = result.get("content", "")
            try:
                await ctx.sse_emitter(
                    SSEEmitMiddleware.format_tool_event_sse(
                        ctx, tool_name, "completed", output,
                    )
                )
            except Exception as emit_err:
                logger.warning(f"[ToolExec] tool_event completed 发射失败: {emit_err}")

        return result


# ──────────────────────────────────────────────────────────────
# 3. SpecialToolMiddleware
# ──────────────────────────────────────────────────────────────


class SpecialToolMiddleware(AgentMiddleware):
    """处理特殊工具的事件队列转发。

    识别三种特殊工具：
    - delegate_to_subagent: 子 Agent 委派，事件走 subagent_event 通道
    - create_scheduled_task: 定时任务，browser_action 走 subagent_event，其余走 task_event
    - start_collaboration: 多 Agent 协作，事件走 subagent_event 通道

    洋葱式位置：在 ToolExecutionMiddleware 内层（后进入、先退出）。
    通过 contextvars 注入事件回调，并行消费事件队列与工具任务，
    将事件通过 ctx.sse_emitter 转发为 SSE。

    支持 ctx.extra["special_tool_handlers"] 注入自定义处理器（可选）：
        {"tool_name": async def handler(ctx, tool_call, next_fn) -> dict}
    """

    _SPECIAL_TOOLS = frozenset({
        "delegate_to_subagent",
        "create_scheduled_task",
        "start_collaboration",
    })

    async def wrap_tool_call(
        self,
        ctx: AgentContext,
        tool_call: dict[str, Any],
        next_fn: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
    ) -> dict[str, Any]:
        tool_name = tool_call.get("function", {}).get("name", "")

        # 自定义处理器优先
        handlers = ctx.extra.get("special_tool_handlers") or {}
        if tool_name in handlers:
            return await handlers[tool_name](ctx, tool_call, next_fn)

        if tool_name not in self._SPECIAL_TOOLS:
            return await next_fn(tool_call)

        if not ctx.sse_emitter:
            return await next_fn(tool_call)

        return await self._run_with_event_queue(ctx, tool_call, next_fn, tool_name)

    async def _run_with_event_queue(
        self,
        ctx: AgentContext,
        tool_call: dict[str, Any],
        next_fn: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
        tool_name: str,
    ) -> dict[str, Any]:
        """设置事件回调 + 并行消费事件队列 + 转发 SSE。"""
        from app.core.tools.builtin.subagent_tool import (
            reset_subagent_event_callback,
            set_subagent_event_callback,
        )

        event_queue: asyncio.Queue = asyncio.Queue()

        async def _event_cb(event: dict[str, Any]) -> None:
            await event_queue.put(event)

        token = set_subagent_event_callback(_event_cb)
        try:
            tool_task = asyncio.ensure_future(next_fn(tool_call))
            while not tool_task.done():
                queue_get = asyncio.ensure_future(event_queue.get())
                done, _pending = await asyncio.wait(
                    [tool_task, queue_get],
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if queue_get in done:
                    event = queue_get.result()
                    sse = self._format_special_event_sse(ctx, event, tool_name)
                    if sse:
                        try:
                            await ctx.sse_emitter(sse)
                        except Exception as emit_err:
                            logger.warning(
                                f"[SpecialTool] {tool_name} 事件转发失败: {emit_err}"
                            )
                if tool_task in done:
                    if not queue_get.done():
                        queue_get.cancel()
                        try:
                            await queue_get
                        except asyncio.CancelledError:
                            pass
                    break

            # 消费剩余事件
            while not event_queue.empty():
                event = event_queue.get_nowait()
                sse = self._format_special_event_sse(ctx, event, tool_name)
                if sse:
                    try:
                        await ctx.sse_emitter(sse)
                    except Exception as emit_err:
                        logger.warning(
                            f"[SpecialTool] {tool_name} 剩余事件转发失败: {emit_err}"
                        )

            return tool_task.result()
        finally:
            reset_subagent_event_callback(token)

    @staticmethod
    def _format_special_event_sse(
        ctx: AgentContext, event: dict[str, Any], tool_name: str,
    ) -> str | None:
        """格式化特殊工具事件为 SSE 字符串。

        - delegate_to_subagent / start_collaboration: 走 subagent_event 通道
        - create_scheduled_task: browser_action 走 subagent_event，其余走 task_event
        """
        chat_id = ctx.state.get("chat_id", "")
        model = ctx.state.get("model", "")
        provider = ctx.state.get("provider", "")

        if tool_name == "create_scheduled_task" and not event.get("browser_action"):
            chunk = ChatStreamChunk(
                id=chat_id, model=model, provider=provider, task_event=event,
            )
        else:
            chunk = ChatStreamChunk(
                id=chat_id, model=model, provider=provider, subagent_event=event,
            )
        return sse_data(chunk)


# ──────────────────────────────────────────────────────────────
# 4. LoopGuardMiddleware
# ──────────────────────────────────────────────────────────────


class LoopGuardMiddleware(AgentMiddleware):
    """检测工具调用循环边界，防止无限循环。

    - ctx.iteration >= max_iterations 时设 ctx.state["aborted"]=True 终止循环
    - 无进展（本轮无 content、无 reasoning、无 tool_calls）时记录 warning
    """

    def __init__(self, max_iterations: int = 10) -> None:
        self._max_iterations = max_iterations

    async def after_model(
        self, ctx: AgentContext, response: LLMResponse | dict | None
    ) -> None:
        if ctx.iteration >= self._max_iterations:
            ctx.state["aborted"] = True
            logger.warning(
                f"[LoopGuard] 达到最大迭代次数 {self._max_iterations}，终止循环"
            )
            return

        iteration_content = ctx.state.get("iteration_content", "")
        iteration_reasoning = ctx.state.get("iteration_reasoning", "")
        tool_calls = ctx.state.get("tool_calls") or []
        if not iteration_content and not iteration_reasoning and not tool_calls:
            logger.warning("[LoopGuard] 无进展（无内容、无推理、无工具调用），终止循环")
            ctx.state["aborted"] = True


# ──────────────────────────────────────────────────────────────
# 5. SubagentCancelMiddleware
# ──────────────────────────────────────────────────────────────


class SubagentCancelMiddleware(AgentMiddleware):
    """检查子 Agent 取消信号（subagent 场景专用）。

    读 ctx.extra["cancel_event"]（asyncio.Event），
    若已设置则标记 aborted 终止循环。
    """

    async def before_model(self, ctx: AgentContext) -> None:
        cancel_event = ctx.extra.get("cancel_event")
        if cancel_event is not None and cancel_event.is_set():
            ctx.state["aborted"] = True
            logger.info(
                f"[SubagentCancel] 子 Agent 在迭代 {ctx.iteration} 被取消"
            )


# ──────────────────────────────────────────────────────────────
# 6. MemoryAccessMiddleware
# ──────────────────────────────────────────────────────────────


class MemoryAccessMiddleware(AgentMiddleware):
    """设置/重置记忆访问权限 contextvar。

    before_agent: 读 ctx.extra["memory_access"] 设置 contextvar，token 存 ctx.state
    after_agent: 重置 contextvar 到之前状态

    对应现有逻辑：
    - chat_service.stream_response 的 MEMORY_ACCESS_READ_WRITE / MEMORY_ACCESS_NONE
    - group_chat._respond_as_agent_stream 的 MEMORY_ACCESS_READ_MAIN
    """

    async def before_agent(self, ctx: AgentContext) -> None:
        memory_access = ctx.extra.get("memory_access")
        if not memory_access:
            return

        from app.core.agents.memory_access import set_luominest_memory_access

        try:
            token = set_luominest_memory_access(memory_access)
            ctx.state["_memory_access_token"] = token
        except ValueError as e:
            logger.warning(f"[MemoryAccess] 设置记忆访问级别失败: {e}")

    async def after_agent(self, ctx: AgentContext) -> None:
        token = ctx.state.pop("_memory_access_token", None)
        if token is None:
            return

        from app.core.agents.memory_access import reset_luominest_memory_access

        try:
            reset_luominest_memory_access(token)
        except Exception as e:
            logger.debug(f"[MemoryAccess] 重置记忆访问级别失败: {e}")


# ──────────────────────────────────────────────────────────────
# 7. SSEEmitMiddleware
# ──────────────────────────────────────────────────────────────


class SSEEmitMiddleware(AgentMiddleware):
    """发射 ChatStreamChunk SSE 事件。

    after_model: 若有 tool_calls，发射 tool_calls 公告 SSE（通过 ctx.sse_emitter）
    after_tool_call: 发射 tool_event "completed" SSE（通过 ctx.sse_emitter）

    同时提供静态格式化方法，供 AgentRunner 直接 yield SSE 字符串。
    """

    @staticmethod
    def format_content_sse(
        ctx: AgentContext,
        content: str,
        reasoning: str = "",
        emotion: str | None = None,
        err_code: str | None = None,
    ) -> str:
        """格式化 content/reasoning SSE 字符串（err_code 仅错误透传场景携带，可为云链路业务码）。"""
        chat_id = ctx.state.get("chat_id", "")
        model = ctx.state.get("model", "")
        provider = ctx.state.get("provider", "")
        chunk = ChatStreamChunk(
            id=chat_id,
            content=content,
            reasoning_content=reasoning,
            model=model,
            provider=provider,
            emotion=emotion,
            errCode=err_code,
        )
        return sse_data(chunk)

    @staticmethod
    def format_tool_calls_sse(
        ctx: AgentContext,
        tool_calls: list[dict[str, Any]],
    ) -> str:
        """格式化 tool_calls 公告 SSE 字符串。"""
        chat_id = ctx.state.get("chat_id", "")
        model = ctx.state.get("model", "")
        provider = ctx.state.get("provider", "")
        chunk = ChatStreamChunk(
            id=chat_id,
            model=model,
            provider=provider,
            tool_calls=tool_calls,
            iteration=ctx.iteration,
        )
        return sse_data(chunk)

    @staticmethod
    def format_tool_event_sse(
        ctx: AgentContext,
        tool_name: str,
        status: str,
        output: str | None,
    ) -> str:
        """格式化 tool_event SSE 字符串。"""
        chat_id = ctx.state.get("chat_id", "")
        model = ctx.state.get("model", "")
        provider = ctx.state.get("provider", "")
        tool_event = {
            "tool_name": tool_name,
            "status": status,
            "output": output,
        }
        chunk = ChatStreamChunk(
            id=chat_id,
            model=model,
            provider=provider,
            tool_event=tool_event,
            iteration=ctx.iteration,
        )
        return sse_data(chunk)

    async def after_model(
        self, ctx: AgentContext, response: LLMResponse | dict | None
    ) -> None:
        if ctx.state.get("aborted"):
            return
        if not ctx.sse_emitter:
            return
        tool_calls = ctx.state.get("tool_calls") or []
        if not tool_calls:
            return
        try:
            await ctx.sse_emitter(self.format_tool_calls_sse(ctx, tool_calls))
        except Exception as emit_err:
            logger.warning(f"[SSEEmit] tool_calls 公告发射失败: {emit_err}")


# ──────────────────────────────────────────────────────────────
# 8. UsageTrackMiddleware
# ──────────────────────────────────────────────────────────────


class UsageTrackMiddleware(AgentMiddleware):
    """记录 token 用量到 usage_tracker。

    after_agent: 读 ctx.state["usage"]，调 usage_tracker.record_usage。
    异常时仅 warning 不中断。
    """

    async def after_agent(self, ctx: AgentContext) -> None:
        try:
            from app.services.usage_tracker import usage_tracker

            usage = ctx.state.get("usage")
            provider = ctx.state.get("provider", "")
            model = ctx.state.get("model", "")
            agent_id = ctx.extra.get("agent_id")
            conv_id = ctx.extra.get("conv_id")
            is_stream = ctx.extra.get("is_stream", True)
            usage_tracker.record_usage(
                provider=provider,
                model=model,
                usage=usage,
                agent_id=agent_id,
                conversation_id=conv_id,
                is_stream=is_stream,
            )
        except Exception as e:
            logger.warning(f"[UsageTrack] Usage tracking failed: {e}")
