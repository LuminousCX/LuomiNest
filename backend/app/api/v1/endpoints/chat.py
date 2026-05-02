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

    if request.stream:
        logger.info(f"[API] POST /chat/completions - Starting stream response")
        return StreamingResponse(
            _stream_chat(messages, request, resolved_provider, resolved_model),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    try:
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


async def _stream_chat(messages: list[dict], request: ChatRequest, provider: str, model: str):
    start_time = time.time()
    chat_id = str(uuid.uuid4())
    chunk_count = 0

    logger.info(f"[STREAM] Starting stream: chat_id={chat_id}, provider={provider}, model={model}")

    try:
        async for chunk in llm_adapter.chat_stream(
            messages=messages,
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

    if request.stream:
        logger.info(f"[API] POST /chat/conversations/{conv_id}/messages - Starting stream response")

        async def stream_with_save():
            final_answer = ""
            chat_id = str(uuid.uuid4())
            chunk_count = 0
            try:
                async for chunk in llm_adapter.chat_stream(
                    messages=all_messages,
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
