import uuid
import time
from datetime import datetime, timezone
from fastapi import APIRouter
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi import HTTPException
from typing import Any
from pydantic import BaseModel, Field
from loguru import logger

from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ConversationCreate,
    ConversationResponse,
    ConversationListResponse,
    ConversationSearchResult,
    TrashListItemResponse,
    BatchIdsRequest,
)
from app.runtime.provider.llm.adapter import llm_adapter
from app.infrastructure.database.conversation_store import conversation_store
from app.core.context import get_context_manager
from app.services.context_service import context_service
from app.services.suggestion_service import suggestion_service
from app.services.chat_service import ChatService
from app.core.config import get_settings

_chat_service = ChatService(context_service, suggestion_service)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/completions")
async def chat_completions(request: ChatRequest):
    start_time = time.time()
    resolved_provider = request.provider or llm_adapter.default_provider
    resolved_model = request.model or llm_adapter.get_provider(resolved_provider).default_model
    request_ts = request.timestamp or time.time()
    logger.info(
        f"[API] POST /chat/completions - "
        f"provider={resolved_provider}, model={resolved_model}, "
        f"stream={request.stream}, ts={request_ts}"
    )

    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    system_prompt = context_service.build_system_prompt(request.agent_id)
    messages = [{"role": "system", "content": system_prompt}] + messages
    messages = context_service.inject_timestamp_prompt(messages)
    messages = await context_service.inject_memory(messages, request.agent_id, resolved_provider, llm_adapter=llm_adapter)

    if request.file_content:
        supports_vision = llm_adapter.get_provider(resolved_provider).supports_multimodal(resolved_model)
        messages = context_service.inject_file_content(
            messages, request.file_content, request.file_type or "text",
            supports_vision=supports_vision, file_name=request.file_name,
        )

    if request.search_results:
        for i in range(len(messages) - 1, -1, -1):
            if messages[i]["role"] == "user":
                messages[i]["content"] += f"\n\n[搜索结果]\n{request.search_results}"
                break

    ctx_mgr = get_context_manager(resolved_provider, resolved_model)
    messages = await ctx_mgr.process(messages)

    if request.stream:
        logger.info("[API] POST /chat/completions - Starting stream response")
        return StreamingResponse(
            _chat_service.stream_chat(messages, request, resolved_provider, resolved_model, agent_id=request.agent_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    gen_state: dict = {"content": "", "reasoning": "", "aborted": False, "started": True}
    await _chat_service.non_stream_generate(
        gen_state, messages,
        resolved_provider, resolved_model,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        top_p=request.top_p,
    )

    if gen_state["aborted"]:
        raise HTTPException(status_code=400, detail=gen_state["content"].removeprefix("[Error] "))

    result_content = gen_state["content"] or ""

    # 非流式 /chat/completions 写入记忆
    try:
        user_msgs = [m for m in messages if m.get("role") == "user"]
        if user_msgs:
            thread_id = request.conversation_id or f"completions-{uuid.uuid4().hex[:8]}"
            await context_service.schedule_memory_update(
                messages, thread_id, request.agent_id,
                llm_adapter=llm_adapter,
            )
    except Exception as mem_err:
        logger.warning(f"[API] /chat/completions memory update failed: {mem_err}")

    elapsed = time.time() - start_time
    logger.success(
        f"[API] POST /chat/completions - "
        f"Success: elapsed={elapsed:.2f}s, response_len={len(result_content)}"
    )
    return ChatResponse(
        id=str(uuid.uuid4()),
        content=result_content,
        model=resolved_model,
        provider=resolved_provider,
    )


@router.get("/conversations", response_model=list[ConversationListResponse])
async def list_conversations(agent_id: str | None = None):
    logger.info(f"[API] GET /chat/conversations - Listing conversations, agent_id={agent_id}")
    conv_list = await conversation_store.list_conversations_async(agent_id)
    result = []
    for meta in conv_list:
        conv_id = meta.get("id")
        if not conv_id:
            logger.warning("[API] Skipping conversation with missing id in index")
            continue
        result.append(ConversationListResponse(
            id=conv_id,
            title=meta.get("title", "New Conversation"),
            agent_id=meta.get("agent_id"),
            model=meta.get("model"),
            provider=meta.get("provider"),
            last_message=meta.get("last_message"),
            created_at=meta.get("created_at", ""),
            updated_at=meta.get("updated_at", ""),
        ))
    logger.success(f"[API] GET /chat/conversations - Success: returned {len(result)} conversations")
    return result


@router.get("/conversations/search", response_model=list[ConversationSearchResult])
async def search_conversations(keyword: str, agent_id: str | None = None):
    req_id = str(uuid.uuid4())[:8]
    logger.info(
        f"[API] GET /chat/conversations/search - "
        f"req_id={req_id}, keyword_len={len(keyword)}, "
        f"agent_id={'***' if agent_id else None}"
    )
    results = await conversation_store.search_conversations_async(keyword, agent_id)
    response = [
        ConversationSearchResult(
            id=r["id"],
            title=r["title"],
            snippet=r["snippet"],
            updated_at=r["updated_at"],
        )
        for r in results
    ]
    logger.success(
        f"[API] GET /chat/conversations/search - req_id={req_id}, found {len(response)} results"
    )
    return response


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(request: ConversationCreate):
    logger.info(
        f"[API] POST /chat/conversations - "
        f"Creating conversation: title={request.title}, agent_id={request.agent_id}"
    )
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
    await conversation_store.set_async(conv_id, conv)
    logger.success(f"[API] POST /chat/conversations - Conversation created: id={conv_id}")
    return ConversationResponse(**conv)


@router.get("/conversations/{conv_id}", response_model=ConversationResponse)
async def get_conversation(conv_id: str):
    logger.info(f"[API] GET /chat/conversations/{conv_id} - Fetching conversation")
    conv = await conversation_store.get_async(conv_id)
    if not conv:
        logger.error(f"[API] GET /chat/conversations/{conv_id} - Conversation not found")
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Conversation {conv_id} not found")
    logger.success(
        f"[API] GET /chat/conversations/{conv_id} - "
        f"Success: title={conv['title']}, messages={len(conv.get('messages', []))}"
    )
    return ConversationResponse(**conv)


async def _resolve_agent_id(conv: dict, request_agent_id: str | None = None) -> str | None:
    """解析并回填 agent_id：优先 conv 存储，其次 request，最后 agents_store 兜底。"""
    agent_id = conv.get("agent_id") or request_agent_id
    if not agent_id:
        from app.infrastructure.database.json_store import agents_store
        all_agents = await agents_store.all_async()
        if all_agents:
            agent_id = all_agents[0].get("id")
    if agent_id and not conv.get("agent_id"):
        conv["agent_id"] = agent_id
    return agent_id


@router.post("/conversations/{conv_id}/leave")
async def leave_conversation(conv_id: str):
    """用户离开/切换对话时触发最终蒸馏"""
    logger.info(f"[API] POST /chat/conversations/{conv_id}/leave")
    try:
        conv = await conversation_store.get_async(conv_id)
        if conv and conv.get("messages"):
            from app.services.distillation_service import distillation_service
            agent_id = await _resolve_agent_id(conv)
            await distillation_service.final_distill(
                agent_id, conv_id, conv["messages"], llm_adapter,
            )
    except Exception as distill_err:
        logger.warning(f"[API] Final distill on leave failed: {distill_err}")
    return {"error": None, "data": {"left": True}}


@router.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: str):
    logger.info(f"[API] DELETE /chat/conversations/{conv_id} - Moving to trash")
    # 对话移到回收站前触发最终蒸馏
    try:
        conv = await conversation_store.get_async(conv_id)
        if conv and conv.get("messages"):
            from app.services.distillation_service import distillation_service
            agent_id = await _resolve_agent_id(conv)
            await distillation_service.final_distill(
                agent_id, conv_id, conv["messages"], llm_adapter,
            )
    except Exception as distill_err:
        logger.warning(f"[API] Final distill on delete failed: {distill_err}")

    await conversation_store.soft_delete_async(conv_id)
    logger.success(f"[API] DELETE /chat/conversations/{conv_id} - Moved to trash")
    return {"error": None, "data": {"deleted": True}}


class RenameConversationRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)


@router.patch("/conversations/{conv_id}/rename")
async def rename_conversation(conv_id: str, request: RenameConversationRequest):
    logger.info(f"[API] PATCH /chat/conversations/{conv_id}/rename - title_len={len(request.title)}")
    success = await conversation_store.rename_async(conv_id, request.title)
    if not success:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Conversation {conv_id} not found")
    logger.success(f"[API] PATCH /chat/conversations/{conv_id}/rename - Renamed")
    return {"error": None, "data": {"renamed": True, "title": request.title}}


class TruncateMessagesRequest(BaseModel):
    keep_count: int = Field(..., ge=0)


class DeleteMessageRequest(BaseModel):
    message_id: str


@router.patch("/conversations/{conv_id}/messages")
async def truncate_messages(conv_id: str, request: TruncateMessagesRequest):
    logger.info(
        f"[API] PATCH /chat/conversations/{conv_id}/messages - "
        f"Truncating to {request.keep_count}"
    )
    conv = await conversation_store.get_async(conv_id)
    if not conv:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Conversation {conv_id} not found")
    conv["messages"] = conv["messages"][:request.keep_count]
    await _chat_service.persist_conv(conv_id, conv)

    # 截断的是尾部，重建对话级记忆
    agent_id = await _resolve_agent_id(conv)
    if agent_id:
        try:
            from app.engines.memory import get_memory_engine
            from app.services.distillation_service import distillation_service as ds
            engine = get_memory_engine(agent_id)
            engine.clear_conversation_data(conv_id)
            ds.reset_distill_state(conv_id)
            await context_service.schedule_memory_update(
                conv["messages"], conv_id, agent_id, llm_adapter=llm_adapter,
            )
            await ds.maybe_distill(
                agent_id, conv_id, conv["messages"], llm_adapter,
            )
        except Exception as mem_err:
            logger.warning(f"[Memory] Rebuild after truncate failed: {mem_err}")

    logger.success(
        f"[API] PATCH /chat/conversations/{conv_id}/messages - "
        f"Truncated to {request.keep_count} messages"
    )
    return {"error": None, "data": {"truncated": True, "keep_count": request.keep_count}}


class RegenerateRequest(BaseModel):
    model: str | None = None
    provider: str | None = None
    stream: bool = True
    versions: list[dict[str, Any]] | None = None
    agent_id: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None


class UpdateMessageVersionRequest(BaseModel):
    message_id: str
    current_version: int


@router.post("/conversations/{conv_id}/regenerate")
async def regenerate_message(conv_id: str, request: RegenerateRequest):
    start_time = time.time()
    logger.info(f"[API] POST /chat/conversations/{conv_id}/regenerate")

    conv = await conversation_store.get_async(conv_id)
    if not conv:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Conversation {conv_id} not found")

    while conv["messages"] and conv["messages"][-1].get("role") == "assistant":
        conv["messages"].pop()
    await _chat_service.persist_conv(conv_id, conv)

    resolved_provider = (
        request.provider or conv.get("provider") or llm_adapter.default_provider
    )
    resolved_model = (
        request.model or conv.get("model")
        or llm_adapter.get_provider(resolved_provider).default_model
    )

    system_prompt = context_service.build_system_prompt(conv.get("agent_id"))
    all_messages: list[dict] = [{"role": "system", "content": system_prompt}]

    supports_vision = llm_adapter.get_provider(resolved_provider).supports_multimodal(resolved_model)

    for m in conv["messages"]:
        content = m["content"]
        if m.get("role") == "user" and m.get("file_content"):
            content = context_service.build_content_with_file(
                content, m["file_content"], m.get("file_type", "text"),
                supports_vision=supports_vision, file_name=m.get("file_name"),
            )
        msg = {"role": m["role"], "content": content}
        all_messages.append(msg)

    all_messages = context_service.inject_timestamp_prompt(all_messages)
    # 始终以对话存储的 agent_id 为准，确保记忆读写一致
    agent_id = conv.get("agent_id") or request.agent_id
    if not agent_id:
        from app.infrastructure.database.json_store import agents_store
        all_agents = await agents_store.all_async()
        if all_agents:
            agent_id = all_agents[0].get("id")
    # 回写到对话中，确保后续使用一致
    if agent_id and not conv.get("agent_id"):
        conv["agent_id"] = agent_id
    all_messages = await context_service.inject_memory(
        all_messages, agent_id, resolved_provider, conv_id,
        llm_adapter=llm_adapter,
    )

    ctx_mgr = get_context_manager(resolved_provider, resolved_model)
    all_messages = await ctx_mgr.process(all_messages)

    gen_state: dict = {
        "content": "",
        "reasoning": "",
        "aborted": False,
        "started": True,
        "model": resolved_model,
        "provider": resolved_provider,
    }

    if request.stream:
        return await _chat_service.stream_response(
            conv_id, conv, request, all_messages,
            resolved_provider, resolved_model,
            agent_id, gen_state, start_time,
            versions=request.versions,
        )

    await _chat_service.non_stream_generate(
        gen_state, all_messages,
        resolved_provider, resolved_model,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        top_p=request.top_p,
    )

    persist_state = dict(gen_state)
    if persist_state["aborted"] and persist_state["content"].startswith("[Error]"):
        persist_state["content"] = ""

    _chat_service.save_assistant_message(conv, persist_state, versions=request.versions)
    await _chat_service.persist_conv(conv_id, conv)

    try:
        await context_service.schedule_memory_update(
            [dict(m) for m in conv["messages"]], conv_id, agent_id,
            llm_adapter=llm_adapter,
        )
    except Exception as mem_err:
        logger.warning(f"[API] Regenerate memory update failed: {mem_err}")

    try:
        from app.services.distillation_service import distillation_service
        await distillation_service.maybe_distill(agent_id, conv_id, conv["messages"], llm_adapter)
    except Exception as distill_err:
        logger.warning(f"[API] Regenerate distillation failed: {distill_err}")

    elapsed = time.time() - start_time
    logger.success(f"[API] Regenerate done: conv={conv_id}, elapsed={elapsed:.2f}s")

    return ChatResponse(
        id=str(uuid.uuid4()),
        content=gen_state["content"],
        model=resolved_model,
        provider=resolved_provider,
    )


@router.patch("/conversations/{conv_id}/messages/version")
async def update_message_version(conv_id: str, request: UpdateMessageVersionRequest):
    logger.info(
        f"[API] PATCH /chat/conversations/{conv_id}/messages/version - "
        f"Updating message version for {request.message_id}"
    )
    conv = await conversation_store.get_async(conv_id)
    if not conv:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Conversation {conv_id} not found")

    for msg in conv["messages"]:
        if msg.get("id") == request.message_id:
            versions = msg.get("versions", [])
            if not versions or request.current_version < 0 or request.current_version >= len(versions):
                from app.core.exceptions import ValidationError
                raise ValidationError(f"Invalid version index {request.current_version}")
            msg["current_version"] = request.current_version
            v = versions[request.current_version]
            msg["content"] = v.get("content", "")
            msg["reasoning_content"] = v.get("reasoning_content")
            msg["model"] = v.get("model")
            msg["provider"] = v.get("provider")
            if v.get("suggested_questions") is not None:
                msg["suggested_questions"] = v["suggested_questions"]
            elif "suggested_questions" in msg:
                del msg["suggested_questions"]
            await _chat_service.persist_conv(conv_id, conv)
            logger.success(
                f"[API] PATCH /chat/conversations/{conv_id}/messages/version - Version updated"
            )
            return {"error": None, "data": {"updated": True}}

    from app.core.exceptions import NotFoundError
    raise NotFoundError(f"Message {request.message_id} not found in conversation {conv_id}")


@router.delete("/conversations/{conv_id}/messages/{message_id}")
async def delete_message(conv_id: str, message_id: str):
    logger.info(
        f"[API] DELETE /chat/conversations/{conv_id}/messages/{message_id} - Deleting message"
    )
    conv = await conversation_store.get_async(conv_id)
    if not conv:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Conversation {conv_id} not found")

    # 找到被删消息在原始列表中的位置
    deleted_idx = None
    deleted_role = None
    for i, m in enumerate(conv["messages"]):
        if m.get("id") == message_id:
            deleted_idx = i
            deleted_role = m.get("role")
            break

    if deleted_idx is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Message {message_id} not found in conversation {conv_id}")

    # 找到最后一条用户消息的位置（用于尾部判断）
    last_user_idx = -1
    for i, m in enumerate(conv["messages"]):
        if m.get("role") == "user":
            last_user_idx = i

    conv["messages"] = [m for m in conv["messages"] if m.get("id") != message_id]
    await _chat_service.persist_conv(conv_id, conv)

    # 删除用户消息时始终重建记忆，删除中间AI消息则跳过
    agent_id = await _resolve_agent_id(conv)
    if agent_id and conv["messages"]:
        if deleted_role == "user" or deleted_idx >= last_user_idx:
            try:
                from app.engines.memory import get_memory_engine
                from app.services.distillation_service import distillation_service as ds
                engine = get_memory_engine(agent_id)
                engine.clear_conversation_data(conv_id)
                ds.reset_distill_state(conv_id)
                await context_service.schedule_memory_update(
                    conv["messages"], conv_id, agent_id, llm_adapter=llm_adapter,
                )
                await ds.maybe_distill(
                    agent_id, conv_id, conv["messages"], llm_adapter,
                )
            except Exception as mem_err:
                logger.warning(f"[Memory] Rebuild after delete failed: {mem_err}")
        else:
            logger.info("[Memory] Middle message deleted, tail unchanged — skip rebuild")

    logger.success(
        f"[API] DELETE /chat/conversations/{conv_id}/messages/{message_id} - Message deleted"
    )
    return {"error": None, "data": {"deleted": True}}


@router.post("/conversations/{conv_id}/messages")
async def add_message(conv_id: str, request: ChatRequest):
    start_time = time.time()
    logger.info(f"[API] POST /chat/conversations/{conv_id}/messages - Adding message")

    conv = await conversation_store.get_async(conv_id)
    if not conv:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Conversation {conv_id} not found")

    last_user_content = ""
    for m in reversed(request.messages):
        if m.role == "user":
            last_user_content = m.content
            break

    _chat_service.save_user_message(
        conv, last_user_content, request.file_content, request.file_name, request.file_type,
    )
    await _chat_service.persist_conv(conv_id, conv)

    resolved_provider = (
        request.provider or conv.get("provider") or llm_adapter.default_provider
    )
    resolved_model = (
        request.model or conv.get("model")
        or llm_adapter.get_provider(resolved_provider).default_model
    )

    system_prompt = context_service.build_system_prompt(conv.get("agent_id"))
    all_messages: list[dict] = [{"role": "system", "content": system_prompt}]

    supports_vision = llm_adapter.get_provider(resolved_provider).supports_multimodal(resolved_model)

    for m in conv["messages"]:
        content = m["content"]
        if m.get("role") == "user" and m.get("file_content"):
            content = context_service.build_content_with_file(
                content, m["file_content"], m.get("file_type", "text"),
                supports_vision=supports_vision, file_name=m.get("file_name"),
            )
        msg = {"role": m["role"], "content": content}
        all_messages.append(msg)

    all_messages = context_service.inject_timestamp_prompt(all_messages)
    # 始终以对话存储的 agent_id 为准，确保记忆读写一致
    agent_id = conv.get("agent_id") or request.agent_id
    if not agent_id:
        from app.infrastructure.database.json_store import agents_store
        all_agents = await agents_store.all_async()
        if all_agents:
            agent_id = all_agents[0].get("id")
    # 回写到对话中，确保后续使用一致
    if agent_id and not conv.get("agent_id"):
        conv["agent_id"] = agent_id
    all_messages = await context_service.inject_memory(
        all_messages, agent_id, resolved_provider, conv_id,
        llm_adapter=llm_adapter,
    )

    if request.search_results:
        for i in range(len(all_messages) - 1, -1, -1):
            if all_messages[i]["role"] == "user":
                all_messages[i]["content"] += f"\n\n[搜索结果]\n{request.search_results}"
                break

    ctx_mgr = get_context_manager(resolved_provider, resolved_model)
    all_messages = await ctx_mgr.process(all_messages)

    gen_state: dict = {
        "content": "",
        "reasoning": "",
        "aborted": False,
        "started": True,
        "model": resolved_model,
        "provider": resolved_provider,
    }

    if request.stream:
        return await _chat_service.stream_response(
            conv_id, conv, request, all_messages,
            resolved_provider, resolved_model,
            agent_id, gen_state, start_time,
            versions=request.versions,
        )

    await _chat_service.non_stream_generate(
        gen_state, all_messages,
        resolved_provider, resolved_model,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        top_p=request.top_p,
    )

    persist_state = dict(gen_state)
    if persist_state["aborted"] and persist_state["content"].startswith("[Error]"):
        persist_state["content"] = ""

    _chat_service.save_assistant_message(conv, persist_state, versions=request.versions)
    await _chat_service.persist_conv(conv_id, conv)
    await context_service.schedule_memory_update(
        [dict(m) for m in conv["messages"]], conv_id, agent_id,
        llm_adapter=llm_adapter,
    )

    try:
        from app.services.distillation_service import distillation_service
        await distillation_service.maybe_distill(agent_id, conv_id, conv["messages"], llm_adapter)
    except Exception as distill_err:
        logger.warning(f"[API] Distillation failed: {distill_err}")

    elapsed = time.time() - start_time
    logger.success(
        f"[API] Done: conv={conv_id}, elapsed={elapsed:.2f}s, "
        f"len={len(gen_state['content'])}, aborted={gen_state['aborted']}"
    )

    return ChatResponse(
        id=str(uuid.uuid4()),
        content=gen_state["content"],
        model=resolved_model,
        provider=resolved_provider,
    )


@router.get("/trash", response_model=list[TrashListItemResponse])
async def list_trash(agent_id: str | None = None):
    logger.info(f"[API] GET /chat/trash - Listing trash, agent_id={agent_id}")
    items = await conversation_store.list_trash_async(agent_id)
    result = []
    for meta in items:
        result.append(TrashListItemResponse(
            id=meta["id"],
            title=meta.get("title", "New Conversation"),
            agent_id=meta.get("agent_id"),
            model=meta.get("model"),
            provider=meta.get("provider"),
            last_message=meta.get("last_message"),
            created_at=meta.get("created_at", ""),
            updated_at=meta.get("updated_at", ""),
            deleted_at=meta.get("deleted_at", ""),
        ))
    logger.success(f"[API] GET /chat/trash - Success: returned {len(result)} items")
    return result


@router.post("/trash/{conv_id}/restore")
async def restore_conversation(conv_id: str):
    logger.info(f"[API] POST /chat/trash/{conv_id}/restore - Restoring conversation")
    restored = await conversation_store.restore_async(conv_id)
    if not restored:
        logger.warning(f"[API] POST /chat/trash/{conv_id}/restore - Restore failed, not found")
        return {"error": "not found", "data": {"restored": False}}
    logger.success(f"[API] POST /chat/trash/{conv_id}/restore - Restored")
    return {"error": None, "data": {"restored": True}}


@router.delete("/trash/{conv_id}")
async def permanent_delete_conversation(conv_id: str):
    logger.info(f"[API] DELETE /chat/trash/{conv_id} - Permanent deleting conversation")
    deleted = await conversation_store.permanent_delete_async(conv_id)
    if not deleted:
        logger.warning(f"[API] DELETE /chat/trash/{conv_id} - Delete failed, not found")
        return {"error": "not found", "data": {"deleted": False}}
    logger.success(f"[API] DELETE /chat/trash/{conv_id} - Permanently deleted")
    return {"error": None, "data": {"deleted": True}}


@router.delete("/trash")
async def empty_trash(agent_id: str | None = None):
    logger.info(f"[API] DELETE /chat/trash - Emptying trash, agent_id={agent_id}")
    count = await conversation_store.empty_trash_async(agent_id)
    logger.success(f"[API] DELETE /chat/trash - Emptied {count} items")
    return {"error": None, "data": {"deleted_count": count}}


@router.post("/trash/batch-restore")
async def batch_restore(request: BatchIdsRequest):
    logger.info(f"[API] POST /chat/trash/batch-restore - Restoring {len(request.ids)} items")
    count = await conversation_store.batch_restore_async(request.ids)
    logger.success(f"[API] POST /chat/trash/batch-restore - Restored {count} items")
    return {"error": None, "data": {"restored_count": count}}


@router.post("/trash/batch-delete")
async def batch_permanent_delete(request: BatchIdsRequest):
    logger.info(f"[API] POST /chat/trash/batch-delete - Deleting {len(request.ids)} items")
    count = await conversation_store.batch_permanent_delete_async(request.ids)
    logger.success(f"[API] POST /chat/trash/batch-delete - Deleted {count} items")
    return {"error": None, "data": {"deleted_count": count}}


@router.post("/conversations/batch-delete")
async def batch_soft_delete(request: BatchIdsRequest):
    logger.info(f"[API] POST /chat/conversations/batch-delete - Moving {len(request.ids)} to trash")

    # 为每个对话触发最终蒸馏（与单个删除行为对齐）
    for conv_id in request.ids:
        try:
            conv = await conversation_store.get_async(conv_id)
            if conv and conv.get("messages"):
                from app.services.distillation_service import distillation_service as ds
                agent_id = await _resolve_agent_id(conv)
                await ds.final_distill(
                    agent_id, conv_id, conv["messages"], llm_adapter,
                )
        except Exception as distill_err:
            logger.warning(f"[Memory] Final distill on batch delete failed for {conv_id}: {distill_err}")

    count = await conversation_store.batch_soft_delete_async(request.ids)
    logger.success(f"[API] POST /chat/conversations/batch-delete - Moved {count} to trash")
    return {"error": None, "data": {"deleted_count": count}}


class TTSRequest(BaseModel):
    text: str = Field(..., max_length=2000)
    voice: str = Field(default="default")


@router.post("/tts/synthesize")
async def tts_synthesize(request: TTSRequest):
    if not request.text.strip():
        return JSONResponse({"error": "text is required"}, status_code=400)

    from fastapi.responses import Response

    # Try Edge TTS first (natural voices, requires network)
    try:
        from app.runtime.provider.tts.edge_tts import EdgeTTSProvider
        settings = get_settings()
        proxy = settings.TTS_PROXY or None
        provider = EdgeTTSProvider(proxy=proxy)
        audio_bytes = await provider.synthesize(request.text, request.voice)
        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={"Content-Disposition": "inline"},
        )
    except ImportError:
        logger.warning("[API] TTS: edge-tts not installed, trying local TTS")
    except Exception as e:
        logger.warning(f"[API] TTS: Edge TTS failed ({e}), falling back to local TTS")

    # Fallback to local TTS (offline, system voice)
    try:
        from app.runtime.provider.tts.local_tts import LocalTTSProvider
        provider = LocalTTSProvider()
        audio_bytes = await provider.synthesize(request.text)
        return Response(
            content=audio_bytes,
            media_type="audio/wav",
            headers={"Content-Disposition": "inline"},
        )
    except ImportError:
        logger.error("[API] TTS: pyttsx3 not installed")
        return JSONResponse(
            {"error": "No TTS engine available. Install edge-tts or pyttsx3"},
            status_code=503,
        )
    except Exception as e:
        logger.error(f"[API] TTS: all providers failed: {e}")
        return JSONResponse({"error": f"TTS synthesis failed: {e}"}, status_code=500)
