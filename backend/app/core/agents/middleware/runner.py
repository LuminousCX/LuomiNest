"""LuomiNest AgentRunner — 统一的工具调用循环编排器。

替代 4 处重复的工具循环（stream_chat / stream_response / subagent / group_chat），
通过中间件管道组合实现：
- before_agent → while 循环(before_model → llm_call_fn → after_model → tool_calls → after_tool_call) → after_agent

两种运行模式：
- run_stream: 流式循环，llm_call_fn 返回 AsyncIterator[StreamEvent]，runner yield SSE 字符串
- run_non_stream: 非流式循环，llm_call_fn 返回 LLMResponse/dict，runner 返回最终 state

SSE 发射策略（run_stream）：
- content/reasoning: runner 直接 yield（实时流式）
- tool_calls 公告 / tool_event / subagent_event / task_event: 通过 ctx.sse_emitter 收集到 buffer，
  runner 在步骤边界 drain buffer 并 yield（近实时）
- runner 自动将 ctx.sse_emitter 设置为 buffer 收集器，循环结束后恢复原值
"""
from __future__ import annotations

from typing import Any, AsyncIterator, Awaitable, Callable

from loguru import logger

from app.core.agents.middleware.base import AgentContext
from app.core.agents.middleware.builtin import SSEEmitMiddleware
from app.core.agents.middleware.pipeline import MiddlewarePipeline
from app.core.tools.orchestrator import tool_orchestrator
from app.runtime.provider.llm.types import LLMResponse, StreamEvent


class AgentRunner:
    """统一的 Agent 工具调用循环编排器。"""

    def __init__(
        self,
        pipeline: MiddlewarePipeline,
        max_iterations: int = 10,
        execute_fn: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]] | None = None,
    ) -> None:
        """
        Args:
            pipeline: 中间件管道
            max_iterations: 最大工具调用循环次数
            execute_fn: 工具执行函数（默认 tool_orchestrator.execute_tool_call，测试可注入 mock）
        """
        self._pipeline = pipeline
        self._max_iterations = max_iterations
        self._execute_fn = execute_fn or tool_orchestrator.execute_tool_call

    async def run_stream(
        self,
        ctx: AgentContext,
        llm_call_fn: Callable[[AgentContext], AsyncIterator[StreamEvent]],
    ) -> AsyncIterator[str]:
        """流式循环。llm_call_fn(ctx) 返回 AsyncIterator[StreamEvent]。

        yield SSE 事件字符串（ChatStreamChunk 格式，与前端兼容）。
        循环结束后不发射 done 事件（由调用方负责）。
        """
        # 设置 SSE buffer 收集器：中间件通过 ctx.sse_emitter 发射的 SSE 进入 buffer，
        # runner 在步骤边界 drain 并 yield（content/reasoning 由 runner 直接 yield）
        sse_buffer: list[str] = []
        original_emitter = ctx.sse_emitter

        async def _buffer_emitter(sse_str: str) -> None:
            sse_buffer.append(sse_str)

        ctx.sse_emitter = _buffer_emitter

        await self._pipeline.run_before_agent(ctx)
        try:
            while ctx.iteration <= self._max_iterations and not ctx.state.get("aborted"):
                await self._pipeline.run_before_model(ctx)
                if ctx.state.get("aborted"):
                    break

                # 重置每轮状态
                ctx.state["iteration_content"] = ""
                ctx.state["iteration_reasoning"] = ""
                ctx.state["tool_calls"] = []
                ctx.state["_tool_call_deltas"] = {}
                ctx.state["finish_reason"] = None

                # 流式消费 LLM 输出（content/reasoning 直接 yield）
                try:
                    async for event in llm_call_fn(ctx):
                        sse = self._process_stream_event(ctx, event)
                        if sse:
                            yield sse
                except Exception as e:
                    logger.error(
                        f"[AgentRunner] run_stream LLM 调用失败: {e}", exc_info=True,
                    )
                    ctx.state["aborted"] = True
                    yield SSEEmitMiddleware.format_content_sse(
                        ctx, "[Error] An internal error occurred",
                    )
                    break

                # 组装本轮 tool_calls
                ctx.state["tool_calls"] = self._assemble_tool_calls(ctx)

                # after_model 钩子（SSEEmit 发射 tool_calls 公告到 buffer，LoopGuard 检测边界）
                await self._pipeline.run_after_model(ctx, ctx.state)
                while sse_buffer:
                    yield sse_buffer.pop(0)

                if ctx.state.get("aborted"):
                    break

                tool_calls = ctx.state.get("tool_calls") or []
                if not tool_calls:
                    break

                # 回填带 tool_calls 的 assistant 消息
                assistant_msg = tool_orchestrator.build_assistant_message_with_tool_calls(
                    ctx.state.get("iteration_content", ""), tool_calls,
                )
                ctx.messages.append(assistant_msg)

                # 依次执行工具调用
                for tc in tool_calls:
                    tool_name = tc.get("function", {}).get("name", "")
                    logger.info(
                        f"[AgentRunner] 执行工具: {tool_name} "
                        f"(iteration={ctx.iteration})"
                    )
                    result = await self._pipeline.run_tool_call(ctx, tc, self._execute_fn)
                    while sse_buffer:
                        yield sse_buffer.pop(0)
                    await self._pipeline.run_after_tool_call(ctx, tc, result)
                    while sse_buffer:
                        yield sse_buffer.pop(0)
                    ctx.messages.append(result)

                ctx.iteration += 1
        finally:
            ctx.sse_emitter = original_emitter
            await self._pipeline.run_after_agent(ctx)

    async def run_non_stream(
        self,
        ctx: AgentContext,
        llm_call_fn: Callable[[AgentContext], Awaitable[LLMResponse | dict]],
    ) -> dict[str, Any]:
        """非流式循环。llm_call_fn(ctx) 返回 LLMResponse 或 dict。

        返回 ctx.state（含 content/reasoning/tool_calls/usage/aborted 等）。
        """
        await self._pipeline.run_before_agent(ctx)
        try:
            while ctx.iteration <= self._max_iterations and not ctx.state.get("aborted"):
                await self._pipeline.run_before_model(ctx)
                if ctx.state.get("aborted"):
                    break

                # 重置每轮状态
                ctx.state["iteration_content"] = ""
                ctx.state["tool_calls"] = []
                ctx.state["finish_reason"] = None

                # 非流式调用 LLM
                try:
                    response = await llm_call_fn(ctx)
                except Exception as e:
                    logger.error(
                        f"[AgentRunner] run_non_stream LLM 调用失败: {e}",
                        exc_info=True,
                    )
                    ctx.state["aborted"] = True
                    ctx.state["content"] = f"子 Agent LLM 调用失败: {e}"
                    break

                # 解析响应到 ctx.state
                self._process_response(ctx, response)

                # after_model 钩子（LoopGuard 检测边界）
                await self._pipeline.run_after_model(ctx, response)
                if ctx.state.get("aborted"):
                    break

                tool_calls = ctx.state.get("tool_calls") or []
                if not tool_calls:
                    # 无工具调用，回填最终 assistant 消息并终止循环
                    final_content = ctx.state.get("iteration_content", "")
                    if final_content:
                        ctx.messages.append({
                            "role": "assistant",
                            "content": final_content,
                        })
                    break

                # 回填带 tool_calls 的 assistant 消息
                assistant_msg = tool_orchestrator.build_assistant_message_with_tool_calls(
                    ctx.state.get("iteration_content", ""), tool_calls,
                )
                ctx.messages.append(assistant_msg)

                # 依次执行工具调用
                for tc in tool_calls:
                    tool_name = tc.get("function", {}).get("name", "")
                    logger.info(
                        f"[AgentRunner] 执行工具: {tool_name} "
                        f"(iteration={ctx.iteration})"
                    )
                    result = await self._pipeline.run_tool_call(ctx, tc, self._execute_fn)
                    await self._pipeline.run_after_tool_call(ctx, tc, result)
                    ctx.messages.append(result)

                ctx.iteration += 1
        finally:
            await self._pipeline.run_after_agent(ctx)

        return ctx.state

    def _process_stream_event(
        self, ctx: AgentContext, event: StreamEvent,
    ) -> str | None:
        """处理流式事件，更新 ctx.state，返回 SSE 字符串或 None。

        - content: 累积到 content/iteration_content，返回 content SSE
        - reasoning: 累积到 reasoning，返回 reasoning SSE
        - tool_call_delta: 累积到 _tool_call_deltas，返回 None
        - finish_reason: 记录到 finish_reason，返回 None
        - usage: 记录到 usage，返回 None
        """
        if event.type == "content":
            content = event.data.get("content", "")
            emotion = event.data.get("emotion")
            if content:
                ctx.state["iteration_content"] += content
                ctx.state["content"] = ctx.state.get("content", "") + content
            return SSEEmitMiddleware.format_content_sse(ctx, content, "", emotion)

        if event.type == "reasoning":
            rc = event.data.get("reasoning", "")
            if rc:
                ctx.state["reasoning"] = ctx.state.get("reasoning", "") + rc
                ctx.state["iteration_reasoning"] = ctx.state.get("iteration_reasoning", "") + rc
            return SSEEmitMiddleware.format_content_sse(ctx, "", rc)

        if event.type == "tool_call_delta":
            idx = event.data.get("index", 0)
            deltas = ctx.state.setdefault("_tool_call_deltas", {})
            if idx not in deltas:
                deltas[idx] = {"id": "", "name": "", "arguments": ""}
            if event.data.get("tool_call_id"):
                deltas[idx]["id"] = event.data["tool_call_id"]
            if event.data.get("function_name"):
                deltas[idx]["name"] = event.data["function_name"]
            if event.data.get("function_arguments"):
                deltas[idx]["arguments"] += event.data["function_arguments"]
            return None

        if event.type == "finish_reason":
            ctx.state["finish_reason"] = event.data.get("finish_reason")
            return None

        if event.type == "usage":
            ctx.state["usage"] = event.data.get("usage")
            return None

        return None

    @staticmethod
    def _assemble_tool_calls(ctx: AgentContext) -> list[dict[str, Any]]:
        """从 _tool_call_deltas 组装 tool_calls 列表（OpenAI function calling 格式）。"""
        deltas = ctx.state.pop("_tool_call_deltas", {})
        if not deltas:
            return []
        tool_calls: list[dict[str, Any]] = []
        for idx in sorted(deltas.keys()):
            entry = deltas[idx]
            tool_calls.append({
                "id": entry["id"] or f"call_{ctx.iteration}_{idx}",
                "type": "function",
                "function": {
                    "name": entry["name"],
                    "arguments": entry["arguments"],
                },
            })
        return tool_calls

    @staticmethod
    def _process_response(
        ctx: AgentContext, response: LLMResponse | dict,
    ) -> None:
        """解析非流式响应到 ctx.state。

        - LLMResponse: 取 content/reasoning/tool_calls/usage/finish_reason
        - dict: 取 content/tool_calls/usage（兼容旧版 return_raw=True 格式）
        """
        if isinstance(response, LLMResponse):
            content = response.content or ""
            ctx.state["iteration_content"] = content
            ctx.state["content"] = content
            if response.reasoning:
                ctx.state["reasoning"] = response.reasoning
            ctx.state["tool_calls"] = response.tool_calls or []
            if response.usage:
                ctx.state["usage"] = response.usage
            ctx.state["finish_reason"] = response.finish_reason
            return

        if isinstance(response, dict):
            content = response.get("content", "")
            ctx.state["iteration_content"] = content
            ctx.state["content"] = content
            if response.get("reasoning"):
                ctx.state["reasoning"] = response["reasoning"]
            ctx.state["tool_calls"] = response.get("tool_calls") or []
            if response.get("usage"):
                ctx.state["usage"] = response["usage"]
            ctx.state["finish_reason"] = response.get("finish_reason", "stop")
            return

        ctx.state["iteration_content"] = str(response)
        ctx.state["content"] = str(response)
        ctx.state["tool_calls"] = []
