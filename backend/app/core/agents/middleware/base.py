"""LuomiNest Agent 中间件基类。

定义中间件共享上下文 AgentContext 与基类 AgentMiddleware。
所有内置中间件（builtin.py）继承 AgentMiddleware，按需 override 钩子。

钩子分类（参考 deer-flow + airi 观察者模式）：
- before_agent: Agent 循环开始前（设置 contextvar / 过滤工具）
- before_model: 每轮 LLM 调用前（检查取消 / 注入参数）
- on_before_message_composed: 消息组装前，可修改 messages 列表
- on_after_message_composed: 消息组装后，可修改 messages 列表
- after_model: 每轮 LLM 调用后（检测循环边界 / 发射 SSE）
- wrap_tool_call: 工具调用洋葱式包装（执行 / 特殊工具事件转发）
- after_tool_call: 单个工具调用完成后（发射 tool_event SSE）
- on_stream_token: 流式 token 到达时通知
- on_chat_turn_complete: 整个回合（含工具调用链）结束后通知
- after_agent: Agent 循环结束后（记录 usage / 重置 contextvar）

HookRegistry: 观察者模式钩子注册表，支持运行时动态注册/取消回调。
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from loguru import logger

from app.runtime.provider.llm.types import LLMResponse, RouteHint


class HookRegistry:
    """观察者模式钩子注册表。

    支持运行时动态注册/取消异步回调，按注册顺序串行执行。
    异常回调仅 warning 不中断后续回调。
    """

    # 钩子点名称常量
    ON_BEFORE_MESSAGE_COMPOSED = "on_before_message_composed"
    ON_AFTER_MESSAGE_COMPOSED = "on_after_message_composed"
    ON_STREAM_TOKEN = "on_stream_token"
    ON_CHAT_TURN_COMPLETE = "on_chat_turn_complete"

    def __init__(self) -> None:
        self._hooks: dict[str, list[Callable[..., Awaitable[None]]]] = defaultdict(list)

    def register(
        self, hook_name: str, callback: Callable[..., Awaitable[None]],
    ) -> Callable[[], None]:
        """注册钩子回调，返回取消注册函数。"""
        self._hooks[hook_name].append(callback)

        def unregister() -> None:
            self._hooks[hook_name].remove(callback)

        return unregister

    async def emit(self, hook_name: str, **kwargs: Any) -> None:
        """触发钩子，串行执行所有注册的回调。"""
        for callback in list(self._hooks.get(hook_name, [])):
            try:
                await callback(**kwargs)
            except Exception as e:
                logger.warning(f"Hook {hook_name} callback error: {e}")

    def clear(self, hook_name: str | None = None) -> None:
        """清空钩子。hook_name=None 时清空所有。"""
        if hook_name:
            self._hooks[hook_name].clear()
        else:
            self._hooks.clear()

    @property
    def hook_count(self) -> int:
        """返回已注册的钩子总数。"""
        return sum(len(hooks) for hooks in self._hooks.values())


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

    # ── 新增生命周期钩子（可选 override） ──────────────────────

    async def on_before_message_composed(
        self, ctx: AgentContext, messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """消息组装前钩子，可修改 messages 列表（正序执行）。

        在消息发送给 LLM 之前调用，适合注入系统提示、过滤消息等。
        返回修改后的 messages 列表（可原地修改或返回新列表）。
        """
        return messages

    async def on_after_message_composed(
        self, ctx: AgentContext, messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """消息组装后钩子，可修改 messages 列表（正序执行）。

        在 on_before_message_composed 之后、LLM 调用之前调用，
        适合最终的消息校验、token 计数等。
        返回修改后的 messages 列表。
        """
        return messages

    async def on_stream_token(
        self, ctx: AgentContext, token: str, token_type: str,
    ) -> None:
        """流式 token 通知钩子（正序执行）。

        每个流式 token 到达时调用。token_type 为 "content" 或 "reasoning"。
        适合统计 token 数、实时日志等。
        """

    async def on_chat_turn_complete(
        self, ctx: AgentContext, result: dict[str, Any],
    ) -> None:
        """回合完成通知钩子（正序执行）。

        整个回合（含工具调用链）结束后调用。
        result 包含 output / output_text / tool_calls 等汇总信息。
        适合记录 usage 统计、日志归档等。
        """
