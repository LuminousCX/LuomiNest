"""
流式处理器 —— 统一 stream_chat / stream_response 中重复的流式 chunk 处理管线。

将 ThinkingTagManager + StreamCoalescer + EmotionStreamParser 三条管线
封装为单一可组合的异步生成器包装器，消除 ~80% 的重复代码。
"""
from __future__ import annotations

from typing import AsyncIterator, Callable, Awaitable

from loguru import logger

from app.runtime.provider.llm.types import StreamEvent
from app.services.avatar_manager import EmotionStreamParser
from app.core.agents.middleware.base import HookRegistry


class StreamProcessor:
    """流式 chunk 处理管线：thinking 分流 → chunk 合并 → emotion 清洗。

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
        from app.services.chat_service import ThinkingTagManager, StreamCoalescer

        self._thinking_mgr = ThinkingTagManager()
        self._coalescer = StreamCoalescer()
        self._emotion_parser = EmotionStreamParser()
        self._hook_registry = hook_registry
        self._on_reasoning = on_reasoning

    async def process_stream(
        self,
        source: AsyncIterator[StreamEvent],
        ctx: "AgentContext",
    ) -> AsyncIterator[StreamEvent]:
        """包装 LLM 流，注入 thinking/coalesce/emotion 处理管线。"""
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
                        pass

                # 2. 流式 chunk 合并
                if content_text:
                    merged = await self._coalescer.feed(content_text)
                    if merged:
                        # 3. Emotion 清洗
                        clean_content, emotion = self._emotion_parser.feed(merged)
                        chunk.data["content"] = clean_content
                        if emotion:
                            chunk.data["emotion"] = emotion
                        try:
                            await self._hook_registry.notify(
                                HookRegistry.ON_STREAM_TOKEN,
                                ctx, merged, "content",
                            )
                        except Exception:
                            pass
                    else:
                        continue  # 缓冲区未达阈值
                else:
                    continue  # 纯 thinking 内容

            yield chunk

        # 流结束，flush 合并器缓冲区
        remaining = self._coalescer.flush()
        if remaining:
            clean_content, emotion = self._emotion_parser.feed(remaining)
            if clean_content:
                yield StreamEvent(
                    "content",
                    {"content": clean_content, **({"emotion": emotion} if emotion else {})},
                )
                try:
                    await self._hook_registry.notify(
                        HookRegistry.ON_STREAM_TOKEN, ctx, remaining, "content",
                    )
                except Exception:
                    pass
