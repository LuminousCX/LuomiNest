"""LuomiNest Agent 中间件基类。

定义中间件共享上下文 AgentContext 与基类 AgentMiddleware。
所有内置中间件（builtin.py）继承 AgentMiddleware，按需 override 钩子。

钩子分类（参考 deer-flow）：
- before_agent: Agent 循环开始前（设置 contextvar / 过滤工具）
- before_model: 每轮 LLM 调用前（检查取消 / 注入参数）
- after_model: 每轮 LLM 调用后（检测循环边界 / 发射 SSE）
- wrap_tool_call: 工具调用洋葱式包装（执行 / 特殊工具事件转发）
- after_tool_call: 单个工具调用完成后（发射 tool_event SSE）
- after_agent: Agent 循环结束后（记录 usage / 重置 contextvar）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from app.runtime.provider.llm.types import LLMResponse, RouteHint


@dataclass
class AgentContext:
    """中间件共享上下文。

    所有中间件通过此对象共享状态，runner 在循环中读写 ctx。

    Attributes:
        messages: 对话消息列表（可变，工具循环中追加 assistant/tool 消息）
        tools: OpenAI function calling 格式工具列表，None 表示不启用工具
        route_hint: 路由提示（CHAT/REASONER/AGENT），决定主模型/推理模型
        iteration: 当前工具调用循环轮次（从 0 开始）
        state: 运行时状态字典，含以下键：
            - chat_id: SSE 事件 ID
            - content: 累积的文本内容（跨轮次）
            - reasoning: 累积的推理内容
            - iteration_content: 当前轮次的文本内容（每轮重置）
            - tool_calls: 当前轮次的工具调用列表（每轮重置）
            - finish_reason: 当前轮次的停止原因
            - usage: token 用量统计
            - aborted: 是否中止（LoopGuard / SubagentCancel 设置）
            - model: 模型名称
            - provider: 供应商名称
            - emotion: 情绪标签（可选）
        extra: 调用方注入的配置字典，含以下键：
            - scene: 场景（"chat" / "subagent" / "group"）
            - is_stream: 是否流式模式
            - disable_tools: list[str] 禁用的工具名列表
            - tool_whitelist: set[str] 工具白名单
            - is_sub_agent: bool 是否子 Agent
            - agent_depth: int 委派深度
            - memory_access: str 记忆访问级别（"none"/"read_main"/"read_write"）
            - cancel_event: asyncio.Event 取消信号（subagent 场景）
            - agent_id: str Agent ID
            - conv_id: str 会话 ID
            - special_tool_handlers: dict 特殊工具自定义处理器
        sse_emitter: SSE 事件发射器（流式模式由 runner 设置为 buffer 收集器）
    """
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]] | None = None
    route_hint: RouteHint = RouteHint.CHAT
    iteration: int = 0
    state: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)
    sse_emitter: Callable[[str], Awaitable[None]] | None = None


class AgentMiddleware:
    """Agent 中间件基类。

    钩子默认 no-op，子类按需 override。
    wrap_tool_call 默认直接调用 next_fn（透传）。
    """

    async def before_agent(self, ctx: AgentContext) -> None:
        """Agent 循环开始前钩子（正序执行）。"""

    async def before_model(self, ctx: AgentContext) -> None:
        """每轮 LLM 调用前钩子（正序执行）。"""

    async def after_model(
        self, ctx: AgentContext, response: LLMResponse | dict | None
    ) -> None:
        """每轮 LLM 调用后钩子（反序执行）。"""

    async def wrap_tool_call(
        self,
        ctx: AgentContext,
        tool_call: dict[str, Any],
        next_fn: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
    ) -> dict[str, Any]:
        """工具调用洋葱式包装钩子（idx=0 最外层）。

        默认直接调用 next_fn（透传），子类可 override 添加前置/后置逻辑。
        """
        return await next_fn(tool_call)

    async def after_tool_call(
        self, ctx: AgentContext, tool_call: dict[str, Any], result: dict[str, Any]
    ) -> None:
        """单个工具调用完成后钩子（反序执行）。"""

    async def after_agent(self, ctx: AgentContext) -> None:
        """Agent 循环结束后钩子（反序执行）。"""
