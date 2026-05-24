from pydantic import BaseModel, Field
from typing import Any, Literal


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
    timestamp: float | None = None
    file_content: str | None = Field(default=None, max_length=100_000_000)
    file_name: str | None = Field(default=None, max_length=255)
    file_type: Literal[
        "text", "image",
        "text/plain", "image/png", "image/jpeg", "image/gif", "image/webp",
        "application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ] | None = None
    search_results: str | None = Field(default=None, max_length=100_000)


class ChatResponse(BaseModel):
    id: str
    content: str
    model: str
    provider: str
    usage: dict[str, int] | None = None


class ChatStreamChunk(BaseModel):
    id: str
    content: str = ""
    reasoning_content: str = ""
    model: str
    provider: str
    done: bool = False

    @classmethod
    def _coerce_str(cls, v: str | None) -> str:
        return v if isinstance(v, str) else ""

    def __init__(self, **data: Any) -> None:
        data["content"] = self._coerce_str(data.get("content"))
        data["reasoning_content"] = self._coerce_str(data.get("reasoning_content"))
        super().__init__(**data)


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
