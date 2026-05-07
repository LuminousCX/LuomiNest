import copy
import uuid
import time
import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from loguru import logger

from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ChatStreamChunk,
    ConversationCreate,
    ConversationResponse,
    ConversationListResponse,
)
from app.runtime.provider.llm.adapter import llm_adapter
from app.infrastructure.database.json_store import conversations_store, agents_store
from app.core.config import settings
from app.utils.intent_gateway import classify_request, RequestType
from app.utils.tool_lazy_loader import get_matched_tools
from app.utils.tool_result_processor import process_tool_result
from app.utils.local_handler import handle_local_tool_request

router = APIRouter(prefix="/chat", tags=["chat"])

_memory_locks: dict[str | None, asyncio.Lock] = {}


def _get_memory_lock(agent_id: str | None) -> asyncio.Lock:
    if agent_id not in _memory_locks:
        _memory_locks[agent_id] = asyncio.Lock()
    return _memory_locks[agent_id]


def _get_user_query(messages: list[dict]) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                return content[:200]
    return ""


def _resolve_tools(user_message: str, request_type: RequestType) -> list[dict] | None:
    """按需解析工具定义 —— 仅 TOOL_CALL 类型才注入匹配场景的工具

    GENERAL_CHAT 和 LOCAL_TOOL 请求绝不注入任何工具，从根源杜绝工具乱触发。

    异常安全：
        懒加载异常时返回空列表 []（不注入任何工具），避免全量注入导致工具乱触发。
        GENERAL_CHAT 和 LOCAL_TOOL 请求始终返回 None。

    参数:
        user_message: 用户原始消息文本
        request_type: classify_request 返回的请求类型

    返回:
        - TOOL_CALL 且命中场景：OpenAI Function Calling 格式工具列表
        - TOOL_CALL 但无匹配场景：空列表 []（等效不注入工具）
        - 其他类型：None（不注入工具）
        - 异常：空列表 []（安全降级，不注入工具）
    """
    if request_type != RequestType.TOOL_CALL:
        return None

    try:
        tools = get_matched_tools(user_message)
        return tools if tools else []
    except Exception as e:
        logger.warning(f"[Chat] 工具懒加载异常，降级返回空列表（不注入工具）: {e}")
        return []


async def _execute_tool_call_loop(
    messages: list[dict],
    tools: list[dict],
    provider_name: str,
    model: str,
    temperature: float | None = None,
    max_tokens: int | None = None,
    top_p: float | None = None,
    max_iterations: int = 3,
) -> str:
    """工具调用循环 —— 处理 LLM 工具调用请求，执行工具并回传精简结果

    完整流程（支持多轮工具调用）：
      第一轮：发送 messages + tools → LLM 决定是否需要工具
        ├─ 无 tool_calls → 直接返回文本内容
        └─ 有 tool_calls → 遍历每个 tool_call:
              1. SkillExecutor.execute(tool_name, args) → 原始结果
              2. process_tool_result(tool_name, 原始结果) → 精简结果
              3. 追加 tool result message
            → 回到循环起点，下一轮 LLM 看到工具结果后生成最终回复

    安全机制：
      - max_iterations 限制最大轮次，防止死循环
      - 任何环节异常均不中断对话，返回友好提示
      - 工具执行失败时仍传递错误信息给 LLM，让其自行处理

    参数:
        messages: 对话消息列表（会被浅拷贝，不会修改原始列表）
        tools: 工具定义列表
        provider_name: LLM provider 名称
        model: 模型名称
        temperature: 温度参数
        max_tokens: 最大 token 数
        top_p: top_p 参数
        max_iterations: 最大迭代次数，默认 3

    返回:
        最终回复文本字符串
    """
    import json as _json

    current_messages = [dict(m) for m in messages]

    for iteration in range(max_iterations):
        # 调用 LLM：第一轮传工具定义让 LLM 选择，后续轮次不传（避免重复调用）
        response = await llm_adapter.chat(
            messages=current_messages,
            tools=tools if iteration == 0 else None,
            provider_name=provider_name,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            return_raw=True,
        )

        # 判断响应的类型：可能是 dict（raw 模式）或 str（降级）
        if isinstance(response, str):
            # 降级场景：LLM 直接返回了文本
            return response

        tool_calls = response.get("tool_calls", []) if isinstance(response, dict) else []

        # 无工具调用 → 这是最终文本回复
        if not tool_calls:
            content = response.get("content", "") if isinstance(response, dict) else ""
            return content or "抱歉，我暂时无法处理这个请求。"

        logger.info(
            f"[Chat] 工具调用循环 第{iteration + 1}轮: "
            f"检测到 {len(tool_calls)} 个工具调用 → "
            f"{[tc.get('function', {}).get('name', '?') for tc in tool_calls]}"
        )

        # 追加 assistant 消息（含 tool_calls）
        assistant_msg: dict = {
            "role": "assistant",
            "content": response.get("content") or None,
        }
        # 保留完整的 tool_calls 结构
        assistant_msg["tool_calls"] = tool_calls
        current_messages.append(assistant_msg)

        # 执行每个工具调用
        from app.runtime.plugin.skill.executor import SkillExecutor
        executor = SkillExecutor()

        for tool_call in tool_calls:
            fn = tool_call.get("function", {})
            tool_name = fn.get("name", "")
            arguments_str = fn.get("arguments", "{}")

            # 解析参数
            try:
                arguments = _json.loads(arguments_str) if isinstance(arguments_str, str) else arguments_str
            except (_json.JSONDecodeError, TypeError):
                arguments = {}

            tool_call_id = tool_call.get("id", f"call_{iteration}_{tool_name}")

            try:
                # 步骤1：执行工具获取原始结果
                raw_result = await executor.execute(tool_name, arguments, agent_id=None)
                # 步骤2：结果处理器过滤聚合精简
                processed_result = process_tool_result(tool_name, raw_result)
                logger.info(
                    f"[Chat] 工具 {tool_name} 执行完成: "
                    f"原始 {len(raw_result)} 字符 → 精简 {len(processed_result)} 字符"
                )
            except Exception as e:
                logger.warning(f"[Chat] 工具 {tool_name} 执行异常: {e}")
                processed_result = f"工具执行出错: {e}"

            # 追加 tool result 消息
            current_messages.append({
                "role": "tool",
                "tool_call_id": tool_call_id,
                "name": tool_name,
                "content": processed_result,
            })

    # 超过最大迭代次数
    logger.warning(f"[Chat] 工具调用循环达到最大迭代次数 {max_iterations}，强制终止")
    return "抱歉，处理您的请求需要多次工具调用，请尝试简化问题后再问我。"



async def _inject_memory(messages: list[dict], agent_id: str | None = None, provider_name: str | None = None) -> list[dict]:
    try:
        from app.engines.memory.core import MemoryInjector, get_memory_storage
        storage = get_memory_storage()
        lock = _get_memory_lock(agent_id)
        async with lock:
            memory_data = await asyncio.to_thread(storage.load, agent_id)

        if not memory_data.facts and not memory_data.working_memory.core_goal and not memory_data.episodic_events:
            has_profile = bool(
                memory_data.profile.name or memory_data.profile.nickname
                or memory_data.profile.occupation or memory_data.profile.location
            )
            if not has_profile:
                return messages

        user_query = _get_user_query(messages)
        injector = MemoryInjector()

        try:
            if provider_name:
                provider = llm_adapter.get_provider(provider_name)
                context_window = getattr(provider, 'context_window', None) or 128000
                existing_tokens = sum(len(m.get("content", "")) for m in messages) // 3
                injector.set_token_budget(context_window, existing_tokens)
        except Exception:
            pass

        return injector.inject_memory_to_messages(messages, memory_data, user_query)
    except Exception as e:
        logger.warning(f"[Memory] Injection skipped: {e}")
        return messages


def _schedule_memory_update(
    messages: list[dict],
    conv_id: str,
    agent_id: str | None = None,
    provider_name: str | None = None,
):
    try:
        from app.engines.memory.core import MemoryUpdater, get_memory_storage
        storage = get_memory_storage()
        updater = MemoryUpdater(storage, provider_name=provider_name)
        messages_snapshot = copy.deepcopy(messages)

        async def _do_update():
            try:
                lock = _get_memory_lock(agent_id)
                async with lock:
                    await updater.update_from_conversation(messages_snapshot, conv_id, agent_id)
            except Exception as e:
                logger.warning(f"[Memory] Async update failed: {e}")

        asyncio.create_task(_do_update())
    except Exception as e:
        logger.warning(f"[Memory] Update scheduling skipped: {e}")


@router.post("/completions")
async def chat_completions(request: ChatRequest):
    start_time = time.time()
    resolved_provider = request.provider or llm_adapter.default_provider
    resolved_model = request.model or llm_adapter.get_provider(resolved_provider).default_model
    logger.info(f"[API] POST /chat/completions - provider={resolved_provider}, model={resolved_model}, stream={request.stream}")

    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    messages = await _inject_memory(messages, request.agent_id, resolved_provider)

    # 意图分类 + 按需工具加载（仅 TOOL_CALL 类型注入匹配场景的工具）
    user_query = _get_user_query(messages)
    request_type = classify_request(user_query)
    tools = _resolve_tools(user_query, request_type)
    tools_count = len(tools) if tools else 0
    logger.info(f"[API] 意图分类: type={request_type.value}, tools_injected={tools_count}")

    # LOCAL_TOOL：本地工具直接处理，不走 LLM
    if request_type == RequestType.LOCAL_TOOL:
        result = await handle_local_tool_request(user_query)
        if result is None:
            result = await llm_adapter.chat(
                messages=messages,
                provider_name=resolved_provider,
                model=resolved_model,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                top_p=request.top_p,
            )
        elapsed = time.time() - start_time
        logger.success(f"[API] POST /chat/completions [LOCAL_TOOL] - Success: elapsed={elapsed:.2f}s")

        # 流式请求：包装为 SSE 响应（前端始终用 stream=true）
        if request.stream:
            chat_id = str(uuid.uuid4())
            data = ChatStreamChunk(id=chat_id, content=result, model=resolved_model, provider=resolved_provider)
            done_data = ChatStreamChunk(id=chat_id, content="", model=resolved_model, provider=resolved_provider, done=True)

            async def _local_tool_stream():
                yield f"data: {data.model_dump_json()}\n\n"
                yield f"data: {done_data.model_dump_json()}\n\n"

            return StreamingResponse(_local_tool_stream(), media_type="text/event-stream")

        return ChatResponse(
            id=str(uuid.uuid4()),
            content=result,
            model=resolved_model,
            provider=resolved_provider,
        )

    # TOOL_CALL 天气：本地工具直接处理
    if request_type == RequestType.TOOL_CALL:
        result = await handle_local_tool_request(user_query)
        if result is not None:
            elapsed = time.time() - start_time
            logger.success(f"[API] POST /chat/completions [WEATHER local] - Success: elapsed={elapsed:.2f}s")

            if request.stream:
                chat_id = str(uuid.uuid4())
                data = ChatStreamChunk(id=chat_id, content=result, model=resolved_model, provider=resolved_provider)
                done_data = ChatStreamChunk(id=chat_id, content="", model=resolved_model, provider=resolved_provider, done=True)

                async def _weather_local_stream():
                    yield f"data: {data.model_dump_json()}\n\n"
                    yield f"data: {done_data.model_dump_json()}\n\n"

                return StreamingResponse(_weather_local_stream(), media_type="text/event-stream")

            return ChatResponse(
                id=str(uuid.uuid4()),
                content=result,
                model=resolved_model,
                provider=resolved_provider,
            )

    if request.stream:
        logger.info(f"[API] POST /chat/completions - Starting stream response")
        return StreamingResponse(
            _stream_chat(messages, request, resolved_provider, resolved_model, tools),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    try:
        # TOOL_CALL → 工具调用循环 | GENERAL_CHAT → LLM（LOCAL_TOOL 已在上面处理）
        if tools:
            result = await _execute_tool_call_loop(
                messages=messages,
                tools=tools,
                provider_name=resolved_provider,
                model=resolved_model,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                top_p=request.top_p,
            )
        else:
            result = await llm_adapter.chat(
                messages=messages,
                provider_name=resolved_provider,
                model=resolved_model,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                top_p=request.top_p,
            )

        elapsed = time.time() - start_time
        logger.success(f"[API] POST /chat/completions - Success: elapsed={elapsed:.2f}s, response_len={len(result)}")
        return ChatResponse(
            id=str(uuid.uuid4()),
            content=result,
            model=resolved_model,
            provider=resolved_provider,
        )
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[API] POST /chat/completions - Failed: elapsed={elapsed:.2f}s, error={e}")
        raise


async def _stream_chat(messages: list[dict], request: ChatRequest, provider: str, model: str, tools: list[dict] | None = None):
    # 当有工具定义时，先用工具调用循环处理（非流式），再将最终回复以流式输出
    if tools:
        final_reply = await _execute_tool_call_loop(
            messages=messages,
            tools=tools,
            provider_name=provider,
            model=model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            top_p=request.top_p,
        )
        chat_id = str(uuid.uuid4())
        data = ChatStreamChunk(id=chat_id, content=final_reply, model=model, provider=provider)
        yield f"data: {data.model_dump_json()}\n\n"
        done_data = ChatStreamChunk(id=chat_id, content="", model=model, provider=provider, done=True)
        yield f"data: {done_data.model_dump_json()}\n\n"
        return

    start_time = time.time()
    chat_id = str(uuid.uuid4())
    chunk_count = 0

    logger.info(f"[STREAM] Starting stream: chat_id={chat_id}, provider={provider}, model={model}")

    try:
        async for chunk in llm_adapter.chat_stream(
            messages=messages,
            tools=tools,
            provider_name=provider,
            model=model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            top_p=request.top_p,
        ):
            chunk_count += 1
            data = ChatStreamChunk(
                id=chat_id,
                content=chunk,
                model=model,
                provider=provider,
            )
            yield f"data: {data.model_dump_json()}\n\n"

        done_data = ChatStreamChunk(
            id=chat_id,
            content="",
            model=model,
            provider=provider,
            done=True,
        )
        yield f"data: {done_data.model_dump_json()}\n\n"

        elapsed = time.time() - start_time
        logger.success(f"[STREAM] Stream completed: chat_id={chat_id}, chunks={chunk_count}, elapsed={elapsed:.2f}s")
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[STREAM] Stream failed: chat_id={chat_id}, elapsed={elapsed:.2f}s, error={e}")
        error_data = ChatStreamChunk(
            id=chat_id,
            content=f"[Error] {str(e)}",
            model=model,
            provider=provider,
            done=True,
        )
        yield f"data: {error_data.model_dump_json()}\n\n"


@router.get("/conversations", response_model=list[ConversationListResponse])
async def list_conversations(agent_id: str | None = None):
    logger.info(f"[API] GET /chat/conversations - Listing conversations, agent_id={agent_id}")
    result = []
    for conv_id, conv in conversations_store.items():
        if agent_id and conv.get("agent_id") != agent_id:
            continue
        messages = conv.get("messages", [])
        last_msg = messages[-1]["content"][:50] if messages else None
        result.append(ConversationListResponse(
            id=conv_id,
            title=conv.get("title", "New Conversation"),
            agent_id=conv.get("agent_id"),
            model=conv.get("model"),
            provider=conv.get("provider"),
            last_message=last_msg,
            created_at=conv.get("created_at", ""),
            updated_at=conv.get("updated_at", ""),
        ))
    result.sort(key=lambda x: x.updated_at, reverse=True)
    logger.success(f"[API] GET /chat/conversations - Success: returned {len(result)} conversations")
    return result


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(request: ConversationCreate):
    logger.info(f"[API] POST /chat/conversations - Creating conversation: title={request.title}, agent_id={request.agent_id}")
    conv_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conv = {
        "id": conv_id,
        "title": request.title or "New Conversation",
        "agent_id": request.agent_id,
        "model": request.model,
        "provider": request.provider,
        "messages": [],
        "created_at": now,
        "updated_at": now,
    }
    conversations_store.set(conv_id, conv)
    logger.success(f"[API] POST /chat/conversations - Conversation created: id={conv_id}")
    return ConversationResponse(**conv)


@router.get("/conversations/{conv_id}", response_model=ConversationResponse)
async def get_conversation(conv_id: str):
    logger.info(f"[API] GET /chat/conversations/{conv_id} - Fetching conversation")
    conv = conversations_store.get(conv_id)
    if not conv:
        logger.error(f"[API] GET /chat/conversations/{conv_id} - Conversation not found")
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Conversation {conv_id} not found")
    logger.success(f"[API] GET /chat/conversations/{conv_id} - Success: title={conv['title']}, messages={len(conv.get('messages', []))}")
    return ConversationResponse(**conv)


@router.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: str):
    logger.info(f"[API] DELETE /chat/conversations/{conv_id} - Deleting conversation")
    conv = conversations_store.get(conv_id)
    if conv:
        conv_title = conv.get("title", "unknown")
        conversations_store.delete(conv_id)
        logger.success(f"[API] DELETE /chat/conversations/{conv_id} - Conversation deleted: title={conv_title}")
    else:
        logger.warning(f"[API] DELETE /chat/conversations/{conv_id} - Conversation not found")
    return {"error": None, "data": {"deleted": True}}


@router.post("/conversations/{conv_id}/messages")
async def add_message(conv_id: str, request: ChatRequest):
    start_time = time.time()
    logger.info(f"[API] POST /chat/conversations/{conv_id}/messages - Adding message")
    conv = conversations_store.get(conv_id)
    if not conv:
        logger.error(f"[API] POST /chat/conversations/{conv_id}/messages - Conversation not found")
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Conversation {conv_id} not found")

    last_user_msg = None
    for m in reversed(request.messages):
        if m.role == "user":
            last_user_msg = m
            break

    if last_user_msg:
        msg_entry = {"role": "user", "content": last_user_msg.content}
        if not conv["messages"] or conv["messages"][-1] != msg_entry:
            conv["messages"].append(msg_entry)
            logger.debug(f"[API] POST /chat/conversations/{conv_id}/messages - Added user message")

    conv["updated_at"] = datetime.now(timezone.utc).isoformat()

    resolved_provider = request.provider or conv.get("provider") or llm_adapter.default_provider
    resolved_model = request.model or conv.get("model") or llm_adapter.get_provider(resolved_provider).default_model

    all_messages = []
    for m in conv["messages"]:
        all_messages.append({"role": m["role"], "content": m["content"]})

    agent_id = request.agent_id or conv.get("agent_id")
    all_messages = await _inject_memory(all_messages, agent_id, resolved_provider)

    # 意图分类 + 按需工具加载（仅 TOOL_CALL 类型注入匹配场景的工具）
    user_query = _get_user_query(all_messages)
    request_type = classify_request(user_query)
    tools = _resolve_tools(user_query, request_type)
    tools_count = len(tools) if tools else 0
    logger.info(f"[API] 意图分类: type={request_type.value}, tools_injected={tools_count}")

    # LOCAL_TOOL：本地工具直接处理，不走 LLM
    if request_type == RequestType.LOCAL_TOOL:
        result = await handle_local_tool_request(user_query)
        if result is None:
            # 本地工具无法处理时降级走 LLM
            result = await llm_adapter.chat(
                messages=all_messages,
                provider_name=resolved_provider,
                model=resolved_model,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                top_p=request.top_p,
            )
        assistant_msg = {"role": "assistant", "content": result}
        if result and (not conv["messages"] or conv["messages"][-1] != assistant_msg):
            conv["messages"].append(assistant_msg)
            conv["updated_at"] = datetime.now(timezone.utc).isoformat()
            conversations_store.set(conv_id, conv)
        _schedule_memory_update(conv["messages"], conv_id, agent_id, provider_name=resolved_provider)

        # 流式请求：将本地结果包装为 SSE 流式响应（前端始终用 stream=true）
        if request.stream:
            chat_id = str(uuid.uuid4())
            data = ChatStreamChunk(id=chat_id, content=result, model=resolved_model, provider=resolved_provider)
            done_data = ChatStreamChunk(id=chat_id, content="", model=resolved_model, provider=resolved_provider, done=True)

            async def _local_tool_stream():
                yield f"data: {data.model_dump_json()}\n\n"
                yield f"data: {done_data.model_dump_json()}\n\n"

            logger.info(f"[API] POST /chat/conversations/{conv_id}/messages [LOCAL_TOOL stream] - Success")
            return StreamingResponse(_local_tool_stream(), media_type="text/event-stream")

        logger.info(f"[API] POST /chat/conversations/{conv_id}/messages [LOCAL_TOOL] - Success")
        return ChatResponse(
            id=str(uuid.uuid4()),
            content=result,
            model=resolved_model,
            provider=resolved_provider,
        )

    # TOOL_CALL 天气：优先尝试本地天气工具处理，无城市名时走工具调用循环
    if request_type == RequestType.TOOL_CALL:
        local_result = await handle_local_tool_request(user_query)
        if local_result is not None:
            assistant_msg = {"role": "assistant", "content": local_result}
            if local_result and (not conv["messages"] or conv["messages"][-1] != assistant_msg):
                conv["messages"].append(assistant_msg)
                conv["updated_at"] = datetime.now(timezone.utc).isoformat()
                conversations_store.set(conv_id, conv)
            _schedule_memory_update(conv["messages"], conv_id, agent_id, provider_name=resolved_provider)

            if request.stream:
                chat_id = str(uuid.uuid4())
                data = ChatStreamChunk(id=chat_id, content=local_result, model=resolved_model, provider=resolved_provider)
                done_data = ChatStreamChunk(id=chat_id, content="", model=resolved_model, provider=resolved_provider, done=True)

                async def _weather_local_stream():
                    yield f"data: {data.model_dump_json()}\n\n"
                    yield f"data: {done_data.model_dump_json()}\n\n"

                logger.info(f"[API] POST /chat/conversations/{conv_id}/messages [WEATHER local stream] - Success")
                return StreamingResponse(_weather_local_stream(), media_type="text/event-stream")

            logger.info(f"[API] POST /chat/conversations/{conv_id}/messages [WEATHER local] - Success")
            return ChatResponse(
                id=str(uuid.uuid4()),
                content=local_result,
                model=resolved_model,
                provider=resolved_provider,
            )

    if request.stream:
        logger.info(f"[API] POST /chat/conversations/{conv_id}/messages - Starting stream response")

        async def stream_with_save():
            # 当有工具定义时，先用工具调用循环处理，再将最终回复以流式输出
            if tools:
                final_reply = await _execute_tool_call_loop(
                    messages=all_messages,
                    tools=tools,
                    provider_name=resolved_provider,
                    model=resolved_model,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    top_p=request.top_p,
                )
                chat_id = str(uuid.uuid4())
                data = ChatStreamChunk(id=chat_id, content=final_reply, model=resolved_model, provider=resolved_provider)
                yield f"data: {data.model_dump_json()}\n\n"
                done_data = ChatStreamChunk(id=chat_id, content="", model=resolved_model, provider=resolved_provider, done=True)
                yield f"data: {done_data.model_dump_json()}\n\n"

                assistant_msg = {"role": "assistant", "content": final_reply}
                if not conv["messages"] or conv["messages"][-1] != assistant_msg:
                    conv["messages"].append(assistant_msg)
                    conv["updated_at"] = datetime.now(timezone.utc).isoformat()
                    conversations_store.set(conv_id, conv)

                _schedule_memory_update(
                    conv["messages"], conv_id, agent_id,
                    provider_name=resolved_provider,
                )
                return

            final_answer = ""
            chat_id = str(uuid.uuid4())
            chunk_count = 0
            try:
                async for chunk in llm_adapter.chat_stream(
                    messages=all_messages,
                    tools=tools,
                    provider_name=resolved_provider,
                    model=resolved_model,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    top_p=request.top_p,
                ):
                    final_answer += chunk
                    chunk_count += 1
                    data = ChatStreamChunk(
                        id=chat_id,
                        content=chunk,
                        model=resolved_model,
                        provider=resolved_provider,
                    )
                    yield f"data: {data.model_dump_json()}\n\n"

                done_data = ChatStreamChunk(
                    id=chat_id,
                    content="",
                    model=resolved_model,
                    provider=resolved_provider,
                    done=True,
                )
                yield f"data: {done_data.model_dump_json()}\n\n"

                assistant_msg = {"role": "assistant", "content": final_answer}
                if not conv["messages"] or conv["messages"][-1] != assistant_msg:
                    conv["messages"].append(assistant_msg)
                    conv["updated_at"] = datetime.now(timezone.utc).isoformat()
                    conversations_store.set(conv_id, conv)

                _schedule_memory_update(
                    conv["messages"], conv_id, agent_id,
                    provider_name=resolved_provider,
                )

                elapsed = time.time() - start_time
                logger.success(f"[STREAM] Stream completed & saved: conv={conv_id}, chunks={chunk_count}, elapsed={elapsed:.2f}s")
            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(f"[STREAM] Stream failed: conv={conv_id}, elapsed={elapsed:.2f}s, error={e}")
                error_data = ChatStreamChunk(
                    id=chat_id,
                    content=f"[Error] {str(e)}",
                    model=resolved_model,
                    provider=resolved_provider,
                    done=True,
                )
                yield f"data: {error_data.model_dump_json()}\n\n"

        return StreamingResponse(
            stream_with_save(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # 工具调用循环：有工具时走程序化调用流程（执行→处理→回传），无工具时走普通对话
    if tools:
        result = await _execute_tool_call_loop(
            messages=all_messages,
            tools=tools,
            provider_name=resolved_provider,
            model=resolved_model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            top_p=request.top_p,
        )
    else:
        result = await llm_adapter.chat(
            messages=all_messages,
            provider_name=resolved_provider,
        model=resolved_model,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        top_p=request.top_p,
    )

    assistant_msg = {"role": "assistant", "content": result}
    if not conv["messages"] or conv["messages"][-1] != assistant_msg:
        conv["messages"].append(assistant_msg)
        conv["updated_at"] = datetime.now(timezone.utc).isoformat()
        conversations_store.set(conv_id, conv)

    _schedule_memory_update(
        conv["messages"], conv_id, agent_id,
        provider_name=resolved_provider,
    )

    elapsed = time.time() - start_time
    logger.success(f"[API] POST /chat/conversations/{conv_id}/messages - Success: elapsed={elapsed:.2f}s, response_len={len(result)}")

    return ChatResponse(
        id=str(uuid.uuid4()),
        content=result,
        model=resolved_model,
        provider=resolved_provider,
    )
