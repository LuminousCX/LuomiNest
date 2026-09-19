from pydantic import BaseModel, Field, field_validator
from typing import Any, Literal


class ChatMessageCreate(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str = Field(..., max_length=65536)  # 文本长度上限（审计 B4-4）


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
    # 用户本次请求显式选择的技能 ID（优先于关键词自动匹配注入）
    skill_ids: list[str] | None = None
    # Agent 集群调用内部字段（不暴露前端，仅供 agent_tool_call 递归守卫使用）
    is_sub_agent: bool = False
    # 父会话透传（Agent 集群委派时由 agent_tool 携带）：
    # 子 Agent 的命令确认会话授权按主对话 conv_id 判定
    parent_conv_id: str | None = Field(default=None, max_length=64)
    disable_tools: list[str] | None = None
    agent_depth: int = 0


class ChatResponse(BaseModel):
    id: str
    content: str
    model: str
    provider: str
    usage: dict[str, int] | None = None
    # 云链路业务错误码（数字字符串，如 "13005"；无业务码为 null）。
    # 非流式业务错误随 200 响应携带（content 以 "[Error] " 开头），前端映射本地化文案
    errCode: str | None = None


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
    # 命令执行确认请求（PermissionGate：{request_id, tool, command, timeout}，
    # 前端弹三档确认窗后 POST /chat/tool-permission/{request_id} 回调）
    permission_request: dict[str, Any] | None = None
    # 压缩后上下文 token 数（done 时回填）
    context_tokens: int | None = None
    # 上下文窗口容量（done 时回填，前端用于计算使用百分比）
    context_max_tokens: int | None = None
    # 模型路由通知（如专业模式推理模型退化为主模型，前端右上角 toast 展示）
    notice: str | None = None
    # 云链路业务错误码（数字字符串，如 "13005"；无业务码为 null）。
    # 出现在错误 chunk 上，前端按 errCode 映射本地化文案（message 为人类可读兜底）
    errCode: str | None = None

    @field_validator("content", "reasoning_content", mode="before")
    @classmethod
    def coerce_str(cls, v: str | None) -> str:
        return v if isinstance(v, str) else ""


class ConversationCreate(BaseModel):
    title: str | None = None
    agent_id: str | None = None
    model: str | None = None
    provider: str | None = None
    chat_mode: str | None = None
    is_hidden: bool = False
    # 对话域字段（洋葱架构 §5.2，B3 创建时写入；缺省按 agent_id 推导）
    domain: str | None = None
    scene: str | None = None


class ConversationResponse(BaseModel):
    id: str
    title: str
    agent_id: str | None = None
    model: str | None = None
    provider: str | None = None
    chat_mode: str | None = None
    is_hidden: bool = False
    # 对话域字段（洋葱架构 §5.2，新增只增不改，老客户端忽略即可）
    domain: str = ""
    scene: str = "workbench"
    user_key: str = ""
    messages: list[dict[str, Any]] = []
    created_at: str
    updated_at: str
    has_more: bool | None = None
    total_messages: int | None = None


class ConversationListResponse(BaseModel):
    id: str
    title: str
    agent_id: str | None = None
    model: str | None = None
    provider: str | None = None
    chat_mode: str | None = None
    is_hidden: bool = False
    # 对话域字段（洋葱架构 §5.2，新增只增不改，老客户端忽略即可）
    domain: str = ""
    scene: str = "workbench"
    user_key: str = ""
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
    # 上限 100：batch-delete 会对每个 id 触发一次 LLM final distill，
    # 无上限时可放大为任意次 LLM 调用（审计 B4-4）
    ids: list[str] = Field(..., min_length=1, max_length=100)
