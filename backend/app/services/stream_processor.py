"""
流式处理器 —— 统一 stream_chat / stream_response 中重复的流式 chunk 处理管线。

将 ThinkingTagManager + StreamCoalescer + 五类标签网关（TagStreamParser，原
EmotionStreamParser）三条管线封装为单一可组合的异步生成器包装器。
"""
from __future__ import annotations

from typing import Any, AsyncIterator, Callable, Awaitable

from loguru import logger

from app.runtime.provider.llm.types import StreamEvent
from app.core.tags import TagStreamParser, get_default_translator
from app.core.tags.definitions import TASK_DISPATCH_DETECTED_KEY
from app.services.stream_components import ThinkingTagManager, StreamCoalescer
from app.core.agents.middleware.base import AgentContext, HookRegistry


class StreamProcessor:
    """流式 chunk 处理管线：thinking 分流 → chunk 合并 → 标签网关清洗。

    使用方式：
        processor = StreamProcessor(hook_registry, on_reasoning=...)
        async for chunk in processor.wrap(llm_adapter.chat_stream(...), ctx):
            yield chunk
    """

    def __init__(
        self,
        hook_registry: HookRegistry,
        on_reasoning: Callable[[str, "AgentContext"], Awaitable[None]] | None = None,
    ):
        """
        Args:
            hook_registry: 钩子注册表，用于通知 stream token 事件。
            on_reasoning: 可选回调，收到 reasoning 文本时调用。
                          stream_response 用它积累 ctx.state["reasoning"]；
                          stream_chat 不需要（默认忽略）。
        """
        self._thinking_mgr = ThinkingTagManager()
        self._coalescer = StreamCoalescer()
        # 五类标签网关（分册 08 §15.3）：emotion/action/navigate/avatar_tool
        # 从 chunk.data 透传；皮套工具开关与 motion 注册表读 settings 运行时值
        # （model_config 五键经 model.py 装配，见 apply_model_config_from_db）
        from app.core.config import settings

        self._tag_parser = TagStreamParser(
            translator=get_default_translator(),
            motion_registry=list(getattr(settings, "AVATAR_MOTION_REGISTRY", []) or []),
            avatar_tools_enabled=bool(getattr(settings, "AVATAR_TOOLS_ENABLED", False)),
        )
        self._hook_registry = hook_registry
        self._on_reasoning = on_reasoning

    @staticmethod
    def _apply_tag_events(
        data: dict[str, Any], events: list, ctx_state: dict[str, Any],
    ) -> None:
        """把网关结构化事件写入 StreamEvent.data（runner → SSE chunk 透传）。

        - emotion/action/navigate/avatar_tool：随 content chunk 下发前端（W4 契约字段）；
        - dispatch（phase=detected）：**不直接下发**，存入执行上下文挂点
          ctx_state[TASK_DISPATCH_DETECTED_KEY]（list[dict]，给派发中间件的约定
          字段，见 app/core/tags/definitions.py）——若派发中间件不存在，detected
          事件就地终结，前端感知不到（优雅降级）。
        """
        for ev in events:
            if ev.kind == "dispatch":
                ctx_state.setdefault(TASK_DISPATCH_DETECTED_KEY, []).append(ev.value)
                continue
            data[ev.kind] = ev.value

    async def process_stream(
        self,
        source: AsyncIterator[StreamEvent],
        ctx: "AgentContext",
    ) -> AsyncIterator[StreamEvent]:
        """包装 LLM 流，注入 thinking/coalesce/标签网关处理管线。"""
        async for chunk in source:
            if chunk.type == "content":
                content = chunk.data.get("content", "")

                # 1. Thinking 标签分流
                content_text, reasoning_text = self._thinking_mgr.process(content)

                if reasoning_text:
                    if self._on_reasoning:
                        await self._on_reasoning(reasoning_text, ctx)
                    try:
                        await self._hook_registry.notify(
                            HookRegistry.ON_STREAM_TOKEN,
                            ctx, reasoning_text, "reasoning",
                        )
                    except Exception:
                        logger.warning(
                            f"[StreamProcessor] reasoning hook 事件通知失败已丢弃: "
                            f"agent={ctx.extra.get('agent_id') or ctx.state.get('chat_id') or '?'}",
                            exc_info=True,
                        )

                # 2. 流式 chunk 合并
                if content_text:
                    merged = await self._coalescer.feed(content_text)
                    if merged:
                        # 3. 五类标签网关清洗（emotion/action/navigate/avatar_tool/dispatch）
                        clean_content, tag_events = self._tag_parser.feed(merged)
                        chunk.data["content"] = clean_content
                        self._apply_tag_events(chunk.data, tag_events, ctx.state)
                        try:
                            await self._hook_registry.notify(
                                HookRegistry.ON_STREAM_TOKEN,
                                ctx, merged, "content",
                            )
                        except Exception:
                            logger.warning(
                                f"[StreamProcessor] content hook 事件通知失败已丢弃: "
                                f"agent={ctx.extra.get('agent_id') or ctx.state.get('chat_id') or '?'}",
                                exc_info=True,
                            )
                    else:
                        continue  # 缓冲区未达阈值
                else:
                    continue  # 纯 thinking 内容

            yield chunk

        # 流结束，flush 合并器缓冲区
        remaining = self._coalescer.flush()
        if remaining:
            clean_content, tag_events = self._tag_parser.feed(remaining)
            if clean_content or tag_events:
                data: dict[str, Any] = {"content": clean_content}
                self._apply_tag_events(data, tag_events, ctx.state)
                yield StreamEvent("content", data)
                try:
                    await self._hook_registry.notify(
                        HookRegistry.ON_STREAM_TOKEN, ctx, remaining, "content",
                    )
                except Exception:
                    logger.warning(
                        f"[StreamProcessor] flush 残留 hook 事件通知失败已丢弃: "
                        f"agent={ctx.extra.get('agent_id') or ctx.state.get('chat_id') or '?'}",
                        exc_info=True,
                    )
        # 断流净化：未闭合的疑似标签残片直接丢弃（分册 08 §15.3 缓冲匹配条款）
        self._tag_parser.flush()
