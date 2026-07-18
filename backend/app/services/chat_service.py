import asyncio
import time
import uuid
from typing import Any
from loguru import logger

from app.core.config import settings
from app.core.context import get_context_manager
from app.core.utils import utc_now, sse_response, sse_data
from app.core.tools import tool_registry
from app.core.tools.orchestrator import tool_orchestrator
from app.runtime.provider.llm.adapter import llm_adapter
from app.runtime.provider.llm.types import RouteHint, StreamEvent
from app.runtime.provider.llm.providers import LLMResponse
from app.infrastructure.database.conversation_store import conversation_store
from app.schemas.chat import ChatStreamChunk
from app.services.avatar_manager import EmotionStreamParser, strip_emotion_tags
from app.services.context_service import ContextService
from app.services.suggestion_service import SuggestionService
from app.services.usage_tracker import usage_tracker
from app.services.distillation_service import distillation_service
from app.core.agents.middleware.base import HookRegistry


# ──────────────────────────────────────────────────────────────
# 流式 chunk 合并器
# ──────────────────────────────────────────────────────────────

class StreamCoalescer:
    """流式 chunk 合并器 - 合并小 chunk 减少 UI 更新频率。

    借鉴 DeepTutor 的 stream_coalesce_chars / stream_coalesce_seconds 设计。
    """

    def __init__(self, coalesce_chars: int = 64, coalesce_seconds: float = 0.04):
        self.coalesce_chars = coalesce_chars
        self.coalesce_seconds = coalesce_seconds
        self._buffer: str = ""
        self._last_flush_time: float = 0

    async def feed(self, token: str) -> str | None:
        """输入一个 token，返回合并后的 chunk（如果达到阈值），否则返回 None。"""
        self._buffer += token
        now = time.monotonic()
        if len(self._buffer) >= self.coalesce_chars or \
           (now - self._last_flush_time) >= self.coalesce_seconds:
            return self.flush()
        return None

    def flush(self) -> str:
        """强制输出缓冲区内容。"""
        result = self._buffer
        self._buffer = ""
        self._last_flush_time = time.monotonic()
        return result


# ──────────────────────────────────────────────────────────────
# Thinking 标签管理器
# ──────────────────────────────────────────────────────────────

class ThinkingTagManager:
    """Thinking 标签管理器 - 在流式中检测 <think>/</think> 标签并正确分流。"""

    def __init__(self):
        self._in_thinking = False
        self._tag_buffer = ""  # 用于处理标签跨 chunk 的情况

    def process(self, text: str) -> tuple[str, str]:
        """处理文本，返回 (content_text, reasoning_text)。"""
        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        i = 0
        combined = self._tag_buffer + text
        self._tag_buffer = ""

        while i < len(combined):
            if not self._in_thinking:
                think_start = combined.find("<think>", i)
                if think_start == -1:
                    content_parts.append(combined[i:])
                    break
                else:
                    content_parts.append(combined[i:think_start])
                    self._in_thinking = True
                    i = think_start + len("<think>")
            else:
                think_end = combined.find("</think>", i)
                if think_end == -1:
                    # 检查是否是不完整的标签在末尾
                    remaining = combined[i:]
                    if remaining.endswith("<") or remaining.endswith("</") or \
                       remaining.endswith("</t") or remaining.endswith("</th") or \
                       remaining.endswith("</thi") or remaining.endswith("</thin") or \
                       remaining.endswith("</think"):
                        # 可能是不完整标签，缓存等待下一个 chunk
                        self._tag_buffer = remaining
                        break
                    reasoning_parts.append(remaining)
                    break
                else:
                    reasoning_parts.append(combined[i:think_end])
                    self._in_thinking = False
                    i = think_end + len("</think>")

        return "".join(content_parts), "".join(reasoning_parts)


# ──────────────────────────────────────────────────────────────
# 全局钩子注册表
# ──────────────────────────────────────────────────────────────

# 全局钩子注册表：用于运行时动态注册的观察者回调
chat_hook_registry = HookRegistry()


async def _on_chat_turn_complete_usage(
    ctx: "AgentContext", result: dict[str, Any],
) -> None:
    """默认 on_chat_turn_complete 钩子：记录回合级 usage 日志。"""
    usage = result.get("usage")
    if usage:
        logger.debug(
            f"[HookRegistry] 回合完成: iterations={result.get('iterations', 0)}, "
            f"usage={usage}"
        )


async def _on_stream_token_counter(
    ctx: "AgentContext", token: str, token_type: str,
) -> None:
    """默认 on_stream_token 钩子：累计流式 token 数。"""
    counter_key = f"_stream_token_count_{token_type}"
    ctx.state[counter_key] = ctx.state.get(counter_key, 0) + 1


# 注册默认钩子
chat_hook_registry.register(
    HookRegistry.ON_CHAT_TURN_COMPLETE, _on_chat_turn_complete_usage,
)
chat_hook_registry.register(
    HookRegistry.ON_STREAM_TOKEN, _on_stream_token_counter,
)


class ChatService:
    def __init__(self, context: ContextService, suggestions: SuggestionService):
        self._llm_semaphore = asyncio.Semaphore(settings.LLM_MAX_CONCURRENT_REQUESTS)
        self._context = context
        self._suggestions = suggestions

    @staticmethod
    async def persist_conv(conv_id: str, conv: dict) -> None:
        conv["updated_at"] = utc_now()
        await conversation_store.set_async(conv_id, conv)

    @staticmethod
    def save_user_message(
        conv: dict,
        content: str,
        file_content: str | None = None,
        file_name: str | None = None,
        file_type: str | None = None,
    ) -> None:
        if not content and not file_content and not file_name:
            return
        entry: dict = {"role": "user", "content": content}
        if file_content:
            entry["file_content"] = file_content
        if file_name:
            entry["file_name"] = file_name
        if file_type:
            entry["file_type"] = file_type
        if file_content and file_name:
            entry["files"] = [{"name": file_name, "type": file_type, "content": file_content}]
        last = conv["messages"][-1] if conv["messages"] else None
        if last and last.get("role") == "user":
            for key in ("file_content", "file_name", "file_type", "files"):
                if key in entry:
                    last[key] = entry[key]
            if not last.get("content"):
                last["content"] = content
        else:
            conv["messages"].append(entry)

    @staticmethod
    def save_assistant_message(conv: dict, state: dict, versions: list[dict] | None = None) -> None:
        content = state["content"] or "[已中断]"
        reasoning = state["reasoning"] or None
        interrupted = state["aborted"]
        entry: dict = {"role": "assistant", "content": content, "id": str(uuid.uuid4())}
        if reasoning:
            entry["reasoning_content"] = reasoning
        if interrupted:
            entry["interrupted"] = True
        if versions:
            new_version: dict = {"content": content, "id": str(uuid.uuid4())}
            if reasoning:
                new_version["reasoning_content"] = reasoning
            if state.get("model"):
                new_version["model"] = state["model"]
            if state.get("provider"):
                new_version["provider"] = state["provider"]
            if state.get("suggested_questions"):
                new_version["suggested_questions"] = state["suggested_questions"]
            all_versions = list(versions) + [new_version]
            entry["versions"] = all_versions
            entry["current_version"] = len(all_versions) - 1
        last = conv["messages"][-1] if conv["messages"] else None
        if not last or last.get("id") != entry.get("id"):
            conv["messages"].append(entry)

        default_titles = {"新对话", "New Conversation"}
        if conv.get("title") in default_titles and len(conv["messages"]) >= 2:
            first_user_message = None
            for msg in conv["messages"]:
                if msg.get("role") == "user":
                    first_user_message = msg.get("content", "")
                    break

            if first_user_message:
                conv["title"] = first_user_message[:30].strip()
                if len(first_user_message) > 30:
                    conv["title"] += "..."

    async def non_stream_generate(
        self,
        state: dict,
        all_messages: list[dict],
        provider: str,
        model: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
        agent_id: str | None = None,
        conv_id: str | None = None,
    ) -> None:
        try:
            async with self._llm_semaphore:
                raw = await llm_adapter.chat(
                    messages=all_messages,
                    provider_name=provider,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                    route_hint=RouteHint.CHAT,
                )
            if isinstance(raw, dict):
                state["content"] = strip_emotion_tags(raw.get("content", ""))
                if raw.get("reasoning"):
                    state["reasoning"] = raw["reasoning"]
                if raw.get("usage"):
                    try:
                        usage_tracker.record_usage(
                            provider=provider, model=model,
                            usage=raw["usage"], agent_id=agent_id, conv_id=conv_id,
                        )
                    except Exception as ut_err:
                        logger.warning(f"[ChatService] Usage tracking failed: {ut_err}")
            elif isinstance(raw, LLMResponse) and raw.usage:
                state["content"] = strip_emotion_tags(raw.content if hasattr(raw, "content") else str(raw))
                try:
                    usage_tracker.record_usage(
                        provider=provider, model=model,
                        usage=raw.usage, agent_id=agent_id, conv_id=conv_id,
                    )
                except Exception as ut_err:
                    logger.warning(f"[ChatService] Usage tracking failed: {ut_err}")
            else:
                state["content"] = strip_emotion_tags(raw if isinstance(raw, str) else str(raw))
                try:
                    usage_tracker.record_usage(
                        provider=provider, model=model,
                        agent_id=agent_id, conv_id=conv_id,
                    )
                except Exception as ut_err:
                    logger.warning(f"[ChatService] Usage tracking failed: {ut_err}")
        except Exception as e:
            logger.error(f"[API] Non-stream error: {e}", exc_info=True)
            state["aborted"] = True
            state["content"] = "[Error] An internal error occurred"

    async def stream_chat(
        self,
        messages: list[dict],
        request,
        provider: str,
        model: str,
        agent_id: str | None = None,
    ):
        """流式对话（/chat/completions stream=true）。

        基于 AgentRunner + 中间件管道实现：
        - 工具过滤（disable_tools）由 ToolFilterMiddleware 处理
        - 工具执行 + tool_event SSE 由 ToolExecutionMiddleware 处理
        - 特殊工具（delegate/scheduler/collaboration）由 SpecialToolMiddleware 处理
        - usage 记录由 UsageTrackMiddleware 处理
        - 循环边界由 LoopGuardMiddleware 检测

        llm_call_fn 内通过 EmotionStreamParser 清洗 content，确保 runner 积累
        干净内容（无 emotion 标签），emotion 通过 chunk.data["emotion"] 传入 SSE。
        """
        from app.core.agents.middleware.base import AgentContext

        chat_id = str(uuid.uuid4())
        parser = EmotionStreamParser()

        # Agent 集群调用：子 Agent 请求设置递归深度 contextvar
        is_sub_agent = getattr(request, "is_sub_agent", False)
        depth_token = None
        if is_sub_agent:
            from app.core.agents.cluster.agent_tool import set_luominest_agent_call_depth
            depth_token = set_luominest_agent_call_depth(getattr(request, "agent_depth", 0))

        # 工具支持：获取工具列表（disable_tools/tool_whitelist 过滤由 ToolFilterMiddleware 处理）
        available_tools = tool_orchestrator.get_tools_for_llm(provider, model) if tool_registry.list_names() else None
        use_tools = bool(available_tools) and llm_adapter.supports_tool_calls(provider, model)
        if available_tools and not use_tools:
            logger.info(f"[STREAM] stream_chat: Provider {provider}/{model} 不支持工具调用，纯对话模式")

        # 按对话模式设置工具白名单（NORMAL 模式仅允许任务视图操作工具）
        chat_mode_str = getattr(request, "chat_mode", "normal")
        tool_whitelist = None
        if chat_mode_str == "normal":
            from app.core.chat_mode import ChatMode, get_tool_config
            tool_whitelist = get_tool_config(ChatMode.NORMAL).get("whitelist")

        # 构建 AgentContext
        ctx = AgentContext(
            messages=[dict(m) for m in messages],
            tools=available_tools if use_tools else None,
            route_hint=RouteHint.CHAT,
            state={"chat_id": chat_id, "provider": provider, "model": model},
            extra={
                "scene": "chat",
                "is_stream": True,
                "disable_tools": getattr(request, "disable_tools", None),
                "tool_whitelist": tool_whitelist,
                "agent_id": agent_id,
            },
        )

        # llm_call_fn：信号量内调用 LLM，content 经 EmotionStreamParser + ThinkingTagManager 清洗
        thinking_mgr = ThinkingTagManager()
        coalescer = StreamCoalescer()

        async def llm_call_fn(ctx):
            async with self._llm_semaphore:
                async for chunk in llm_adapter.chat_stream(
                    messages=ctx.messages,
                    tools=ctx.tools,
                    provider_name=provider,
                    model=model,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    top_p=request.top_p,
                    route_hint=RouteHint.CHAT,
                ):
                    if chunk.type == "content":
                        content = chunk.data.get("content", "")
                        # Thinking 标签分流
                        content_text, reasoning_text = thinking_mgr.process(content)
                        if reasoning_text:
                            # 通过钩子通知 reasoning token
                            try:
                                await chat_hook_registry.notify(
                                    HookRegistry.ON_STREAM_TOKEN, ctx, reasoning_text, "reasoning",
                                )
                            except Exception:
                                pass
                        # 流式 chunk 合并
                        if content_text:
                            merged = await coalescer.feed(content_text)
                            if merged:
                                clean_content, emotion = parser.feed(merged)
                                chunk.data["content"] = clean_content
                                if emotion:
                                    chunk.data["emotion"] = emotion
                                # 通过钩子通知 content token
                                try:
                                    await chat_hook_registry.notify(
                                        HookRegistry.ON_STREAM_TOKEN, ctx, merged, "content",
                                    )
                                except Exception:
                                    pass
                            else:
                                continue  # 缓冲区未达阈值，跳过本次发射
                        else:
                            continue  # 纯 thinking 内容，不发射 content 事件
                    yield chunk
                # 流结束后 flush 缓冲区
                remaining = coalescer.flush()
                if remaining:
                    clean_content, emotion = parser.feed(remaining)
                    if clean_content:
                        yield StreamEvent("content", {"content": clean_content, **({"emotion": emotion} if emotion else {})})
                        try:
                            await chat_hook_registry.notify(
                                HookRegistry.ON_STREAM_TOKEN, ctx, remaining, "content",
                            )
                        except Exception:
                            pass

        runner = tool_orchestrator.create_runner({
            "scene": "chat",
            "is_stream": True,
            "hook_registry": chat_hook_registry,
        })

        try:
            async for sse_str in runner.run_stream(ctx, llm_call_fn):
                yield sse_str

            # 计算压缩后 token 数：使用 runner 执行后的 ctx.messages（已压缩，反映实际上下文使用量）
            try:
                ctx_mgr = get_context_manager(provider, model)
                context_tokens = ctx_mgr.token_counter.count_tokens(ctx.messages)
                context_max_tokens = ctx_mgr.max_context_tokens or None
            except Exception:
                context_tokens = None
                context_max_tokens = None

            done_data = ChatStreamChunk(
                id=chat_id, content="", model=model, provider=provider,
                done=True, context_tokens=context_tokens,
                context_max_tokens=context_max_tokens,
            )
            yield sse_data(done_data)
        except Exception as e:
            logger.error(f"[STREAM] stream_chat error: {e}", exc_info=True)
            yield sse_data(ChatStreamChunk(id=chat_id, content='[Error] An internal error occurred', model=model, provider=provider))
            done_data = ChatStreamChunk(id=chat_id, content="", model=model, provider=provider, done=True)
            yield sse_data(done_data)
        finally:
            if depth_token is not None:
                from app.core.agents.cluster.agent_tool import reset_luominest_agent_call_depth
                reset_luominest_agent_call_depth(depth_token)
            # /chat/completions 流式模式写入记忆（子 Agent 跳过，避免污染主 Agent 记忆）
            if not is_sub_agent:
                try:
                    user_msgs = [m for m in messages if m.get("role") == "user"]
                    if user_msgs:
                        await self._context.schedule_memory_update(
                            messages, f"completions-{chat_id[:8]}", agent_id,
                            llm_adapter=llm_adapter,
                        )
                except Exception as mem_err:
                    logger.warning(f"[STREAM] /chat/completions memory update failed: {mem_err}")

    async def stream_response(
        self,
        conv_id: str,
        conv: dict,
        request,
        all_messages: list,
        provider: str,
        model: str,
        agent_id: str | None,
        state: dict,
        start_time: float,
        versions: list[dict] | None = None,
    ):
        """主对话流式响应（/api/chat stream 模式）。

        基于 AgentRunner + 中间件管道实现：
        - 记忆访问权限由 MemoryAccessMiddleware 设置/重置
        - 工具执行 + tool_event SSE 由 ToolExecutionMiddleware 处理
        - 特殊工具（delegate/scheduler/collaboration）由 SpecialToolMiddleware 处理
        - usage 记录由 UsageTrackMiddleware 处理
        - 循环边界由 LoopGuardMiddleware 检测

        流式结束后执行：state 同步、推荐问题生成、消息持久化、done 事件、记忆更新、蒸馏。
        """
        from app.core.agents.middleware.base import AgentContext
        from app.core.agents.memory_access import MEMORY_ACCESS_NONE, MEMORY_ACCESS_READ_WRITE
        from app.services.context_service import is_main_agent

        chat_id = str(uuid.uuid4())
        parser = EmotionStreamParser()

        # 工具支持
        available_tools = tool_orchestrator.get_tools_for_llm(provider, model) if tool_registry.list_names() else None
        use_tools = bool(available_tools) and llm_adapter.supports_tool_calls(provider, model)
        if available_tools and not use_tools:
            logger.info(f"[STREAM] Provider {provider}/{model} 不支持工具调用，本次以纯对话模式运行")

        # 记忆访问权限：主 Agent 可读写，联系人 Agent 无权限
        memory_access = MEMORY_ACCESS_READ_WRITE if is_main_agent(agent_id) else MEMORY_ACCESS_NONE

        # 按对话模式设置工具白名单（NORMAL 模式仅允许任务视图操作工具）
        chat_mode_str = getattr(request, "chat_mode", "normal")
        tool_whitelist = None
        if chat_mode_str == "normal":
            from app.core.chat_mode import ChatMode, get_tool_config
            tool_whitelist = get_tool_config(ChatMode.NORMAL).get("whitelist")

        # 构建 AgentContext（all_messages 共享引用，runner 追加 assistant/tool 消息）
        ctx = AgentContext(
            messages=all_messages,
            tools=available_tools if use_tools else None,
            route_hint=RouteHint.CHAT,
            state={"chat_id": chat_id, "provider": provider, "model": model},
            extra={
                "scene": "chat",
                "is_stream": True,
                "memory_access": memory_access,
                "tool_whitelist": tool_whitelist,
                "agent_id": agent_id,
                "conv_id": conv_id,
            },
        )

        # llm_call_fn：信号量内调用 LLM，content 经 EmotionStreamParser + ThinkingTagManager 清洗
        thinking_mgr = ThinkingTagManager()
        coalescer = StreamCoalescer()

        async def llm_call_fn(ctx):
            async with self._llm_semaphore:
                async for chunk in llm_adapter.chat_stream(
                    messages=ctx.messages,
                    tools=ctx.tools,
                    provider_name=provider,
                    model=model,
                    temperature=request.temperature or 0.7,
                    max_tokens=request.max_tokens or 4096,
                    top_p=request.top_p or 0.9,
                    route_hint=RouteHint.CHAT,
                ):
                    if chunk.type == "content":
                        content = chunk.data.get("content", "")
                        # Thinking 标签分流
                        content_text, reasoning_text = thinking_mgr.process(content)
                        if reasoning_text:
                            # 积累 reasoning 到 ctx.state
                            ctx.state["reasoning"] = ctx.state.get("reasoning", "") + reasoning_text
                            try:
                                await chat_hook_registry.notify(
                                    HookRegistry.ON_STREAM_TOKEN, ctx, reasoning_text, "reasoning",
                                )
                            except Exception:
                                pass
                        # 流式 chunk 合并
                        if content_text:
                            merged = await coalescer.feed(content_text)
                            if merged:
                                clean_content, emotion = parser.feed(merged)
                                chunk.data["content"] = clean_content
                                if emotion:
                                    chunk.data["emotion"] = emotion
                                try:
                                    await chat_hook_registry.notify(
                                        HookRegistry.ON_STREAM_TOKEN, ctx, merged, "content",
                                    )
                                except Exception:
                                    pass
                            else:
                                continue
                        else:
                            continue
                    yield chunk
                # 流结束后 flush 缓冲区
                remaining = coalescer.flush()
                if remaining:
                    clean_content, emotion = parser.feed(remaining)
                    if clean_content:
                        yield StreamEvent("content", {"content": clean_content, **({"emotion": emotion} if emotion else {})})
                        try:
                            await chat_hook_registry.notify(
                                HookRegistry.ON_STREAM_TOKEN, ctx, remaining, "content",
                            )
                        except Exception:
                            pass

        runner = tool_orchestrator.create_runner({
            "scene": "chat",
            "is_stream": True,
            "hook_registry": chat_hook_registry,
        })

        async def generator():
            suggested_questions: list[str] = []
            try:
                async for sse_str in runner.run_stream(ctx, llm_call_fn):
                    yield sse_str
            except Exception as e:
                logger.error(f"[STREAM] Aborted: conv={conv_id}, error={e}", exc_info=True)
                state["aborted"] = True
                error_chunk = ChatStreamChunk(
                    id=chat_id, content="[Error] An internal error occurred",
                    model=model, provider=provider,
                )
                yield sse_data(error_chunk)
            finally:
                # 同步 ctx.state → state（供持久化使用）
                state["content"] = ctx.state.get("content", "")
                state["reasoning"] = ctx.state.get("reasoning", "")
                state["aborted"] = bool(state.get("aborted", False)) or bool(ctx.state.get("aborted", False))
                state["model"] = model
                state["provider"] = provider

                # 推荐问题生成 + 消息持久化
                try:
                    if not state["aborted"] and state["content"]:
                        try:
                            suggested_questions = await self._suggestions.generate_suggestions_for_conv(
                                conv_id=conv_id,
                                messages=[dict(m) for m in conv["messages"]],
                                agent_id=agent_id,
                                provider=provider,
                                model=model,
                            )
                        except Exception as sq_err:
                            logger.warning(f"[STREAM] Suggested questions failed: conv={conv_id}, error={sq_err}")
                        state["suggested_questions"] = suggested_questions if suggested_questions else None

                    persist_state = dict(state)
                    if persist_state["aborted"] and persist_state["content"].startswith("[Error]"):
                        persist_state["content"] = ""
                    self.save_assistant_message(conv, persist_state, versions=versions)
                    await self.persist_conv(conv_id, conv)
                except Exception as persist_err:
                    logger.error(f"[STREAM] Persist failed: conv={conv_id}, error={persist_err}")

                # done 事件
                try:
                    # 计算压缩后 token 数：使用 ctx.messages（已压缩，反映实际上下文使用量）
                    # 而非 conv["messages"]（未压缩的存储版本，会导致 context_tokens 远大于实际值）
                    try:
                        ctx_mgr = get_context_manager(provider, model)
                        context_tokens = ctx_mgr.token_counter.count_tokens(ctx.messages)
                        context_max_tokens = ctx_mgr.max_context_tokens or None
                    except Exception:
                        context_tokens = None
                        context_max_tokens = None

                    done_chunk = ChatStreamChunk(
                        id=chat_id, content="", model=model, provider=provider,
                        done=True, suggested_questions=suggested_questions or None,
                        context_tokens=context_tokens,
                        context_max_tokens=context_max_tokens,
                    )
                    yield sse_data(done_chunk)
                except Exception as done_err:
                    logger.debug(f"[STREAM] Done event send failed (client may have disconnected): {done_err}")

                # 记忆更新
                try:
                    await self._context.schedule_memory_update(
                        [dict(m) for m in conv["messages"]], conv_id, agent_id,
                        llm_adapter=llm_adapter,
                    )
                except Exception as schedule_err:
                    logger.warning(f"[STREAM] Memory update scheduling failed: {schedule_err}")

                # 蒸馏
                try:
                    await distillation_service.maybe_distill(agent_id, conv_id, conv["messages"], llm_adapter)
                except Exception as distill_err:
                    logger.warning(f"[STREAM] Distillation failed: {distill_err}")

        return sse_response(
            generator(),
        )
