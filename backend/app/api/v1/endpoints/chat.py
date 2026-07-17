import uuid
import time
from fastapi import APIRouter, UploadFile, File, Form, Query
from fastapi.responses import JSONResponse
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
from app.core.utils import utc_now, sse_response, require_store, ok
from app.core.exceptions import NotFoundError, ValidationError

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
        f"stream={request.stream}, ts={request_ts}, "
        f"is_sub_agent={request.is_sub_agent}, agent_depth={request.agent_depth}"
    )

    # Agent 集群调用递归守卫：防止 Agent A→B→A 无限循环
    if request.agent_depth > 3:
        raise HTTPException(
            status_code=400,
            detail="已达到最大 Agent 调用深度（3），无法继续递归调用",
        )

    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    # Ultra 模式跳过 system prompt（含用户画像引用），减少 token 消耗
    _conv_chat_mode = None
    if request.conversation_id:
        _conv = await conversation_store.get_async(request.conversation_id)
        if _conv:
            _conv_chat_mode = _conv.get("chat_mode")
    if _conv_chat_mode != "ultra":
        user_query = context_service.get_user_query(messages)
        system_prompt = context_service.build_system_prompt(request.agent_id, user_context=user_query)
        messages = [{"role": "system", "content": system_prompt}] + messages

    messages = context_service.inject_timestamp_prompt(messages)
    # 子 Agent 调用不注入主 Agent 记忆，避免污染独立上下文
    # Ultra 模式跳过 inject_memory（含用户画像 <user_memory>），减少 token 消耗
    if not request.is_sub_agent and _conv_chat_mode != "ultra":
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
    process_result = await ctx_mgr.process(messages)
    messages = process_result["messages"]

    if request.stream:
        logger.info("[API] POST /chat/completions - Starting stream response")
        return sse_response(
            _chat_service.stream_chat(messages, request, resolved_provider, resolved_model, agent_id=request.agent_id),
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

    # 非流式 /chat/completions 写入记忆（子 Agent 调用跳过，避免污染主 Agent 记忆）
    if not request.is_sub_agent:
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
async def list_conversations(
    agent_id: str | None = None,
    include_hidden: bool = Query(default=False, description="是否包含隐藏对话"),
):
    logger.info(f"[API] GET /chat/conversations - Listing conversations, agent_id={agent_id}, include_hidden={include_hidden}")
    conv_list = await conversation_store.list_conversations_async(agent_id, include_hidden=include_hidden)
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
            chat_mode=meta.get("chat_mode", "normal"),
            is_hidden=bool(meta.get("is_hidden", False)),
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
        f"Creating conversation: title={request.title}, agent_id={request.agent_id}, chat_mode={request.chat_mode}"
    )
    conv_id = str(uuid.uuid4())
    now = utc_now()
    conv = {
        "id": conv_id,
        "title": request.title or "New Conversation",
        "agent_id": request.agent_id,
        "model": request.model,
        "provider": request.provider,
        "chat_mode": request.chat_mode or "normal",
        "is_hidden": request.is_hidden,
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


async def _trigger_final_distill(conv_id: str, conv: dict) -> None:
    """对话结束前触发最终蒸馏（离开/删除/批量删除共用）。"""
    if not (conv and conv.get("messages")):
        return
    from app.services.distillation_service import distillation_service
    agent_id = await _resolve_agent_id(conv)
    await distillation_service.final_distill(
        agent_id, conv_id, conv["messages"], llm_adapter,
    )


async def _rebuild_conversation_memory(conv_id: str, conv: dict, agent_id: str) -> None:
    """消息变更后重建对话级记忆（截断/删除消息共用）。"""
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


@router.post("/conversations/{conv_id}/leave")
async def leave_conversation(conv_id: str):
    """用户离开/切换对话时触发最终蒸馏"""
    logger.info(f"[API] POST /chat/conversations/{conv_id}/leave")
    try:
        conv = await conversation_store.get_async(conv_id)
        await _trigger_final_distill(conv_id, conv)
    except Exception as distill_err:
        logger.warning(f"[API] Final distill on leave failed: {distill_err}")
    return ok({"left": True})


@router.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: str):
    logger.info(f"[API] DELETE /chat/conversations/{conv_id} - Moving to trash")
    # 对话移到回收站前触发最终蒸馏
    try:
        conv = await conversation_store.get_async(conv_id)
        await _trigger_final_distill(conv_id, conv)
    except Exception as distill_err:
        logger.warning(f"[API] Final distill on delete failed: {distill_err}")

    await conversation_store.soft_delete_async(conv_id)
    logger.success(f"[API] DELETE /chat/conversations/{conv_id} - Moved to trash")
    return ok({"deleted": True})
    

class RenameConversationRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)


@router.patch("/conversations/{conv_id}/rename")
async def rename_conversation(conv_id: str, request: RenameConversationRequest):
    logger.info(f"[API] PATCH /chat/conversations/{conv_id}/rename - title_len={len(request.title)}")
    success = await conversation_store.rename_async(conv_id, request.title)
    if not success:
        raise NotFoundError(f"Conversation {conv_id} not found")
    logger.success(f"[API] PATCH /chat/conversations/{conv_id}/rename - Renamed")
    return ok({"renamed": True, "title": request.title})


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
    conv = await require_store(conversation_store, conv_id, "Conversation")
    conv["messages"] = conv["messages"][:request.keep_count]
    await _chat_service.persist_conv(conv_id, conv)

    # 截断的是尾部，重建对话级记忆
    agent_id = await _resolve_agent_id(conv)
    if agent_id:
        try:
            await _rebuild_conversation_memory(conv_id, conv, agent_id)
        except Exception as mem_err:
            logger.warning(f"[Memory] Rebuild after truncate failed: {mem_err}")

    logger.success(
        f"[API] PATCH /chat/conversations/{conv_id}/messages - "
        f"Truncated to {request.keep_count} messages"
    )
    return ok({"truncated": True, "keep_count": request.keep_count})


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

    conv = await require_store(conversation_store, conv_id, "Conversation")

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

    # Ultra 模式跳过 system prompt（含用户画像引用），减少 token 消耗
    if conv.get("chat_mode") != "ultra":
        user_query = context_service.get_user_query(conv["messages"])
        system_prompt = context_service.build_system_prompt(conv.get("agent_id"), user_context=user_query)
        all_messages: list[dict] = [{"role": "system", "content": system_prompt}]
    else:
        all_messages: list[dict] = []

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
    agent_id = await _resolve_agent_id(conv, request.agent_id)
    # Ultra 模式跳过 inject_memory（含用户画像 <user_memory>），减少 token 消耗
    if conv.get("chat_mode") != "ultra":
        all_messages = await context_service.inject_memory(
            all_messages, agent_id, resolved_provider, conv_id,
            llm_adapter=llm_adapter,
        )

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
    conv = await require_store(conversation_store, conv_id, "Conversation")

    for msg in conv["messages"]:
        if msg.get("id") == request.message_id:
            versions = msg.get("versions", [])
            if not versions or request.current_version < 0 or request.current_version >= len(versions):
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
            return ok({"updated": True})

    raise NotFoundError(f"Message {request.message_id} not found in conversation {conv_id}")


@router.delete("/conversations/{conv_id}/messages/{message_id}")
async def delete_message(conv_id: str, message_id: str):
    logger.info(
        f"[API] DELETE /chat/conversations/{conv_id}/messages/{message_id} - Deleting message"
    )
    conv = await require_store(conversation_store, conv_id, "Conversation")

    # 找到被删消息在原始列表中的位置
    deleted_idx = None
    deleted_role = None
    for i, m in enumerate(conv["messages"]):
        if m.get("id") == message_id:
            deleted_idx = i
            deleted_role = m.get("role")
            break

    if deleted_idx is None:
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
                await _rebuild_conversation_memory(conv_id, conv, agent_id)
            except Exception as mem_err:
                logger.warning(f"[Memory] Rebuild after delete failed: {mem_err}")
        else:
            logger.info("[Memory] Middle message deleted, tail unchanged — skip rebuild")

    logger.success(
        f"[API] DELETE /chat/conversations/{conv_id}/messages/{message_id} - Message deleted"
    )
    return ok({"deleted": True})
    

@router.post("/conversations/{conv_id}/messages")
async def add_message(conv_id: str, request: ChatRequest):
    start_time = time.time()
    logger.info(f"[API] POST /chat/conversations/{conv_id}/messages - Adding message")

    conv = await require_store(conversation_store, conv_id, "Conversation")

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

    # Ultra 模式跳过 system prompt（含用户画像引用），减少 token 消耗
    if conv.get("chat_mode") != "ultra":
        user_query = context_service.get_user_query(conv["messages"])
        system_prompt = context_service.build_system_prompt(conv.get("agent_id"), user_context=user_query)
        all_messages: list[dict] = [{"role": "system", "content": system_prompt}]
    else:
        all_messages: list[dict] = []

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
    agent_id = await _resolve_agent_id(conv, request.agent_id)
    # Ultra 模式跳过 inject_memory（含用户画像 <user_memory>），减少 token 消耗
    if conv.get("chat_mode") != "ultra":
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
    process_result = await ctx_mgr.process(all_messages)
    all_messages = process_result["messages"]

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
            chat_mode=meta.get("chat_mode", "normal"),
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
    return ok({"restored": True})


@router.delete("/trash/{conv_id}")
async def permanent_delete_conversation(conv_id: str):
    logger.info(f"[API] DELETE /chat/trash/{conv_id} - Permanent deleting conversation")
    deleted = await conversation_store.permanent_delete_async(conv_id)
    if not deleted:
        logger.warning(f"[API] DELETE /chat/trash/{conv_id} - Delete failed, not found")
        return {"error": "not found", "data": {"deleted": False}}
    logger.success(f"[API] DELETE /chat/trash/{conv_id} - Permanently deleted")
    return ok({"deleted": True})
    

@router.delete("/trash")
async def empty_trash(agent_id: str | None = None):
    logger.info(f"[API] DELETE /chat/trash - Emptying trash, agent_id={agent_id}")
    count = await conversation_store.empty_trash_async(agent_id)
    logger.success(f"[API] DELETE /chat/trash - Emptied {count} items")
    return ok({"deleted_count": count})
    

@router.post("/trash/batch-restore")
async def batch_restore(request: BatchIdsRequest):
    logger.info(f"[API] POST /chat/trash/batch-restore - Restoring {len(request.ids)} items")
    count = await conversation_store.batch_restore_async(request.ids)
    logger.success(f"[API] POST /chat/trash/batch-restore - Restored {count} items")
    return ok({"restored_count": count})


@router.post("/trash/batch-delete")
async def batch_permanent_delete(request: BatchIdsRequest):
    logger.info(f"[API] POST /chat/trash/batch-delete - Deleting {len(request.ids)} items")
    count = await conversation_store.batch_permanent_delete_async(request.ids)
    logger.success(f"[API] POST /chat/trash/batch-delete - Deleted {count} items")
    return ok({"deleted_count": count})
    

@router.post("/conversations/batch-delete")
async def batch_soft_delete(request: BatchIdsRequest):
    logger.info(f"[API] POST /chat/conversations/batch-delete - Moving {len(request.ids)} to trash")

    # 为每个对话触发最终蒸馏（与单个删除行为对齐）
    for conv_id in request.ids:
        try:
            conv = await conversation_store.get_async(conv_id)
            await _trigger_final_distill(conv_id, conv)
        except Exception as distill_err:
            logger.warning(f"[Memory] Final distill on batch delete failed for {conv_id}: {distill_err}")

    count = await conversation_store.batch_soft_delete_async(request.ids)
    logger.success(f"[API] POST /chat/conversations/batch-delete - Moved {count} to trash")
    return ok({"deleted_count": count})
    

@router.post("/conversations/{conv_id}/compress")
async def compress_conversation(conv_id: str):
    """手动压缩对话上下文。"""
    logger.info(f"[API] POST /chat/conversations/{conv_id}/compress - Compressing conversation")
    conv = await require_store(conversation_store, conv_id, "Conversation")

    agent_id = await _resolve_agent_id(conv)
    resolved_provider = conv.get("provider") or llm_adapter.default_provider
    resolved_model = conv.get("model") or llm_adapter.get_provider(resolved_provider).default_model

    # 构建完整消息列表
    user_query = context_service.get_user_query(conv.get("messages", []))
    system_prompt = context_service.build_system_prompt(agent_id, user_context=user_query)
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

    # 回写 conversation（去除 system 消息后存储）
    non_system_messages = [m for m in compressed_messages if m.get("role") != "system"]
    # 将摘要消息写回
    conv["messages"] = non_system_messages
    await _chat_service.persist_conv(conv_id, conv)

    logger.success(
        f"[API] POST /chat/conversations/{conv_id}/compress - "
        f"Done: {tokens_before} -> {tokens_after} tokens"
    )
    return ok({
        "compressed": True,
        "tokens_before": tokens_before,
        "tokens_after": tokens_after,
    })

class TTSRequest(BaseModel):
    text: str = Field(..., max_length=2000)
    voice: str = Field(default="default")
    engine: str = Field(default="auto")
    model: str = Field(default="")
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    apiKey: str = Field(default="")
    baseUrl: str = Field(default="")


@router.post("/tts/synthesize")
async def tts_synthesize(request: TTSRequest):
    if not request.text.strip():
        return JSONResponse({"error": "文本内容不能为空"}, status_code=400)

    from fastapi.responses import Response
    from app.utils.tts_text_filter import filter_tts_text
    # 触发 TTS 引擎注册（import 包即注册）
    import app.runtime.provider.tts  # noqa: F401
    from app.runtime.provider.tts.tts_registry import LuminousChenXiTTSRegistry

    # 后端兜底过滤：清理 markdown/emoji/特殊符号
    clean_text = filter_tts_text(request.text)
    if not clean_text:
        return JSONResponse({"error": "过滤后文本为空，无需合成"}, status_code=400)

    # 构建引擎配置 kwargs（仅传递非空值，避免覆盖引擎默认值）
    config: dict = {}
    if request.model:
        config["model"] = request.model
    if request.speed and request.speed != 1.0:
        config["speed"] = request.speed
    if request.apiKey:
        config["apiKey"] = request.apiKey
    if request.baseUrl:
        config["baseUrl"] = request.baseUrl
    if request.voice and request.voice != "default":
        config["voice"] = request.voice

    # 通过 Registry 解析引擎，支持自动降级
    try:
        provider, used_engine = LuminousChenXiTTSRegistry.resolve(request.engine, **config)
    except RuntimeError as e:
        logger.error(f"[API] TTS: no engine available: {e}")
        return JSONResponse({"error": str(e)}, status_code=503)

    try:
        audio_bytes = await provider.synthesize(clean_text, request.voice)
        logger.info(f"[API] TTS synthesized by [{used_engine}]: {clean_text[:60]}...")
        return Response(
            content=audio_bytes,
            media_type="audio/wav",
            headers={"Content-Disposition": "inline"},
        )
    except Exception as e:
        logger.error(f"[API] TTS: engine [{used_engine}] failed: {e}")
        return JSONResponse({"error": f"语音合成失败：{e}"}, status_code=500)


def _detect_tts_device() -> dict:
    """Detect compute device availability for TTS.

    Checks for CUDA (GPU) via torch if installed, otherwise reports CPU.
    pyttsx3 is CPU-only; this info helps the frontend show what's available
    and lets future GPU-based TTS engines be auto-selected.
    """
    import platform

    device = {"type": "cpu", "name": platform.processor() or "Unknown CPU", "cuda_available": False}

    try:
        import torch
        if torch.cuda.is_available():
            device["type"] = "gpu"
            device["name"] = torch.cuda.get_device_name(0)
            device["cuda_available"] = True
            device["cuda_version"] = torch.version.cuda or "unknown"
    except ImportError:
        pass
    except Exception as dev_err:
        logger.debug(f"[API] TTS device detection (torch) failed: {dev_err}")

    return device


@router.get("/tts/engines")
async def tts_engines():
    """Report available TTS engines, device info, and avatar voice bindings."""
    # 触发 TTS 引擎注册
    import app.runtime.provider.tts  # noqa: F401
    from app.runtime.provider.tts.tts_registry import LuminousChenXiTTSRegistry

    # 引擎元数据：显示名称、分类、是否需要 API Key、是否在线
    engine_meta = {
        "edge-tts": {"name": "Edge TTS (在线，免费)", "category": "cloud-free", "needs_api_key": False, "online": True},
        "sherpa-onnx": {"name": "Sherpa-ONNX TTS (离线神经网络)", "category": "local", "needs_api_key": False, "online": False},
        "local": {"name": "本地 TTS (pyttsx3, CPU)", "category": "local", "needs_api_key": False, "online": False},
        "gemini": {"name": "Gemini TTS (Google，免费层)", "category": "cloud-paid", "needs_api_key": True, "online": True},
        "minimax": {"name": "MiniMax TTS (高质量)", "category": "cloud-paid", "needs_api_key": True, "online": True},
        "siliconflow": {"name": "SiliconFlow TTS (CosyVoice2 云端)", "category": "cloud-paid", "needs_api_key": True, "online": True},
        "fish-audio": {"name": "Fish Audio TTS (多语言)", "category": "cloud-paid", "needs_api_key": True, "online": True},
    }

    engines: list[dict] = []
    for engine_id in LuminousChenXiTTSRegistry.list_engines():
        provider_class = LuminousChenXiTTSRegistry.get(engine_id)
        available = LuminousChenXiTTSRegistry.is_available(engine_id)
        meta = engine_meta.get(engine_id, {"name": engine_id, "category": "unknown", "needs_api_key": False, "online": False})

        engine_info: dict = {
            "id": engine_id,
            "name": meta["name"],
            "category": meta["category"],
            "needs_api_key": meta["needs_api_key"],
            "online": meta["online"],
            "available": available,
        }

        # 附加引擎特定信息（default_voices / voices / lang_map）
        if available and provider_class is not None:
            default_voices = getattr(provider_class, "DEFAULT_VOICES", None)
            if default_voices:
                engine_info["default_voices"] = default_voices

            # 本地引擎枚举系统语音列表
            if engine_id == "local":
                try:
                    provider = provider_class()
                    engine_info["voices"] = provider.list_voices()
                    engine_info["lang_map"] = provider.get_lang_map()
                except Exception as lv_err:
                    logger.debug(f"[API] TTS local voice enumeration failed: {lv_err}")

        engines.append(engine_info)

    device = _detect_tts_device()

    # Avatar voice bindings (model_id -> voice/lang)
    from app.services.avatar_manager import LUOMINEST_AVATAR_BINDINGS
    bindings = {
        mid: {
            "model_id": b.model_id,
            "voice": b.voice,
            "voice_lang": b.voice_lang,
            "default_expression": b.default_expression,
        }
        for mid, b in LUOMINEST_AVATAR_BINDINGS.items()
    }

    return {
        "error": None,
        "data": {
            "engines": engines,
            "device": device,
            "avatar_bindings": bindings,
        },
    }


# ---------------------------------------------------------------------------
# STT (Speech-to-Text) endpoints
# ---------------------------------------------------------------------------

# STT 引擎优先级（自动降级顺序）
_STT_FALLBACK_ORDER = ["sherpa-onnx", "funasr", "faster-whisper"]


def _get_stt_provider(engine_id: str | None = None):
    """根据引擎 ID 获取 STT Provider，支持自动降级.

    Args:
        engine_id: 用户指定的引擎 ID，None 时按优先级自动选择

    Returns:
        (provider, engine_id) 元组

    Raises:
        RuntimeError: 所有引擎都不可用
    """
    # 构建尝试顺序：用户指定的优先，其余按 fallback order
    if engine_id and engine_id != "auto":
        try_order = [engine_id] + [e for e in _STT_FALLBACK_ORDER if e != engine_id]
    else:
        try_order = list(_STT_FALLBACK_ORDER)

    errors: list[str] = []

    for eid in try_order:
        try:
            if eid == "sherpa-onnx":
                from app.runtime.provider.stt.sherpa_onnx_stt import SherpaOnnxSTTProvider
                if not SherpaOnnxSTTProvider.is_available():
                    errors.append(f"{eid}: sherpa-onnx 未安装")
                    continue
                provider = SherpaOnnxSTTProvider()
                return provider, eid

            elif eid == "faster-whisper":
                from app.runtime.provider.stt.faster_whisper_stt import FasterWhisperSTTProvider
                if not FasterWhisperSTTProvider.is_available():
                    errors.append(f"{eid}: faster-whisper 未安装")
                    continue
                provider = FasterWhisperSTTProvider()
                return provider, eid

            elif eid == "funasr":
                from app.runtime.provider.stt.funasr_stt import FunASRSTTProvider
                if not FunASRSTTProvider.is_available():
                    errors.append(f"{eid}: funasr 未安装")
                    continue
                provider = FunASRSTTProvider()
                return provider, eid

        except Exception as e:
            errors.append(f"{eid}: {e}")
            logger.warning(f"[API] STT engine [{eid}] failed: {e}, trying next...")

    raise RuntimeError(
        f"所有 STT 引擎均不可用: {'; '.join(errors)}. "
        f"请安装 sherpa-onnx / faster-whisper / funasr 中的至少一个"
    )


@router.post("/stt/transcribe")
async def stt_transcribe(
    audio: "UploadFile" = File(...),
    engine: str = Form(default="auto"),
    language: str = Form(default="auto"),
):
    """语音识别接口 - 接收音频文件，返回识别文本.

    Args:
        audio: 音频文件（wav/mp3/webm/ogg 等）
        engine: STT 引擎 ID（sherpa-onnx / funasr / faster-whisper / auto）
        language: 识别语言（auto/zh/en/ja/ko 等）

    Returns:
        {"error": None, "data": {"text": "...", "engine": "sherpa-onnx"}}
    """
    audio_data = await audio.read()
    if not audio_data:
        return JSONResponse({"error": "音频文件为空"}, status_code=400)

    # 获取音频格式（从文件扩展名推断）
    format_hint = "wav"
    if audio.filename:
        ext = audio.filename.rsplit(".", 1)[-1].lower() if "." in audio.filename else ""
        if ext:
            format_hint = ext

    try:
        provider, used_engine = _get_stt_provider(engine)
    except RuntimeError as e:
        return JSONResponse({"error": str(e)}, status_code=503)

    try:
        text = await provider.transcribe(audio_data, format=format_hint)
        logger.info(f"[API] STT transcribed by [{used_engine}]: {text[:80]}...")
        return {
            "error": None,
            "data": {
                "text": text,
                "engine": used_engine,
            },
        }
    except Exception as e:
        logger.error(f"[API] STT transcribe failed: {e}")
        return JSONResponse({"error": f"语音识别失败：{e}"}, status_code=500)


@router.get("/stt/engines")
async def stt_engines():
    """报告可用的 STT 引擎列表."""
    engines: list[dict] = []

    # Sherpa-ONNX STT
    try:
        from app.runtime.provider.stt.sherpa_onnx_stt import SherpaOnnxSTTProvider
        sherpa_available = SherpaOnnxSTTProvider.is_available()
        sherpa_model_ready = SherpaOnnxSTTProvider.is_model_ready() if sherpa_available else False
        engines.append({
            "id": "sherpa-onnx",
            "name": "Sherpa-ONNX (离线, SenseVoice)",
            "online": False,
            "available": sherpa_available,
            "model_ready": sherpa_model_ready,
            "languages": ["zh", "en", "ja", "ko", "yue", "auto"],
            "description": "基于 ONNX 的离线语音识别，默认使用 SenseVoice 模型，支持中英日韩粤",
            "model_types": ["sense_voice", "paraformer", "whisper"],
        })
    except ImportError:
        engines.append({
            "id": "sherpa-onnx",
            "name": "Sherpa-ONNX (离线, SenseVoice)",
            "online": False,
            "available": False,
        })

    # FunASR STT
    try:
        from app.runtime.provider.stt.funasr_stt import FunASRSTTProvider
        funasr_available = FunASRSTTProvider.is_available()
        engines.append({
            "id": "funasr",
            "name": "FunASR (离线, 阿里达摩院)",
            "online": False,
            "available": funasr_available,
            "model_ready": funasr_available,
            "languages": ["zh", "en", "auto"],
            "description": "阿里达摩院 FunASR，默认使用 SenseVoiceSmall，中文识别效果优秀",
            "models": FunASRSTTProvider.SUPPORTED_MODELS,
        })
    except ImportError:
        engines.append({
            "id": "funasr",
            "name": "FunASR (离线, 阿里达摩院)",
            "online": False,
            "available": False,
        })

    # Faster Whisper STT
    try:
        from app.runtime.provider.stt.faster_whisper_stt import FasterWhisperSTTProvider, MODEL_SIZES as FW_MODEL_SIZES
        fw_available = FasterWhisperSTTProvider.is_available()
        engines.append({
            "id": "faster-whisper",
            "name": "Faster Whisper (离线, CTranslate2 加速)",
            "online": False,
            "available": fw_available,
            "model_ready": fw_available,
            "languages": ["zh", "en", "ja", "ko", "fr", "de", "es", "auto"],
            "description": "基于 CTranslate2 的 Whisper 加速版，比原版快 4 倍以上",
            "model_sizes": list(FW_MODEL_SIZES.keys()),
        })
    except ImportError:
        engines.append({
            "id": "faster-whisper",
            "name": "Faster Whisper (离线, CTranslate2 加速)",
            "online": False,
            "available": False,
        })

    return {
        "error": None,
        "data": {
            "engines": engines,
            "fallback_order": _STT_FALLBACK_ORDER,
        },
    }
