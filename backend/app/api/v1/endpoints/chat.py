import uuid
import json
from fastapi import APIRouter, Request
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

router = APIRouter(prefix="/chat", tags=["chat"])

_conversations: dict[str, dict] = {}


@router.post("/completions")
async def chat_completions(request: ChatRequest):
    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    if request.stream:
        return StreamingResponse(
            _stream_chat(messages, request),
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
            provider_name=request.provider,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            top_p=request.top_p,
            tools=request.tools,
        )
        return ChatResponse(
            id=str(uuid.uuid4()),
            content=result,
            model=request.model or llm_adapter.get_provider(request.provider).default_model,
            provider=request.provider or llm_adapter.default_provider,
        )
    except Exception as e:
        logger.error(f"Chat completion failed: {e}")
        raise


async def _stream_chat(messages: list[dict], request: ChatRequest):
    chat_id = str(uuid.uuid4())
    model = request.model or llm_adapter.get_provider(request.provider).default_model
    provider = request.provider or llm_adapter.default_provider

    try:
        async for chunk in llm_adapter.chat_stream(
            messages=messages,
            provider_name=request.provider,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            top_p=request.top_p,
            tools=request.tools,
        ):
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
    except Exception as e:
        logger.error(f"Stream chat failed: {e}")
        error_data = ChatStreamChunk(
            id=chat_id,
            content=f"[Error] {str(e)}",
            model=model,
            provider=provider,
            done=True,
        )
        yield f"data: {error_data.model_dump_json()}\n\n"


@router.get("/conversations", response_model=list[ConversationListResponse])
async def list_conversations():
    result = []
    for conv_id, conv in _conversations.items():
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
    return result


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(request: ConversationCreate):
    from datetime import datetime, timezone
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
    _conversations[conv_id] = conv
    return ConversationResponse(**conv)


@router.get("/conversations/{conv_id}", response_model=ConversationResponse)
async def get_conversation(conv_id: str):
    conv = _conversations.get(conv_id)
    if not conv:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Conversation {conv_id} not found")
    return ConversationResponse(**conv)


@router.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: str):
    if conv_id in _conversations:
        del _conversations[conv_id]
    return {"data": {"deleted": True}}


@router.post("/conversations/{conv_id}/messages")
async def add_message(conv_id: str, request: ChatRequest):
    conv = _conversations.get(conv_id)
    if not conv:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Conversation {conv_id} not found")

    from datetime import datetime, timezone
    for m in request.messages:
        conv["messages"].append({"role": m.role, "content": m.content})
    conv["updated_at"] = datetime.now(timezone.utc).isoformat()

    all_messages = [{"role": m["role"], "content": m["content"]} for m in conv["messages"]]

    if request.stream:
        return StreamingResponse(
            _stream_chat(all_messages, request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    result = await llm_adapter.chat(
        messages=all_messages,
        provider_name=request.provider or conv.get("provider"),
        model=request.model or conv.get("model"),
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        top_p=request.top_p,
        tools=request.tools,
    )

    conv["messages"].append({"role": "assistant", "content": result})
    conv["updated_at"] = datetime.now(timezone.utc).isoformat()

    return ChatResponse(
        id=str(uuid.uuid4()),
        content=result,
        model=request.model or conv.get("model", ""),
        provider=request.provider or conv.get("provider", ""),
    )
