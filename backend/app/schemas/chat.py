from pydantic import BaseModel, Field
from typing import Any
from datetime import datetime, timezone


class ChatMessageCreate(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system|tool)$")
    content: str | list[dict[str, Any]] = ""
    name: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None
    timestamp: float | None = None


class ToolCallFunction(BaseModel):
    name: str
    arguments: str


class ToolCallInfo(BaseModel):
    id: str
    type: str = "function"
    function: ToolCallFunction


class ChatRequest(BaseModel):
    messages: list[ChatMessageCreate]
    model: str | None = None
    provider: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    stream: bool = False
    agent_id: str | None = None
    tools: list[dict[str, Any]] | None = None
    timestamp: float | None = None


class ToolCallResult(BaseModel):
    tool_call_id: str
    tool_name: str
    result: str
    status: str = "success"


class ChatResponse(BaseModel):
    id: str
    content: str | None = None
    model: str
    provider: str
    tool_calls: list[ToolCallInfo] | None = None
    tool_results: list[ToolCallResult] | None = None
    usage: dict[str, int] | None = None
    timestamp: float | None = None


class ChatStreamChunk(BaseModel):
    id: str
    content: str = ""
    model: str
    provider: str
    done: bool = False
    tool_calls: list[dict[str, Any]] | None = None
    tool_results: list[ToolCallResult] | None = None
    usage: dict[str, int] | None = None
    timestamp: float | None = None


class ConversationCreate(BaseModel):
    title: str | None = None
    agent_id: str | None = None
    model: str | None = None
    provider: str | None = None


class ConversationResponse(BaseModel):
    id: str
    title: str
    agent_id: str | None = None
    model: str | None = None
    provider: str | None = None
    messages: list[dict[str, Any]] = []
    created_at: str
    updated_at: str


class ConversationListResponse(BaseModel):
    id: str
    title: str
    agent_id: str | None = None
    model: str | None = None
    provider: str | None = None
    last_message: str | None = None
    created_at: str
    updated_at: str
