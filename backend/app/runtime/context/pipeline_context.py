from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


@dataclass
class Message:
    role: MessageRole
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class UserContext:
    user_id: str = ""
    session_id: str = ""
    permissions: list[str] = field(default_factory=list)
    preferences: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    text: str = ""
    emotion: str = "neutral"
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineContext:
    raw_input: str = ""
    messages: list[Message] = field(default_factory=list)
    user_context: Optional[UserContext] = None
    intent: str = ""
    matched_agent: Optional[Any] = None
    agent_result: Optional[AgentResult] = None
    should_stop: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def add_message(self, role: MessageRole, content: str, **metadata: Any) -> None:
        self.messages.append(Message(role=role, content=content, metadata=metadata))
