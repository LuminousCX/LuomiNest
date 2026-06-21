import asyncio
import uuid
from datetime import datetime, timezone
from loguru import logger

from app.core.config import settings
from app.core.tools import tool_registry
from app.core.tools.orchestrator import tool_orchestrator
from app.runtime.provider.llm.adapter import llm_adapter
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
        chat_id = str(uuid.uuid4())
        parser = EmotionStreamParser()
        try:
            async with self._llm_semaphore:
                async for chunk in llm_adapter.chat_stream(
                    messages=messages,
                    provider_name=provider,
                    model=model,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    top_p=request.top_p,
                ):
                    content = chunk.data.get("content", "")
                    rc = chunk.data.get("reasoning", "")
                    clean_content, emotion = parser.feed(content)
                    data = ChatStreamChunk(
                        id=chat_id, content=clean_content,
                        reasoning_content=rc, model=model, provider=provider,
                        emotion=emotion,
                    )
                    yield f"data: {data.model_dump_json()}\n\n"
        except Exception as e:
            logger.error(f"[STREAM] stream_chat error: {e}", exc_info=True)
            yield (
                f"data: {ChatStreamChunk(id=chat_id, content='[Error] An internal error occurred', model=model, provider=provider).model_dump_json()}\n\n"
            )
        finally:
            done_data = ChatStreamChunk(id=chat_id, content="", model=model, provider=provider, done=True)
            yield f"data: {done_data.model_dump_json()}\n\n"

            # /chat/completions 流式模式写入记忆
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
        chat_id = str(uuid.uuid4())
        parser = EmotionStreamParser()

        # 主 Agent 工具调用：获取工具列表并检测 provider 能力
        available_tools = tool_orchestrator.get_tools_for_llm() if tool_registry.list_names() else None
        use_tools = bool(available_tools) and llm_adapter.supports_tool_calls(provider, model)
        if available_tools and not use_tools:
            logger.info(f"[STREAM] Provider {provider}/{model} 不支持工具调用，本次以纯对话模式运行")

        async def generator():
            suggested_questions: list[str] = []
            stream_usage: dict | None = None
            iteration = 0
            try:
                # 工具调用循环（最多 max_iterations 次，防止无限循环）
                while iteration <= tool_orchestrator.max_iterations:
                    collected_tool_calls: dict[int, dict] = {}
                    finish_reason: str | None = None
                    iteration_content = ""

                    async with self._llm_semaphore:
                        async for chunk in llm_adapter.chat_stream(
                            messages=all_messages,
                            tools=available_tools if use_tools else None,
                            provider_name=provider,
                            model=model,
                            temperature=request.temperature or 0.7,
                            max_tokens=request.max_tokens or 4096,
                            top_p=request.top_p or 0.9,
                        ):
                            if chunk.type == "usage":
                                stream_usage = chunk.data.get("usage")
                                continue
                            if chunk.type == "content":
                                content = chunk.data.get("content", "")
                                clean_content, emotion = parser.feed(content)
                                if clean_content:
                                    state["content"] += clean_content
                                    iteration_content += clean_content
                                yield self._sse(chat_id, clean_content, provider, model, "", emotion)
                            elif chunk.type == "reasoning":
                                rc = chunk.data.get("reasoning", "")
                                if rc:
                                    state["reasoning"] += rc
                                yield self._sse(chat_id, "", provider, model, rc)
                            elif chunk.type == "tool_call_delta":
                                idx = chunk.data.get("index", 0)
                                if idx not in collected_tool_calls:
                                    collected_tool_calls[idx] = {"id": "", "name": "", "arguments": ""}
                                if chunk.data.get("tool_call_id"):
                                    collected_tool_calls[idx]["id"] = chunk.data["tool_call_id"]
                                if chunk.data.get("function_name"):
                                    collected_tool_calls[idx]["name"] = chunk.data["function_name"]
                                if chunk.data.get("function_arguments"):
                                    collected_tool_calls[idx]["arguments"] += chunk.data["function_arguments"]
                            elif chunk.type == "finish_reason":
                                finish_reason = chunk.data.get("finish_reason")

                    # 组装本轮 tool_calls
                    tool_calls_list: list[dict] = []
                    if collected_tool_calls:
                        for idx in sorted(collected_tool_calls.keys()):
                            entry = collected_tool_calls[idx]
                            tool_calls_list.append({
                                "id": entry["id"] or f"call_{iteration}_{idx}",
                                "type": "function",
                                "function": {
                                    "name": entry["name"],
                                    "arguments": entry["arguments"],
                                },
                            })

                    # 无工具调用或未启用工具，结束循环
                    if not tool_calls_list or not use_tools:
                        break

                    # 流式通知前端：主 Agent 请求调用工具
                    yield self._sse_tool_calls(chat_id, tool_calls_list, iteration, provider, model)

                    # 把带 tool_calls 的 assistant 消息回填到上下文
                    assistant_msg = tool_orchestrator.build_assistant_message_with_tool_calls(
                        iteration_content, tool_calls_list,
                    )
                    all_messages.append(assistant_msg)

                    # 依次执行每个工具调用
                    for tc in tool_calls_list:
                        tool_name = tc["function"]["name"]
                        logger.info(
                            f"[ChatService] 主 Agent 调用工具: {tool_name} "
                            f"(conv={conv_id}, iteration={iteration})"
                        )
                        yield self._sse_tool_event(
                            chat_id, tool_name, "started", None, iteration, provider, model,
                        )

                        # 子 Agent 委派工具：流式推送子 Agent 执行事件
                        if tool_name == "delegate_to_subagent":
                            from app.core.tools.builtin.subagent_tool import (
                                set_subagent_event_callback,
                                reset_subagent_event_callback,
                            )

                            event_queue: asyncio.Queue = asyncio.Queue()

                            async def _luominest_subagent_event_cb(event: dict) -> None:
                                await event_queue.put(event)

                            cb_token = set_subagent_event_callback(_luominest_subagent_event_cb)
                            try:
                                delegate_task = asyncio.ensure_future(
                                    tool_orchestrator.execute_tool_call(tc)
                                )
                                # 并行消费事件队列，直到工具任务完成
                                while not delegate_task.done():
                                    queue_get = asyncio.ensure_future(event_queue.get())
                                    done, _pending = await asyncio.wait(
                                        [delegate_task, queue_get],
                                        return_when=asyncio.FIRST_COMPLETED,
                                    )
                                    if queue_get in done:
                                        event = queue_get.result()
                                        yield self._sse_subagent_event(
                                            chat_id, event, provider, model,
                                        )
                                    if delegate_task in done:
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
                                    yield self._sse_subagent_event(
                                        chat_id, event, provider, model,
                                    )
                                tool_msg = delegate_task.result()
                            finally:
                                reset_subagent_event_callback(cb_token)
                        elif tool_name == "create_scheduled_task":
                            # 定时任务工具：通过 task_event 通道推送创建事件
                            from app.core.tools.builtin.subagent_tool import (
                                set_subagent_event_callback,
                                reset_subagent_event_callback,
                            )

                            task_event_queue: asyncio.Queue = asyncio.Queue()

                            async def _luominest_task_event_cb(event: dict) -> None:
                                # 浏览器工具复用 subagent_event 通道，定时任务用 task_event
                                if event.get("browser_action"):
                                    await task_event_queue.put({"channel": "subagent", "data": event})
                                else:
                                    await task_event_queue.put({"channel": "task", "data": event})

                            task_cb_token = set_subagent_event_callback(_luominest_task_event_cb)
                            try:
                                sched_task = asyncio.ensure_future(
                                    tool_orchestrator.execute_tool_call(tc)
                                )
                                while not sched_task.done():
                                    queue_get = asyncio.ensure_future(task_event_queue.get())
                                    done, _pending = await asyncio.wait(
                                        [sched_task, queue_get],
                                        return_when=asyncio.FIRST_COMPLETED,
                                    )
                                    if queue_get in done:
                                        item = queue_get.result()
                                        if item["channel"] == "subagent":
                                            yield self._sse_subagent_event(
                                                chat_id, item["data"], provider, model,
                                            )
                                        else:
                                            yield self._sse_task_event(
                                                chat_id, item["data"], provider, model,
                                            )
                                    if sched_task in done:
                                        if not queue_get.done():
                                            queue_get.cancel()
                                            try:
                                                await queue_get
                                            except asyncio.CancelledError:
                                                pass
                                        break
                                while not task_event_queue.empty():
                                    item = task_event_queue.get_nowait()
                                    if item["channel"] == "subagent":
                                        yield self._sse_subagent_event(
                                            chat_id, item["data"], provider, model,
                                        )
                                    else:
                                        yield self._sse_task_event(
                                            chat_id, item["data"], provider, model,
                                        )
                                tool_msg = sched_task.result()
                            finally:
                                reset_subagent_event_callback(task_cb_token)
                        else:
                            tool_msg = await tool_orchestrator.execute_tool_call(tc)

                        logger.info(
                            f"[ChatService] 工具 {tool_name} 执行完成 "
                            f"(conv={conv_id}, iteration={iteration})"
                        )
                        yield self._sse_tool_event(
                            chat_id, tool_name, "completed",
                            tool_msg.get("content", ""), iteration, provider, model,
                        )
                        all_messages.append(tool_msg)

                    iteration += 1
                    # 继续下一轮 LLM 调用，让模型基于工具结果继续生成

            except Exception as e:
                state["aborted"] = True
                logger.error(f"[STREAM] Aborted: conv={conv_id}, error={e}", exc_info=True)
                yield self._sse(chat_id, "[Error] An internal error occurred", provider, model)

            finally:
                try:
                    if stream_usage:
                        try:
                            usage_tracker.record_usage(
                                provider=provider, model=model,
                                usage=stream_usage, agent_id=agent_id, conv_id=conv_id,
                                is_stream=True,
                            )
                        except Exception as ut_err:
                            logger.warning(f"[STREAM] Usage tracking failed: {ut_err}")
                    else:
                        try:
                            usage_tracker.record_usage(
                                provider=provider, model=model,
                                agent_id=agent_id, conv_id=conv_id, is_stream=True,
                            )
                        except Exception as ut_err:
                            logger.warning(f"[STREAM] Usage tracking failed: {ut_err}")
                except Exception as finalize_err:
                    logger.warning(f"[STREAM] Finalization pre-persist block failed: {finalize_err}")
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

                try:
                    yield self._sse_done(chat_id, provider, model, suggested_questions or None)
                except Exception as done_err:
                    logger.debug(f"[STREAM] Done event send failed (client may have disconnected): {done_err}")

                try:
                    await self._context.schedule_memory_update(
                        [dict(m) for m in conv["messages"]], conv_id, agent_id,
                        llm_adapter=llm_adapter,
                    )
                except Exception as schedule_err:
                    logger.warning(f"[STREAM] Memory update scheduling failed: {schedule_err}")

                try:
                    await distillation_service.maybe_distill(agent_id, conv_id, conv["messages"], llm_adapter)
                except Exception as distill_err:
                    logger.warning(f"[STREAM] Distillation failed: {distill_err}")

        return StreamingResponse(
            generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
        )

    @staticmethod
    def _sse(
        cid: str,
        content: str,
        provider: str,
        model: str,
        reasoning: str = "",
        emotion: str | None = None,
    ) -> str:
        # 兜底过滤：确保任何 <exp:...> 标签变体都不会泄漏到前端
        if content:
            content = strip_emotion_tags(content)
        return (
            f"data: {ChatStreamChunk(id=cid, content=content, reasoning_content=reasoning, model=model, provider=provider, emotion=emotion).model_dump_json()}\n\n"
        )

    @staticmethod
    def _sse_tool_calls(
        cid: str,
        tool_calls: list[dict],
        iteration: int,
        provider: str,
        model: str,
    ) -> str:
        return (
            f"data: {ChatStreamChunk(id=cid, model=model, provider=provider, tool_calls=tool_calls, iteration=iteration).model_dump_json()}\n\n"
        )

    @staticmethod
    def _sse_tool_event(
        cid: str,
        tool_name: str,
        status: str,
        output: str | None,
        iteration: int,
        provider: str,
        model: str,
    ) -> str:
        tool_event = {"tool_name": tool_name, "status": status, "output": output}
        return (
            f"data: {ChatStreamChunk(id=cid, model=model, provider=provider, tool_event=tool_event, iteration=iteration).model_dump_json()}\n\n"
        )

    @staticmethod
    def _sse_subagent_event(
        cid: str,
        event: dict,
        provider: str,
        model: str,
    ) -> str:
        """推送子 Agent 执行事件到 SSE 流

        事件结构：
        - subagent_id: 子 Agent 唯一 ID
        - status: started / running / completed / failed
        - task: 任务描述
        - depth: 委派深度
        - iteration: 当前迭代轮次
        - tool_name / tool_args / tool_output: 工具调用信息（可选）
        - progress: 进度文本（可选）
        - result: 最终结果（completed 时）
        - error: 错误信息（failed 时）
        """
        return (
            f"data: {ChatStreamChunk(id=cid, model=model, provider=provider, subagent_event=event).model_dump_json()}\n\n"
        )

    @staticmethod
    def _sse_task_event(
        cid: str,
        event: dict,
        provider: str,
        model: str,
    ) -> str:
        """推送定时任务事件到 SSE 流"""
        return (
            f"data: {ChatStreamChunk(id=cid, model=model, provider=provider, task_event=event).model_dump_json()}\n\n"
        )

    @staticmethod
    def _sse_done(
        cid: str,
        provider: str,
        model: str,
        suggested_questions: list[str] | None = None,
    ) -> str:
        return (
            f"data: {ChatStreamChunk(id=cid, content='', model=model, provider=provider, done=True, suggested_questions=suggested_questions).model_dump_json()}\n\n"
        )
