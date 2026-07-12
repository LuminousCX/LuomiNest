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


# ──────────────────────────────────────────────────────────────
# 2. ToolExecutionMiddleware
# ──────────────────────────────────────────────────────────────


class ToolExecutionMiddleware(AgentMiddleware):
    """执行工具调用 + 异常兜底 + 发射 tool_event SSE。

    洋葱式位置：在 SpecialToolMiddleware 外层（先进入、后退出）。
    - 进入时：通过 ctx.sse_emitter 发射 tool_event "started"（如有）
    - 调用 next_fn（内层 SpecialTool 或 execute_fn）
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
        return f"data: {chunk.model_dump_json()}\n\n"


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
    ) -> str:
        """格式化 content/reasoning SSE 字符串。"""
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
        )
        return f"data: {chunk.model_dump_json()}\n\n"

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
        return f"data: {chunk.model_dump_json()}\n\n"

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
        return f"data: {chunk.model_dump_json()}\n\n"

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
                conv_id=conv_id,
                is_stream=is_stream,
            )
        except Exception as e:
            logger.warning(f"[UsageTrack] Usage tracking failed: {e}")
