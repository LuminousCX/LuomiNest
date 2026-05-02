from pydantic import BaseModel, Field
from typing import Any


class ChatMessageCreate(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessageCreate]
    model: str | None = None
    provider: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    stream: bool = False
    agent_id: str | None = None


class ChatResponse(BaseModel):
    id: str
    content: str
    model: str
    provider: str
    usage: dict[str, int] | None = None


class ChatStreamChunk(BaseModel):
    id: str
    content: str
    model: str
    provider: str
    done: bool = False


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
