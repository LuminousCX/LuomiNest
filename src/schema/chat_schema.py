"""对话交互相关请求/响应参数校验模型。"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from src.model.conversation import ResponseMode


class ChatRequest(BaseModel):
    """对话请求。"""

    content: str = Field(..., min_length=1, max_length=5000, description="用户输入内容")
    conversation_id: Optional[str] = Field(default=None, description="对话会话ID，为空则创建新会话")
    agent_id: Optional[int] = Field(default=None, description="Agent 角色ID，为空则使用当前角色")
    mode: ResponseMode = Field(default=ResponseMode.FAST, description="响应模式")
    stream: bool = Field(default=True, description="是否流式输出")


class MultimodalChatRequest(BaseModel):
    """多模态对话请求。"""

    content: str = Field(default="", max_length=5000, description="用户输入内容")
    conversation_id: Optional[str] = Field(default=None, description="对话会话ID")
    agent_id: Optional[int] = Field(default=None, description="Agent 角色ID")
    mode: ResponseMode = Field(default=ResponseMode.FAST, description="响应模式")
    stream: bool = Field(default=True, description="是否流式输出")
    file_ids: list[str] = Field(default_factory=list, description="已上传文件的ID列表")
    multimodal_messages: list[dict[str, Any]] = Field(
        default_factory=list,
        description="多模态消息列表（OpenAI格式）",
    )


class ChatResponse(BaseModel):
    """对话响应。"""

    conversation_id: str = Field(description="对话会话ID")
    message_id: str = Field(description="消息ID")
    content: str = Field(default="", description="AI 回复内容")
    tokens: int = Field(default=0, description="本次消耗 token 数")
    total_tokens: int = Field(default=0, description="会话总消耗 token 数")
    mode: ResponseMode = Field(default=ResponseMode.FAST, description="当前响应模式")


class ConversationListResponse(BaseModel):
    """对话会话列表响应。"""

    conversations: list[dict] = Field(default_factory=list, description="会话列表")
    total: int = Field(default=0, description="总数")


class ConversationDetailResponse(BaseModel):
    """对话会话详情响应。"""

    id: str = Field(description="会话ID")
    agent_id: str = Field(description="Agent 角色ID")
    title: str = Field(default="新对话", description="会话标题")
    mode: ResponseMode = Field(default=ResponseMode.FAST, description="响应模式")
    messages: list[dict] = Field(default_factory=list, description="消息列表")
    total_tokens: int = Field(default=0, description="总消耗 token 数")
    created_at: str = Field(default="", description="创建时间")
    updated_at: str = Field(default="", description="更新时间")


class ModeSwitchRequest(BaseModel):
    """模式切换请求。"""

    conversation_id: str = Field(..., min_length=1, description="对话会话ID")
    mode: ResponseMode = Field(..., description="目标响应模式")


class TokenUsageResponse(BaseModel):
    """Token 用量响应。"""

    total_budget: int = Field(description="总预算 token 数")
    used_tokens: int = Field(description="已使用 token 数")
    remaining_tokens: int = Field(description="剩余 token 数")
    usage_ratio: float = Field(description="已用比例")
    remaining_ratio: float = Field(description="剩余比例")
