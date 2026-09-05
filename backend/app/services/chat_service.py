import asyncio
import time
import uuid
from typing import Any

from loguru import logger

from app.core.agents.cluster.agent_tool import (
    reset_luominest_agent_call_depth,
    set_luominest_agent_call_depth,
)
from app.core.agents.memory_access import (
    MEMORY_ACCESS_NONE,
    MEMORY_ACCESS_READ_MAIN,
    MEMORY_ACCESS_READ_WRITE,
)
from app.core.agents.middleware.base import AgentContext, HookRegistry
from app.core.chat_mode import ChatMode, get_tool_config
from app.core.config import settings
from app.core.context import get_context_manager
from app.core.domain_policy import resolve_domain_policy
from app.core.tools import tool_registry
from app.core.tools.orchestrator import tool_orchestrator
from app.core.utils import require_store, sse_data, sse_response, utc_now
from app.infrastructure.database.conversation_store import conversation_store
from app.runtime.provider.llm.adapter import llm_adapter
from app.runtime.provider.llm.types import LLMResponse, RouteHint
from app.schemas.chat import ChatStreamChunk
from app.security.prompt_security import wrap_untrusted_content
from app.services.avatar_manager import strip_emotion_tags
from app.services.context_service import ContextService
from app.services.distillation_service import distillation_service
from app.services.stream_processor import StreamProcessor
from app.services.suggestion_service import SuggestionService
from app.services.usage_tracker import usage_tracker

# ──────────────────────────────────────────────────────────────
# 全局钩子注册表
# ──────────────────────────────────────────────────────────────

# 全局钩子注册表：用于运行时动态注册的观察者回调
chat_hook_registry = HookRegistry()


def _build_normal_tool_whitelist(user_query: str) -> list[str]:
    """NORMAL 模式工具白名单：固定白名单 + S1b 按用户消息召回的 top-K 工具（去重）。

    召回失败不阻断对话（退化为纯固定白名单）。
    """
    whitelist = list(get_tool_config(ChatMode.NORMAL).get("whitelist") or [])
    try:
        for tool in tool_registry.search(user_query, top_k=6):
            if tool.name not in whitelist:
                whitelist.append(tool.name)
    except Exception:
        logger.debug("[ChatService] 工具召回失败，退化为固定白名单", exc_info=True)
    return whitelist


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
                            usage=raw["usage"], agent_id=agent_id, conversation_id=conv_id,
                        )
                    except Exception as ut_err:
                        logger.warning(f"[ChatService] Usage tracking failed: {ut_err}")
            elif isinstance(raw, LLMResponse) and raw.usage:
                state["content"] = strip_emotion_tags(raw.content if hasattr(raw, "content") else str(raw))
                try:
                    usage_tracker.record_usage(
                        provider=provider, model=model,
                        usage=raw.usage, agent_id=agent_id, conversation_id=conv_id,
                    )
                except Exception as ut_err:
                    logger.warning(f"[ChatService] Usage tracking failed: {ut_err}")
            else:
                state["content"] = strip_emotion_tags(raw if isinstance(raw, str) else str(raw))
                try:
                    usage_tracker.record_usage(
                        provider=provider, model=model,
                        agent_id=agent_id, conversation_id=conv_id,
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
        domain: str = "",
        scene: str = "",
        user_key: str = "",
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
        chat_id = str(uuid.uuid4())

        # Agent 集群调用：子 Agent 请求设置递归深度 contextvar
        is_sub_agent = getattr(request, "is_sub_agent", False)
        depth_token = None
        if is_sub_agent:
            depth_token = set_luominest_agent_call_depth(getattr(request, "agent_depth", 0))

        # 工具支持：获取工具列表（disable_tools/tool_whitelist 过滤由 ToolFilterMiddleware 处理）
        available_tools = tool_orchestrator.get_tools_for_llm(provider, model) if tool_registry.list_names() else None
        use_tools = bool(available_tools) and llm_adapter.supports_tool_calls(provider, model)
        if available_tools and not use_tools:
            logger.info(f"[STREAM] stream_chat: Provider {provider}/{model} 不支持工具调用，纯对话模式")

        # 按对话模式设置工具白名单（NORMAL 模式：固定白名单 + S1b 按消息召回）
        chat_mode_str = getattr(request, "chat_mode", "normal")
        tool_whitelist = None
        if chat_mode_str == "normal":
            tool_whitelist = _build_normal_tool_whitelist(
                self._context.get_user_query(messages),
            )

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

        # 流式处理管线：thinking 分流 → chunk 合并 → emotion 清洗（已解耦到 StreamProcessor）
        processor = StreamProcessor(chat_hook_registry)

        async def llm_call_fn(ctx):
            async with self._llm_semaphore:
                async for chunk in processor.process_stream(
                    llm_adapter.chat_stream(
                        messages=ctx.messages,
                        tools=ctx.tools,
                        provider_name=provider,
                        model=model,
                        temperature=request.temperature,
                        max_tokens=request.max_tokens,
                        top_p=request.top_p,
                        route_hint=RouteHint.CHAT,
                    ),
                    ctx,
                ):
                    yield chunk

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
                reset_luominest_agent_call_depth(depth_token)
            # /chat/completions 流式模式写入记忆（子 Agent 跳过，避免污染主 Agent 记忆）
            if not is_sub_agent:
                try:
                    user_msgs = [m for m in messages if m.get("role") == "user"]
                    if user_msgs:
                        await self._context.schedule_memory_update(
                            messages, f"completions-{chat_id[:8]}", agent_id,
                            llm_adapter=llm_adapter,
                            domain=domain, scene=scene, user_key=user_key,
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
        notice: str = "",
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
        chat_id = str(uuid.uuid4())

        # 工具支持
        available_tools = tool_orchestrator.get_tools_for_llm(provider, model) if tool_registry.list_names() else None
        use_tools = bool(available_tools) and llm_adapter.supports_tool_calls(provider, model)
        if available_tools and not use_tools:
            logger.info(f"[STREAM] Provider {provider}/{model} 不支持工具调用，本次以纯对话模式运行")

        # 对话域策略（B6）：记忆访问级别由 DomainPolicy 驱动（洋葱 §9），
        # 替换原 is_main_agent 单一判定；domain 取自会话（P0 已落库）
        conv_domain = conv.get("domain") or ""
        conv_scene = conv.get("scene") or ""
        conv_user_key = conv.get("user_key") or ""
        policy = resolve_domain_policy(
            conv_domain, scene=conv_scene, agent_id=agent_id, user_key=conv_user_key,
        )
        if policy.memory_write:
            memory_access = MEMORY_ACCESS_READ_WRITE
        elif policy.memory_read:
            memory_access = MEMORY_ACCESS_READ_MAIN
        else:
            memory_access = MEMORY_ACCESS_NONE

        # 按对话模式设置工具白名单（NORMAL 模式：固定白名单 + S1b 按消息召回）
        chat_mode_str = getattr(request, "chat_mode", "normal")
        tool_whitelist = None
        if chat_mode_str == "normal":
            tool_whitelist = _build_normal_tool_whitelist(
                self._context.get_user_query(conv["messages"]),
            )

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
                "tool_profile": policy.tool_profile,
                "agent_id": agent_id,
                "conv_id": conv_id,
                "domain": conv_domain,
            },
        )

        # 流式处理管线：thinking 分流 → chunk 合并 → emotion 清洗（已解耦到 StreamProcessor）
        async def _accumulate_reasoning(text: str, ctx: "AgentContext") -> None:
            ctx.state["reasoning"] = ctx.state.get("reasoning", "") + text

        processor = StreamProcessor(
            chat_hook_registry,
            on_reasoning=_accumulate_reasoning,
        )

        async def llm_call_fn(ctx):
            async with self._llm_semaphore:
                async for chunk in processor.process_stream(
                    llm_adapter.chat_stream(
                        messages=ctx.messages,
                        tools=ctx.tools,
                        provider_name=provider,
                        model=model,
                        temperature=request.temperature or 0.7,
                        max_tokens=request.max_tokens or 4096,
                        top_p=request.top_p or 0.9,
                        route_hint=RouteHint.CHAT,
                    ),
                    ctx,
                ):
                    yield chunk

        runner = tool_orchestrator.create_runner({
            "scene": "chat",
            "is_stream": True,
            "hook_registry": chat_hook_registry,
        })

        async def generator():
            suggested_questions: list[str] = []
            # 模型路由通知（如专业模式推理模型退化为主模型）：头部空 chunk 带出，前端 toast
            if notice:
                yield sse_data(ChatStreamChunk(
                    id=chat_id, content="", model=model, provider=provider, notice=notice,
                ))
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
                    prev_len = len(conv["messages"])
                    self.save_assistant_message(conv, persist_state, versions=versions)
                    if len(conv["messages"]) > prev_len:
                        # 热路径：增量追加 assistant 消息 + 同步元数据
                        if not await conversation_store.append_message_async(conv_id, conv["messages"][-1]):
                            await self.persist_conv(conv_id, conv)
                        await conversation_store.update_meta_async(
                            conv_id, {"title": conv.get("title", "New Conversation")}
                        )
                    else:
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

                # 记忆更新（DomainPolicy 门控，B6/B7）
                try:
                    await self._context.schedule_memory_update(
                        [dict(m) for m in conv["messages"]], conv_id, agent_id,
                        llm_adapter=llm_adapter,
                        domain=conv_domain, scene=conv_scene, user_key=conv_user_key,
                    )
                except Exception as schedule_err:
                    logger.warning(f"[STREAM] Memory update scheduling failed: {schedule_err}")

                # 蒸馏（平台域不写 owner 轨，防记忆污染，§8.5.5）
                try:
                    await distillation_service.maybe_distill(
                        agent_id, conv_id, conv["messages"], llm_adapter,
                        domain=conv_domain, user_key=conv_user_key,
                    )
                except Exception as distill_err:
                    logger.warning(f"[STREAM] Distillation failed: {distill_err}")

        return sse_response(
            generator(),
        )

    # ──────────────────────────────────────────────────────────────
    # 对话级共享辅助（自 endpoints/chat.py 下沉）
    # ──────────────────────────────────────────────────────────────

    async def resolve_agent_id(
        self, conv: dict, request_agent_id: str | None = None,
    ) -> str | None:
        """解析并回填 agent_id：优先 conv 存储，其次 request，最后 agents_store 兜底。"""
        agent_id = conv.get("agent_id") or request_agent_id
        if not agent_id:
            # 服务层非路由上下文无法 Depends 注入，经容器取同一门面单例
            from app.core.container import container
            all_agents = await container.agents_store.all_async()
            if all_agents:
                agent_id = all_agents[0].get("id")
        if agent_id and not conv.get("agent_id"):
            conv["agent_id"] = agent_id
        return agent_id

    async def trigger_final_distill(self, conv_id: str, conv: dict, adapter) -> None:
        """对话结束前触发最终蒸馏（离开/删除/批量删除共用）。"""
        if not (conv and conv.get("messages")):
            return
        agent_id = await self.resolve_agent_id(conv)
        await distillation_service.final_distill(
            agent_id, conv_id, conv["messages"], adapter,
            domain=conv.get("domain") or "", user_key=conv.get("user_key") or "",
        )

    async def rebuild_conversation_memory(
        self, conv_id: str, conv: dict, agent_id: str, adapter,
    ) -> None:
        """消息变更后重建对话级记忆（截断/删除消息共用）。"""
        from app.engines.memory import get_memory_engine
        engine = get_memory_engine(agent_id)
        engine.clear_conversation_data(conv_id)
        distillation_service.reset_distill_state(conv_id)
        conv_domain = conv.get("domain") or ""
        conv_scene = conv.get("scene") or ""
        conv_user_key = conv.get("user_key") or ""
        await self._context.schedule_memory_update(
            conv["messages"], conv_id, agent_id, llm_adapter=adapter,
            domain=conv_domain, scene=conv_scene, user_key=conv_user_key,
        )
        await distillation_service.maybe_distill(
            agent_id, conv_id, conv["messages"], adapter,
            domain=conv_domain, user_key=conv_user_key,
        )

    # ──────────────────────────────────────────────────────────────
    # 主对话业务流程（自 endpoints/chat.py 下沉）
    # ──────────────────────────────────────────────────────────────

    async def handle_completions(self, body, adapter, conversation_store):
        """/chat/completions 业务主流程：上下文组装 → 生成 → 命令守卫 → 记忆写回。

        stream=True 时返回 SSE StreamingResponse；
        非流式返回 dict {"aborted", "content", "model", "provider"}，
        由路由层整形响应/错误码。
        """
        start_time = time.time()
        resolved_provider = body.provider or adapter.default_provider
        resolved_model = body.model or adapter.get_provider(resolved_provider).default_model
        request_ts = body.timestamp or time.time()
        logger.info(
            f"[ChatService] POST /chat/completions - "
            f"provider={resolved_provider}, model={resolved_model}, "
            f"stream={body.stream}, ts={request_ts}, "
            f"is_sub_agent={body.is_sub_agent}, agent_depth={body.agent_depth}"
        )

        messages = [{"role": m.role, "content": m.content} for m in body.messages]

        conv_domain = ""
        conv_scene = ""
        conv_user_key = ""
        if body.conversation_id:
            conv_meta = await conversation_store.get_meta_async(body.conversation_id)
            if conv_meta:
                conv_domain = conv_meta.get("domain") or ""
                conv_scene = conv_meta.get("scene") or ""
                conv_user_key = conv_meta.get("user_key") or ""
        user_query = self._context.get_user_query(messages)
        system_prompt = self._context.build_system_prompt(body.agent_id, user_context=user_query)
        messages = [{"role": "system", "content": system_prompt}] + messages

        # 用户显式选择的技能注入（无条件注入完整 body，优先于关键词自动匹配）
        selected_block = self._context.build_user_selected_skills_prompt(body.skill_ids or [])
        if selected_block:
            messages.insert(0, {"role": "system", "content": selected_block})

        messages = self._context.inject_timestamp_prompt(messages)
        # 子 Agent 调用不注入主 Agent 记忆，避免污染独立上下文
        if not body.is_sub_agent:
            messages = await self._context.inject_memory(
                messages, body.agent_id, resolved_provider, llm_adapter=adapter,
                domain=conv_domain, scene=conv_scene, user_key=conv_user_key,
            )

        if body.file_content:
            supports_vision = adapter.get_provider(resolved_provider).supports_multimodal(resolved_model)
            messages = self._context.inject_file_content(
                messages, body.file_content, body.file_type or "text",
                supports_vision=supports_vision, file_name=body.file_name,
            )

        if body.search_results:
            wrapped = wrap_untrusted_content(body.search_results, source="search")
            for i in range(len(messages) - 1, -1, -1):
                if messages[i]["role"] == "user":
                    messages[i]["content"] += f"\n\n[搜索结果]\n{wrapped}"
                    break

        ctx_mgr = get_context_manager(resolved_provider, resolved_model)
        process_result = await ctx_mgr.process(messages)
        messages = process_result["messages"]

        if body.stream:
            logger.info("[ChatService] POST /chat/completions - Starting stream response")
            return sse_response(
                self.stream_chat(
                    messages, body, resolved_provider, resolved_model,
                    agent_id=body.agent_id,
                    domain=conv_domain, scene=conv_scene, user_key=conv_user_key,
                ),
            )

        gen_state: dict = {"content": "", "reasoning": "", "aborted": False, "started": True}
        await self.non_stream_generate(
            gen_state, messages,
            resolved_provider, resolved_model,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
            top_p=body.top_p,
        )

        if gen_state["aborted"]:
            return {
                "aborted": True,
                "content": gen_state["content"],
                "model": resolved_model,
                "provider": resolved_provider,
            }

        result_content = gen_state["content"] or ""

        # 命令安全守卫：扫描 LLM 输出中的不安全命令并标注
        from app.security.command_guard import scan_and_annotate
        result_content = scan_and_annotate(result_content)

        # 非流式 /chat/completions 写入记忆（子 Agent 调用跳过，避免污染主 Agent 记忆）
        if not body.is_sub_agent:
            try:
                user_msgs = [m for m in messages if m.get("role") == "user"]
                if user_msgs:
                    thread_id = body.conversation_id or f"completions-{uuid.uuid4().hex[:8]}"
                    await self._context.schedule_memory_update(
                        messages, thread_id, body.agent_id,
                        llm_adapter=adapter,
                        domain=conv_domain, scene=conv_scene, user_key=conv_user_key,
                    )
            except Exception as mem_err:
                logger.warning(f"[ChatService] /chat/completions memory update failed: {mem_err}")

        elapsed = time.time() - start_time
        logger.success(
            f"[ChatService] POST /chat/completions - "
            f"Success: elapsed={elapsed:.2f}s, response_len={len(result_content)}"
        )
        return {
            "aborted": False,
            "content": result_content,
            "model": resolved_model,
            "provider": resolved_provider,
        }

    async def process_conversation_turn(
        self,
        conv_id: str,
        request,
        adapter,
        conversation_store,
        *,
        regenerate: bool = False,
    ):
        """对话内发送消息 / 重新生成的统一业务主流程。

        收敛原 add_message / regenerate_message 两条路由：
        - regenerate=True：先弹掉末尾 assistant 消息再重新生成（差异分支）
        - regenerate=False：落库新用户消息后生成
        stream=True 时返回 SSE StreamingResponse（记忆更新+蒸馏由
        stream_response 的 finally 统一执行，单触发）；
        非流式返回 dict {"content", "model", "provider"}。
        """
        start_time = time.time()
        conv = await require_store(conversation_store, conv_id, "Conversation")

        if regenerate:
            # 重新生成：先弹掉末尾的 assistant 消息
            while conv["messages"] and conv["messages"][-1].get("role") == "assistant":
                conv["messages"].pop()
            await self.persist_conv(conv_id, conv)
        else:
            last_user_content = ""
            for m in reversed(request.messages):
                if m.role == "user":
                    last_user_content = m.content
                    break
            prev_len = len(conv["messages"])
            self.save_user_message(
                conv, last_user_content, request.file_content, request.file_name, request.file_type,
            )
            if len(conv["messages"]) > prev_len:
                # 热路径：仅追加最后一条消息（O(1) INSERT + 增量 search_text）
                if not await conversation_store.append_message_async(conv_id, conv["messages"][-1]):
                    await self.persist_conv(conv_id, conv)
            else:
                # 合并进最后一条 user 消息（如补充文件内容）→ 按 id 更新，失败回退全量
                last = conv["messages"][-1]
                mid = str(last.get("id", "") or "")
                if not mid or not await conversation_store.update_message_async(conv_id, mid, last):
                    await self.persist_conv(conv_id, conv)

        # ── 模型解析（2026-08 全局模型统一）──
        # 专业模式（standard）路由到推理模型（设置→模型设置→推理模型）；
        # 推理模型不可用时退化为主模型，并通过 notice 通知前端（右上角 toast）。
        # 其余情况使用主模型解析链：请求级显式指定 → 对话级快照 → 全局默认。
        chat_mode_for_route = (
            conv.get("chat_mode") or getattr(request, "chat_mode", None) or "normal"
        )
        model_notice = ""
        reasoner_cfg = (
            adapter.get_reasoner_provider()
            if chat_mode_for_route == "standard"
            else None
        )
        if reasoner_cfg:
            r_provider, r_model, r_temp, r_maxtok, _r_effort = reasoner_cfg
            try:
                r_provider_inst = adapter.get_provider(r_provider)
                resolved_provider = r_provider
                resolved_model = r_model or r_provider_inst.default_model
                # 推理模型自有的生成参数优先（未配置则沿用请求/全局默认）
                if r_temp is not None:
                    request.temperature = r_temp
                if r_maxtok is not None:
                    request.max_tokens = r_maxtok
            except Exception as e:
                logger.warning(
                    f"[ChatService] Reasoner provider '{r_provider}' unavailable, "
                    f"falling back to main model: {e}"
                )
                model_notice = "推理模型不可用，已退化为主模型"
                reasoner_cfg = None

        if not reasoner_cfg:
            resolved_provider = (
                request.provider or conv.get("provider") or adapter.default_provider
            )
            resolved_model = (
                request.model or conv.get("model")
                or adapter.get_provider(resolved_provider).default_model
            )

        user_query = self._context.get_user_query(conv["messages"])
        system_prompt = self._context.build_system_prompt(conv.get("agent_id"), user_context=user_query)
        all_messages: list[dict] = [{"role": "system", "content": system_prompt}]

        # 用户显式选择的技能注入（无条件注入完整 body，优先于关键词自动匹配）
        selected_block = self._context.build_user_selected_skills_prompt(request.skill_ids or [])
        if selected_block:
            if all_messages and all_messages[0]["role"] == "system":
                all_messages.insert(1, {"role": "system", "content": selected_block})
            else:
                all_messages.insert(0, {"role": "system", "content": selected_block})

        supports_vision = adapter.get_provider(resolved_provider).supports_multimodal(resolved_model)

        for m in conv["messages"]:
            content = m["content"]
            if m.get("role") == "user" and m.get("file_content"):
                content = self._context.build_content_with_file(
                    content, m["file_content"], m.get("file_type", "text"),
                    supports_vision=supports_vision, file_name=m.get("file_name"),
                )
            all_messages.append({"role": m["role"], "content": content})

        all_messages = self._context.inject_timestamp_prompt(all_messages)
        # 始终以对话存储的 agent_id 为准，确保记忆读写一致
        agent_id = await self.resolve_agent_id(conv, request.agent_id)
        # 对话域字段（B6）：驱动 DomainPolicy 记忆读/写与轨道选择
        conv_domain = conv.get("domain") or ""
        conv_scene = conv.get("scene") or ""
        conv_user_key = conv.get("user_key") or ""
        all_messages = await self._context.inject_memory(
            all_messages, agent_id, resolved_provider, conv_id,
            llm_adapter=adapter,
            domain=conv_domain, scene=conv_scene, user_key=conv_user_key,
        )

        # 仅"发送新消息"路径拼接搜索结果（regenerate 请求体不携带 search_results）
        if not regenerate and request.search_results:
            wrapped = wrap_untrusted_content(request.search_results, source="search")
            for i in range(len(all_messages) - 1, -1, -1):
                if all_messages[i]["role"] == "user":
                    all_messages[i]["content"] += f"\n\n[搜索结果]\n{wrapped}"
                    break

        ctx_mgr = get_context_manager(resolved_provider, resolved_model)
        process_result = await ctx_mgr.process(all_messages)
        all_messages = process_result["messages"]

        gen_state: dict = {
            "content": "",
            "reasoning": "",
            "aborted": False,
            "started": True,
            "model": resolved_model,
            "provider": resolved_provider,
            "notice": model_notice,
        }

        if request.stream:
            # 流式路径：记忆更新 + 蒸馏由 stream_response 的 finally 统一执行（单触发）
            return await self.stream_response(
                conv_id, conv, request, all_messages,
                resolved_provider, resolved_model,
                agent_id, gen_state, start_time,
                versions=request.versions,
                notice=model_notice,
            )

        await self.non_stream_generate(
            gen_state, all_messages,
            resolved_provider, resolved_model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            top_p=request.top_p,
        )

        persist_state = dict(gen_state)
        if persist_state["aborted"] and persist_state["content"].startswith("[Error]"):
            persist_state["content"] = ""

        prev_len = len(conv["messages"])
        self.save_assistant_message(conv, persist_state, versions=request.versions)
        if len(conv["messages"]) > prev_len:
            # 热路径：增量追加 assistant 消息 + 同步元数据（标题可能被自动更新）
            if not await conversation_store.append_message_async(conv_id, conv["messages"][-1]):
                await self.persist_conv(conv_id, conv)
            await conversation_store.update_meta_async(
                conv_id, {"title": conv.get("title", "New Conversation")}
            )
        else:
            await self.persist_conv(conv_id, conv)

        # 非流式路径单触发：记忆更新 + 增量蒸馏（DomainPolicy 门控，B6/B7）
        # （schedule_memory_update 内部已吞掉全部异常，try/except 仅作防御）
        try:
            await self._context.schedule_memory_update(
                [dict(m) for m in conv["messages"]], conv_id, agent_id,
                llm_adapter=adapter,
                domain=conv_domain, scene=conv_scene, user_key=conv_user_key,
            )
        except Exception as mem_err:
            logger.warning(f"[ChatService] Memory update failed: conv={conv_id}, error={mem_err}")

        try:
            await distillation_service.maybe_distill(
                agent_id, conv_id, conv["messages"], adapter,
                domain=conv_domain, user_key=conv_user_key,
            )
        except Exception as distill_err:
            logger.warning(f"[ChatService] Distillation failed: conv={conv_id}, error={distill_err}")

        elapsed = time.time() - start_time
        logger.success(
            f"[ChatService] Turn done: conv={conv_id}, regenerate={regenerate}, "
            f"elapsed={elapsed:.2f}s, len={len(gen_state['content'])}, aborted={gen_state['aborted']}"
        )

        return {
            "content": gen_state["content"],
            "model": resolved_model,
            "provider": resolved_provider,
            "notice": model_notice or None,
        }

    async def compress_conversation(self, conv_id: str, conv: dict, adapter) -> dict:
        """手动压缩对话上下文，返回 {"tokens_before", "tokens_after"}。"""
        agent_id = await self.resolve_agent_id(conv)
        resolved_provider = conv.get("provider") or adapter.default_provider
        resolved_model = conv.get("model") or adapter.get_provider(resolved_provider).default_model

        # 构建完整消息列表
        user_query = self._context.get_user_query(conv.get("messages", []))
        system_prompt = self._context.build_system_prompt(agent_id, user_context=user_query)
        all_messages: list[dict] = [{"role": "system", "content": system_prompt}]
        for m in conv["messages"]:
            all_messages.append({"role": m["role"], "content": m["content"]})

        ctx_mgr = get_context_manager(resolved_provider, resolved_model)

        # 计算压缩前 token 数
        tokens_before = ctx_mgr.token_counter.count_tokens(all_messages)

        # 强制压缩：通过 force_compression 参数触发，避免修改共享的 compressor.compression_threshold
        # （共享对象在并发请求中会被复用，直接修改 threshold 会导致其他请求的阈值判断失效）
        process_result = await ctx_mgr.process(all_messages, chat_mode="compress", force_compression=True)
        compressed_messages = process_result["messages"]

        tokens_after = ctx_mgr.token_counter.count_tokens(compressed_messages)

        # 回写 conversation（去除 system 消息后存储），将摘要消息写回
        conv["messages"] = [m for m in compressed_messages if m.get("role") != "system"]
        await self.persist_conv(conv_id, conv)

        return {"tokens_before": tokens_before, "tokens_after": tokens_after}
