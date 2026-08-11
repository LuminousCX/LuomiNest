import uuid
from fastapi import APIRouter, Request, UploadFile, File, Form, Query, Depends
from fastapi.responses import JSONResponse
from fastapi import HTTPException
from typing import Any
from pydantic import BaseModel, Field, field_validator
from loguru import logger

from app.api.v1.deps import get_chat_service, get_conversation_store, get_llm_adapter
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
from app.core.hardware import detect_compute_device
from app.core.utils import utc_now, require_store, ok
from app.core.exceptions import NotFoundError, ValidationError
from app.security.rate_limiter import limiter, RATE_CHAT

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/completions")
@limiter.limit(RATE_CHAT)
async def chat_completions(
    request: Request,
    body: ChatRequest,
    adapter=Depends(get_llm_adapter),
    chat_service=Depends(get_chat_service),
    conversation_store=Depends(get_conversation_store),
):
    # Agent 集群调用递归守卫：防止 Agent A→B→A 无限循环
    if body.agent_depth > 3:
        raise HTTPException(
            status_code=400,
            detail="已达到最大 Agent 调用深度（3），无法继续递归调用",
        )

    result = await chat_service.handle_completions(body, adapter, conversation_store)
    if body.stream:
        return result
    if result["aborted"]:
        raise HTTPException(status_code=400, detail=result["content"].removeprefix("[Error] "))
    return ChatResponse(
        id=str(uuid.uuid4()),
        content=result["content"],
        model=result["model"],
        provider=result["provider"],
    )


@router.get("/conversations", response_model=list[ConversationListResponse])
async def list_conversations(
    agent_id: str | None = None,
    include_hidden: bool = Query(default=False, description="是否包含隐藏对话"),
    conversation_store=Depends(get_conversation_store),
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
async def search_conversations(
    keyword: str,
    agent_id: str | None = None,
    conversation_store=Depends(get_conversation_store),
):
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
async def create_conversation(
    request: ConversationCreate,
    conversation_store=Depends(get_conversation_store),
):
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
async def get_conversation(
    conv_id: str,
    limit: int = Query(100, ge=1, le=500, description="每次返回消息数上限"),
    before_id: str | None = Query(None, description="返回此消息之前的历史消息"),
    conversation_store=Depends(get_conversation_store),
):
    logger.info(f"[API] GET /chat/conversations/{conv_id} - Fetching conversation (limit={limit}, before_id={before_id})")
    conv = await conversation_store.get_paginated_async(conv_id, limit=limit, before_id=before_id)
    if not conv:
        logger.error(f"[API] GET /chat/conversations/{conv_id} - Conversation not found")
        raise NotFoundError(f"Conversation {conv_id} not found")
    msg_count = len(conv.get("messages", []))
    total = conv.get("total_messages", msg_count)
    logger.success(
        f"[API] GET /chat/conversations/{conv_id} - "
        f"Success: title={conv['title']}, messages={msg_count}/{total}, has_more={conv.get('has_more', False)}"
    )
    return ConversationResponse(**conv)


@router.post("/conversations/{conv_id}/leave")
async def leave_conversation(
    conv_id: str,
    adapter=Depends(get_llm_adapter),
    chat_service=Depends(get_chat_service),
    conversation_store=Depends(get_conversation_store),
):
    """用户离开/切换对话时触发最终蒸馏"""
    logger.info(f"[API] POST /chat/conversations/{conv_id}/leave")
    try:
        conv = await conversation_store.get_async(conv_id)
        await chat_service.trigger_final_distill(conv_id, conv, adapter)
    except Exception as distill_err:
        logger.warning(f"[API] Final distill on leave failed: {distill_err}")
    return ok({"left": True})


@router.delete("/conversations/{conv_id}")
async def delete_conversation(
    conv_id: str,
    adapter=Depends(get_llm_adapter),
    chat_service=Depends(get_chat_service),
    conversation_store=Depends(get_conversation_store),
):
    logger.info(f"[API] DELETE /chat/conversations/{conv_id} - Moving to trash")
    # 对话移到回收站前触发最终蒸馏
    try:
        conv = await conversation_store.get_async(conv_id)
        await chat_service.trigger_final_distill(conv_id, conv, adapter)
    except Exception as distill_err:
        logger.warning(f"[API] Final distill on delete failed: {distill_err}")

    await conversation_store.soft_delete_async(conv_id)
    logger.success(f"[API] DELETE /chat/conversations/{conv_id} - Moved to trash")
    return ok({"deleted": True})


class RenameConversationRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)


@router.patch("/conversations/{conv_id}/rename")
async def rename_conversation(
    conv_id: str,
    request: RenameConversationRequest,
    conversation_store=Depends(get_conversation_store),
):
    logger.info(f"[API] PATCH /chat/conversations/{conv_id}/rename - title_len={len(request.title)}")
    success = await conversation_store.rename_async(conv_id, request.title)
    if not success:
        raise NotFoundError(f"Conversation {conv_id} not found")
    logger.success(f"[API] PATCH /chat/conversations/{conv_id}/rename - Renamed")
    return ok({"renamed": True, "title": request.title})


class TruncateMessagesRequest(BaseModel):
    keep_count: int = Field(..., ge=0)


@router.patch("/conversations/{conv_id}/messages")
async def truncate_messages(
    conv_id: str,
    request: TruncateMessagesRequest,
    adapter=Depends(get_llm_adapter),
    chat_service=Depends(get_chat_service),
    conversation_store=Depends(get_conversation_store),
):
    logger.info(
        f"[API] PATCH /chat/conversations/{conv_id}/messages - "
        f"Truncating to {request.keep_count}"
    )
    conv = await require_store(conversation_store, conv_id, "Conversation")
    conv["messages"] = conv["messages"][:request.keep_count]
    await chat_service.persist_conv(conv_id, conv)

    # 截断的是尾部，重建对话级记忆
    agent_id = await chat_service.resolve_agent_id(conv)
    if agent_id:
        try:
            await chat_service.rebuild_conversation_memory(conv_id, conv, agent_id, adapter)
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
async def regenerate_message(
    conv_id: str,
    request: RegenerateRequest,
    adapter=Depends(get_llm_adapter),
    chat_service=Depends(get_chat_service),
    conversation_store=Depends(get_conversation_store),
):
    logger.info(f"[API] POST /chat/conversations/{conv_id}/regenerate")
    result = await chat_service.process_conversation_turn(
        conv_id, request, adapter, conversation_store, regenerate=True,
    )
    if request.stream:
        return result
    logger.success(f"[API] Regenerate done: conv={conv_id}")
    return ChatResponse(
        id=str(uuid.uuid4()),
        content=result["content"],
        model=result["model"],
        provider=result["provider"],
    )


@router.patch("/conversations/{conv_id}/messages/version")
async def update_message_version(
    conv_id: str,
    request: UpdateMessageVersionRequest,
    chat_service=Depends(get_chat_service),
    conversation_store=Depends(get_conversation_store),
):
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
            await chat_service.persist_conv(conv_id, conv)
            logger.success(
                f"[API] PATCH /chat/conversations/{conv_id}/messages/version - Version updated"
            )
            return ok({"updated": True})

    raise NotFoundError(f"Message {request.message_id} not found in conversation {conv_id}")


@router.delete("/conversations/{conv_id}/messages/{message_id}")
async def delete_message(
    conv_id: str,
    message_id: str,
    adapter=Depends(get_llm_adapter),
    chat_service=Depends(get_chat_service),
    conversation_store=Depends(get_conversation_store),
):
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
    await chat_service.persist_conv(conv_id, conv)

    # 删除用户消息时始终重建记忆，删除中间AI消息则跳过
    agent_id = await chat_service.resolve_agent_id(conv)
    if agent_id and conv["messages"]:
        if deleted_role == "user" or deleted_idx >= last_user_idx:
            try:
                await chat_service.rebuild_conversation_memory(conv_id, conv, agent_id, adapter)
            except Exception as mem_err:
                logger.warning(f"[Memory] Rebuild after delete failed: {mem_err}")
        else:
            logger.info("[Memory] Middle message deleted, tail unchanged — skip rebuild")

    logger.success(
        f"[API] DELETE /chat/conversations/{conv_id}/messages/{message_id} - Message deleted"
    )
    return ok({"deleted": True})


@router.post("/conversations/{conv_id}/messages")
@limiter.limit(RATE_CHAT)
async def add_message(
    request: Request,
    conv_id: str,
    body: ChatRequest,
    adapter=Depends(get_llm_adapter),
    chat_service=Depends(get_chat_service),
    conversation_store=Depends(get_conversation_store),
):
    logger.info(f"[API] POST /chat/conversations/{conv_id}/messages - Adding message")
    result = await chat_service.process_conversation_turn(
        conv_id, body, adapter, conversation_store,
    )
    if body.stream:
        return result
    return ChatResponse(
        id=str(uuid.uuid4()),
        content=result["content"],
        model=result["model"],
        provider=result["provider"],
    )


@router.get("/trash", response_model=list[TrashListItemResponse])
async def list_trash(
    agent_id: str | None = None,
    conversation_store=Depends(get_conversation_store),
):
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
async def restore_conversation(
    conv_id: str,
    conversation_store=Depends(get_conversation_store),
):
    logger.info(f"[API] POST /chat/trash/{conv_id}/restore - Restoring conversation")
    restored = await conversation_store.restore_async(conv_id)
    if not restored:
        logger.warning(f"[API] POST /chat/trash/{conv_id}/restore - Restore failed, not found")
        return {"error": "not found", "data": {"restored": False}}
    logger.success(f"[API] POST /chat/trash/{conv_id}/restore - Restored")
    return ok({"restored": True})


@router.delete("/trash/{conv_id}")
async def permanent_delete_conversation(
    conv_id: str,
    conversation_store=Depends(get_conversation_store),
):
    logger.info(f"[API] DELETE /chat/trash/{conv_id} - Permanent deleting conversation")
    deleted = await conversation_store.permanent_delete_async(conv_id)
    if not deleted:
        logger.warning(f"[API] DELETE /chat/trash/{conv_id} - Delete failed, not found")
        return {"error": "not found", "data": {"deleted": False}}
    logger.success(f"[API] DELETE /chat/trash/{conv_id} - Permanently deleted")
    return ok({"deleted": True})


@router.delete("/trash")
async def empty_trash(
    agent_id: str | None = None,
    conversation_store=Depends(get_conversation_store),
):
    logger.info(f"[API] DELETE /chat/trash - Emptying trash, agent_id={agent_id}")
    count = await conversation_store.empty_trash_async(agent_id)
    logger.success(f"[API] DELETE /chat/trash - Emptied {count} items")
    return ok({"deleted_count": count})


@router.post("/trash/batch-restore")
async def batch_restore(
    request: BatchIdsRequest,
    conversation_store=Depends(get_conversation_store),
):
    logger.info(f"[API] POST /chat/trash/batch-restore - Restoring {len(request.ids)} items")
    count = await conversation_store.batch_restore_async(request.ids)
    logger.success(f"[API] POST /chat/trash/batch-restore - Restored {count} items")
    return ok({"restored_count": count})


@router.post("/trash/batch-delete")
async def batch_permanent_delete(
    request: BatchIdsRequest,
    conversation_store=Depends(get_conversation_store),
):
    logger.info(f"[API] POST /chat/trash/batch-delete - Deleting {len(request.ids)} items")
    count = await conversation_store.batch_permanent_delete_async(request.ids)
    logger.success(f"[API] POST /chat/trash/batch-delete - Deleted {count} items")
    return ok({"deleted_count": count})


@router.post("/conversations/batch-delete")
async def batch_soft_delete(
    request: BatchIdsRequest,
    adapter=Depends(get_llm_adapter),
    chat_service=Depends(get_chat_service),
    conversation_store=Depends(get_conversation_store),
):
    logger.info(f"[API] POST /chat/conversations/batch-delete - Moving {len(request.ids)} to trash")

    # 为每个对话触发最终蒸馏（与单个删除行为对齐）
    for conv_id in request.ids:
        try:
            conv = await conversation_store.get_async(conv_id)
            await chat_service.trigger_final_distill(conv_id, conv, adapter)
        except Exception as distill_err:
            logger.warning(f"[Memory] Final distill on batch delete failed for {conv_id}: {distill_err}")

    count = await conversation_store.batch_soft_delete_async(request.ids)
    logger.success(f"[API] POST /chat/conversations/batch-delete - Moved {count} to trash")
    return ok({"deleted_count": count})


@router.post("/conversations/{conv_id}/compress")
async def compress_conversation(
    conv_id: str,
    adapter=Depends(get_llm_adapter),
    chat_service=Depends(get_chat_service),
    conversation_store=Depends(get_conversation_store),
):
    """手动压缩对话上下文。"""
    logger.info(f"[API] POST /chat/conversations/{conv_id}/compress - Compressing conversation")
    conv = await require_store(conversation_store, conv_id, "Conversation")
    result = await chat_service.compress_conversation(conv_id, conv, adapter)
    logger.success(
        f"[API] POST /chat/conversations/{conv_id}/compress - "
        f"Done: {result['tokens_before']} -> {result['tokens_after']} tokens"
    )
    return ok({
        "compressed": True,
        "tokens_before": result["tokens_before"],
        "tokens_after": result["tokens_after"],
    })


class TTSRequest(BaseModel):
    text: str = Field(..., max_length=2000)
    voice: str = Field(default="default")
    engine: str = Field(default="auto")
    model: str = Field(default="")
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    apiKey: str = Field(default="", max_length=500)
    baseUrl: str = Field(default="", pattern=r"^$|^https?://.*")

    @field_validator("baseUrl")
    @classmethod
    def _validate_base_url(cls, v: str) -> str:
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("baseUrl 必须是有效的 HTTP/HTTPS URL")
        return v


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

    device = detect_compute_device()

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

def _get_stt_provider(engine_id: str | None = None):
    """根据引擎 ID 获取 STT Provider，支持自动降级.

    Args:
        engine_id: 用户指定的引擎 ID，None 时按优先级自动选择

    Returns:
        (provider, engine_id) 元组

    Raises:
        RuntimeError: 所有引擎都不可用
    """
    # 触发 STT 引擎注册（import 包即注册）
    import app.runtime.provider.stt  # noqa: F401
    from app.runtime.provider.stt.stt_registry import LuomiNestSTTRegistry

    # 通过注册表解析引擎，支持自动降级（降级顺序见 STT_FALLBACK_ORDER）
    return LuomiNestSTTRegistry.resolve(engine_id)


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
    from app.runtime.provider.stt.stt_registry import STT_FALLBACK_ORDER

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
            "fallback_order": STT_FALLBACK_ORDER,
            "device": detect_compute_device(),
        },
    }
