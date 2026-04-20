from dataclasses import dataclass, field
from typing import Any, Optional
from datetime import datetime
from enum import Enum


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


@dataclass
class Message:
    role: MessageRole
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class UserContext:
    user_id: str
    username: str
    session_id: str
    device_id: Optional[str] = None
    location: Optional[str] = None
    permissions: list[str] = field(default_factory=list)


@dataclass
class AgentResult:
    text: str = ""
    actions: list[dict[str, Any]] = field(default_factory=list)
    emotion: str = "neutral"
    avatar_expression: str = "normal"
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineContext:
    messages: list[Message] = field(default_factory=list)
    user_context: Optional[UserContext] = None
    agent_result: Optional[AgentResult] = None
    raw_input: str = ""
    intent: str = ""
    matched_agent: Optional[str] = None
    memory_recall: list[dict] = field(default_factory=list)
    tool_results: list[dict] = field(default_factory=list)
    emotion_analysis: dict[str, Any] = field(default_factory=dict)
    should_stop: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def add_message(self, role: MessageRole, content: str, **kwargs) -> None:
        self.messages.append(Message(role=role, content=content, **kwargs))
