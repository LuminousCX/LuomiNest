import uuid
from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, Field


def utc_now_iso_z() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


FactCategory = Literal[
    "preference",
    "knowledge", 
    "context",
    "behavior",
    "goal",
    "correction",
]


class MemoryFact(BaseModel):
    id: str = Field(default_factory=lambda: f"fact_{uuid.uuid4().hex[:8]}")
    content: str
    category: FactCategory = "context"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    created_at: str = Field(default_factory=utc_now_iso_z)
    source: str = "unknown"
    source_error: str | None = None


class UserContextSection(BaseModel):
    summary: str = ""
    updated_at: str = ""


class UserContext(BaseModel):
    work_context: UserContextSection = Field(default_factory=UserContextSection)
    personal_context: UserContextSection = Field(default_factory=UserContextSection)
    top_of_mind: UserContextSection = Field(default_factory=UserContextSection)


class HistorySection(BaseModel):
    summary: str = ""
    updated_at: str = ""


class History(BaseModel):
    recent_months: HistorySection = Field(default_factory=HistorySection)
    earlier_context: HistorySection = Field(default_factory=HistorySection)
    long_term_background: HistorySection = Field(default_factory=HistorySection)


class UserProfile(BaseModel):
    name: str = ""
    nickname: str = ""
    age: str = ""
    gender: str = ""
    occupation: str = ""
    location: str = ""
    timezone: str = ""
    language: str = ""
    interests: list[str] = Field(default_factory=list)
    hobbies: list[str] = Field(default_factory=list)
    preferences: dict[str, str] = Field(default_factory=dict)
    notes: str = ""
    updated_at: str = ""


class MemoryData(BaseModel):
    version: str = "1.1"
    last_updated: str = Field(default_factory=utc_now_iso_z)
    user: UserContext = Field(default_factory=UserContext)
    history: History = Field(default_factory=History)
    facts: list[MemoryFact] = Field(default_factory=list)
    profile: UserProfile = Field(default_factory=UserProfile)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryData":
        if "profile" not in data:
            data["profile"] = {}
        return cls.model_validate(data)


def create_empty_memory() -> MemoryData:
    return MemoryData()
