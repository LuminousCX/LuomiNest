"""对话交互 API 路由。

提供对话发送、历史记录、模式切换、Token 用量等接口。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from typing_extensions import Annotated

from src.model.conversation import ResponseMode
from src.schema.chat_schema import (
    ChatRequest,
    ChatResponse,
    ConversationDetailResponse,
    ConversationListResponse,
    ModeSwitchRequest,
    MultimodalChatRequest,
    TokenUsageResponse,
)
from src.schema.common_schema import ApiResponse
from src.service.chat_service import ChatService
from src.utils.datetime_utils import format_datetime
from src.utils.logger import get_logger

logger = get_logger()

router = APIRouter(prefix="/chat", tags=["对话交互"])


def get_chat_service() -> ChatService:
    """获取 ChatService 实例（依赖注入）。"""
    from src.api.deps import get_services
    return get_services()["chat_service"]


@router.post("/send", summary="发送对话（非流式）")
async def send_chat(
    request: ChatRequest,
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
) -> ApiResponse[ChatResponse]:
    """发送对话消息并获取 AI 回复（非流式）。"""
    request.stream = False
    response = await chat_service.chat(request)
    return ApiResponse.success(data=response)


@router.post("/stream", summary="发送对话（流式）")
async def stream_chat(
    request: ChatRequest,
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
) -> StreamingResponse:
    """发送对话消息并获取 AI 流式回复。"""
    request.stream = True

    async def event_generator():
        try:
            async for chunk in chat_service.chat_stream(request):
                yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"Stream chat error: {e}")
            yield f"data: [ERROR] {str(e)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/multimodal", summary="多模态对话（非流式）")
async def multimodal_chat(
    request: MultimodalChatRequest,
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
) -> ApiResponse[ChatResponse]:
    """发送多模态对话消息（支持图片、文档）。

    前端只需传递 agent_id，后端自动渲染 system prompt。
    通过 file_ids 或 multimodal_messages 传递多模态内容。
    """
    request.stream = False
    response = await chat_service.multimodal_chat(request)
    return ApiResponse.success(data=response)


@router.get("/conversations", summary="获取对话列表")
async def list_conversations(
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    agent_id: str | None = None,
    limit: int = 50,
) -> ApiResponse[ConversationListResponse]:
    """获取对话会话列表。"""
    conversations = chat_service.get_conversation_list(agent_id, limit)
    conv_list = []
    for conv in conversations:
        conv_list.append({
            "id": conv.id,
            "agent_id": conv.agent_id,
            "title": conv.title,
            "mode": conv.mode.value,
            "total_tokens": conv.total_tokens,
            "created_at": format_datetime(conv.created_at),
            "updated_at": format_datetime(conv.updated_at),
        })
    data = ConversationListResponse(conversations=conv_list, total=len(conv_list))
    return ApiResponse.success(data=data)


@router.get("/conversations/{conversation_id}", summary="获取对话详情")
async def get_conversation(
    conversation_id: str,
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
) -> ApiResponse[ConversationDetailResponse]:
    """获取对话会话详情（含所有消息）。"""
    conversation = chat_service.get_conversation_history(conversation_id)
    if conversation is None:
        return ApiResponse.error(code=50001, message="对话会话不存在")

    messages = []
    for msg in conversation.messages:
        messages.append({
            "id": msg.id,
            "role": msg.role.value,
            "content": msg.content,
            "tokens": msg.tokens,
            "created_at": format_datetime(msg.created_at),
        })

    data = ConversationDetailResponse(
        id=conversation.id,
        agent_id=conversation.agent_id,
        title=conversation.title,
        mode=conversation.mode,
        messages=messages,
        total_tokens=conversation.total_tokens,
        created_at=format_datetime(conversation.created_at),
        updated_at=format_datetime(conversation.updated_at),
    )
    return ApiResponse.success(data=data)


@router.delete("/conversations/{conversation_id}", summary="删除对话")
async def delete_conversation(
    conversation_id: str,
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
) -> ApiResponse[None]:
    """删除对话会话及其所有消息。"""
    chat_service.delete_conversation(conversation_id)
    return ApiResponse.success(message="删除成功")


@router.post("/mode", summary="切换对话模式")
async def switch_mode(
    request: ModeSwitchRequest,
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
) -> ApiResponse[None]:
    """切换对话的响应模式（专家/快速）。"""
    chat_service.switch_mode(request.conversation_id, request.mode)
    return ApiResponse.success(message=f"已切换为{request.mode.value}模式")


@router.get("/token-usage", summary="获取 Token 用量")
async def get_token_usage(
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
) -> ApiResponse[TokenUsageResponse]:
    """获取 Token 用量统计。"""
    usage = chat_service.get_token_usage()
    data = TokenUsageResponse(**usage)
    return ApiResponse.success(data=data)
