from pydantic import BaseModel, Field, field_validator
from typing import Any, Literal


class ChatMessageCreate(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessageCreate]
    model: str | None = None
    provider: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=128_000)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    stream: bool = False
    agent_id: str | None = None
    conversation_id: str | None = None
    timestamp: float | None = None
    file_content: str | None = Field(default=None, max_length=100_000_000)
    file_name: str | None = Field(default=None, max_length=255)
    file_type: Literal[
        "text", "image",
        "text/plain", "image/png", "image/jpeg", "image/gif", "image/webp",
        "application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ] | None = None
    search_results: str | None = Field(default=None, max_length=100_000)
    versions: list[dict[str, Any]] | None = None
    # Agent 集群调用内部字段（不暴露前端，仅供 agent_tool_call 递归守卫使用）
    is_sub_agent: bool = False
    disable_tools: list[str] | None = None
    agent_depth: int = 0


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
    suggested_questions: list[str] | None = None
    emotion: str | None = None
    # 工具调用相关字段（主 Agent 工具调用循环）
    tool_calls: list[dict[str, Any]] | None = None
    tool_event: dict[str, Any] | None = None
    iteration: int = 0
    # 子 Agent 群组事件（主 Agent 通过 delegate_to_subagent 工具委派子任务时推送）
    subagent_event: dict[str, Any] | None = None
    # 定时任务事件（主 Agent 通过 create_scheduled_task 工具创建任务时推送）
    task_event: dict[str, Any] | None = None

    @field_validator("content", "reasoning_content", mode="before")
    @classmethod
    def coerce_str(cls, v: str | None) -> str:
        return v if isinstance(v, str) else ""


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


class ConversationSearchResult(BaseModel):
    id: str
    title: str
    snippet: str
    updated_at: str


class TrashListItemResponse(ConversationListResponse):
    deleted_at: str


class BatchIdsRequest(BaseModel):
    ids: list[str] = Field(..., min_length=1)
