"""LuomiNest 中间件管道。

按顺序执行中间件钩子：
- before_agent / before_model：正序（0→N）
- after_model / after_tool_call / after_agent：反序（N→0）
- wrap_tool_call：洋葱式（idx=0 最外层，idx=N 调 execute_fn）

wrap_tool_call 洋葱式实现：用闭包构造 next 链，
idx=0 的中间件最先进入、最后退出（外层），idx=N 的中间件最后进入、最先退出（内层），
idx=N+1 时调用 execute_fn（实际工具执行）。
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from app.core.agents.middleware.base import AgentContext, AgentMiddleware


class MiddlewarePipeline:
    """中间件管道，按顺序执行钩子。"""

    def __init__(self, middlewares: list[AgentMiddleware]) -> None:
        self._middlewares: list[AgentMiddleware] = list(middlewares)

    @property
    def middlewares(self) -> list[AgentMiddleware]:
        """已注册的中间件列表（只读副本）。"""
        return list(self._middlewares)

    async def run_before_agent(self, ctx: AgentContext) -> None:
        """正序执行 before_agent 钩子（0→N）。"""
        for mw in self._middlewares:
            await mw.before_agent(ctx)

    async def run_before_model(self, ctx: AgentContext) -> None:
        """正序执行 before_model 钩子（0→N）。"""
        for mw in self._middlewares:
            await mw.before_model(ctx)

    async def run_after_model(
        self, ctx: AgentContext, response: Any
    ) -> None:
        """反序执行 after_model 钩子（N→0）。"""
        for mw in reversed(self._middlewares):
            await mw.after_model(ctx, response)

    async def run_after_tool_call(
        self,
        ctx: AgentContext,
        tool_call: dict[str, Any],
        result: dict[str, Any],
    ) -> None:
        """反序执行 after_tool_call 钩子（N→0）。"""
        for mw in reversed(self._middlewares):
            await mw.after_tool_call(ctx, tool_call, result)

    async def run_after_agent(self, ctx: AgentContext) -> None:
        """反序执行 after_agent 钩子（N→0）。"""
        for mw in reversed(self._middlewares):
            await mw.after_agent(ctx)

    async def run_tool_call(
        self,
        ctx: AgentContext,
        tool_call: dict[str, Any],
        execute_fn: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
    ) -> dict[str, Any]:
        """洋葱式执行 wrap_tool_call 钩子。

        idx=0 的中间件最外层（最先进入、最后退出），
        idx=len-1 的中间件最内层（最后进入、最先退出），
        越过最后一个中间件后调用 execute_fn 执行实际工具。

        Args:
            ctx: 中间件共享上下文
            tool_call: 工具调用字典
            execute_fn: 实际工具执行函数（由 tool_orchestrator.execute_tool_call 提供）

        Returns:
            工具执行结果（tool message 字典）
        """

        async def make_next(idx: int) -> dict[str, Any]:
            if idx >= len(self._middlewares):
                return await execute_fn(tool_call)
            mw = self._middlewares[idx]
            # next_fn 是 callable：接受 tool_call，返回 awaitable
            # tool_call 已在闭包中捕获，next_fn 忽略参数直接进入下一层
            next_fn: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]] = (
                lambda _tc: make_next(idx + 1)
            )
            return await mw.wrap_tool_call(ctx, tool_call, next_fn)

        return await make_next(0)
