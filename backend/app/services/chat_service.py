import asyncio
import uuid
from datetime import datetime, timezone
from loguru import logger

from app.core.config import settings
from app.core.tools import tool_registry
from app.core.tools.orchestrator import tool_orchestrator
from app.runtime.provider.llm.adapter import llm_adapter
from app.runtime.provider.llm.types import RouteHint
from app.runtime.provider.llm.providers import LLMResponse
from app.infrastructure.database.conversation_store import conversation_store
from app.schemas.chat import ChatStreamChunk
from app.services.avatar_manager import EmotionStreamParser, strip_emotion_tags
from app.services.context_service import ContextService
from app.services.suggestion_service import SuggestionService
from app.services.usage_tracker import usage_tracker
from app.services.distillation_service import distillation_service

from fastapi.responses import StreamingResponse


class ChatService:
    def __init__(self, context: ContextService, suggestions: SuggestionService):
        self._llm_semaphore = asyncio.Semaphore(settings.LLM_MAX_CONCURRENT_REQUESTS)
        self._context = context
        self._suggestions = suggestions

    @staticmethod
    async def persist_conv(conv_id: str, conv: dict) -> None:
        conv["updated_at"] = datetime.now(timezone.utc).isoformat()
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

        # 工具支持：获取工具列表（disable_tools 过滤由 ToolFilterMiddleware 处理）
        available_tools = tool_orchestrator.get_tools_for_llm() if tool_registry.list_names() else None
        use_tools = bool(available_tools) and llm_adapter.supports_tool_calls(provider, model)
        if available_tools and not use_tools:
            logger.info(f"[STREAM] stream_chat: Provider {provider}/{model} 不支持工具调用，纯对话模式")

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
                "agent_id": agent_id,
            },
        )

        # llm_call_fn：信号量内调用 LLM，content 经 EmotionStreamParser 清洗后传给 runner
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
                        clean_content, emotion = parser.feed(content)
                        chunk.data["content"] = clean_content
                        if emotion:
                            chunk.data["emotion"] = emotion
                    yield chunk

        runner = tool_orchestrator.create_runner({
            "scene": "chat",
            "is_stream": True,
        })

        try:
            async for sse_str in runner.run_stream(ctx, llm_call_fn):
                yield sse_str

            done_data = ChatStreamChunk(id=chat_id, content="", model=model, provider=provider, done=True)
            yield f"data: {done_data.model_dump_json()}\n\n"
        except Exception as e:
            logger.error(f"[STREAM] stream_chat error: {e}", exc_info=True)
            yield (
                f"data: {ChatStreamChunk(id=chat_id, content='[Error] An internal error occurred', model=model, provider=provider).model_dump_json()}\n\n"
            )
            done_data = ChatStreamChunk(id=chat_id, content="", model=model, provider=provider, done=True)
            yield f"data: {done_data.model_dump_json()}\n\n"
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
        available_tools = tool_orchestrator.get_tools_for_llm() if tool_registry.list_names() else None
        use_tools = bool(available_tools) and llm_adapter.supports_tool_calls(provider, model)
        if available_tools and not use_tools:
            logger.info(f"[STREAM] Provider {provider}/{model} 不支持工具调用，本次以纯对话模式运行")

        # 记忆访问权限：主 Agent 可读写，联系人 Agent 无权限
        memory_access = MEMORY_ACCESS_READ_WRITE if is_main_agent(agent_id) else MEMORY_ACCESS_NONE

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
                "agent_id": agent_id,
                "conv_id": conv_id,
            },
        )

        # llm_call_fn：信号量内调用 LLM，content 经 EmotionStreamParser 清洗
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
                        clean_content, emotion = parser.feed(content)
                        chunk.data["content"] = clean_content
                        if emotion:
                            chunk.data["emotion"] = emotion
                    yield chunk

        runner = tool_orchestrator.create_runner({
            "scene": "chat",
            "is_stream": True,
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
                yield f"data: {error_chunk.model_dump_json()}\n\n"
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
                    done_chunk = ChatStreamChunk(
                        id=chat_id, content="", model=model, provider=provider,
                        done=True, suggested_questions=suggested_questions or None,
                    )
                    yield f"data: {done_chunk.model_dump_json()}\n\n"
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

        return StreamingResponse(
            generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
        )
