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


MemoryTier = Literal[
    "core_identity",
    "long_term_preference",
    "temporary_context",
]


class MemoryFact(BaseModel):
    id: str = Field(default_factory=lambda: f"fact_{uuid.uuid4().hex[:8]}")
    content: str
    category: FactCategory = "context"
    tier: MemoryTier = "temporary_context"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    last_accessed_at: str = Field(default_factory=utc_now_iso_z)
    access_count: int = 0
    decay_days: int = 30
    created_at: str = Field(default_factory=utc_now_iso_z)
    source: str = "unknown"
    source_error: str | None = None
    
    def should_archive(self, current_time_str: str) -> bool:
        try:
            current = datetime.fromisoformat(current_time_str.replace("Z", "+00:00"))
            created = datetime.fromisoformat(self.created_at.replace("Z", "+00:00"))
            days_since = (current - created).days
            return days_since > self.decay_days
        except:
            return False
    
    def record_access(self):
        self.access_count += 1
        self.last_accessed_at = utc_now_iso_z()


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


class WorkingMemory(BaseModel):
    core_goal: str = ""
    core_goal_extracted_at: str = ""
    recent_conversations: list[dict] = Field(default_factory=list)
    conversation_summary: str = ""
    current_state: str = "idle"
    last_updated: str = Field(default_factory=utc_now_iso_z)
    
    def add_conversation(self, role: str, content: str):
        self.recent_conversations.append({
            "role": role,
            "content": content,
            "timestamp": utc_now_iso_z()
        })
        self.recent_conversations = self.recent_conversations[-10:]
        self.last_updated = utc_now_iso_z()
    
    def set_core_goal(self, goal: str):
        self.core_goal = goal
        self.core_goal_extracted_at = utc_now_iso_z()
        self.last_updated = utc_now_iso_z()


class EpisodicEvent(BaseModel):
    id: str = Field(default_factory=lambda: f"event_{uuid.uuid4().hex[:8]}")
    timestamp: str = Field(default_factory=utc_now_iso_z)
    conversation_id: str = ""
    agent_id: str = ""
    scene_tags: list[str] = Field(default_factory=list)
    core_goal: str = ""
    key_information: str = ""
    final_result: str = ""
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    
    def matches_query(self, query: str) -> bool:
        query_lower = query.lower()
        return any(
            tag.lower() in query_lower 
            or query_lower in tag.lower()
            for tag in self.scene_tags
        ) or (
            query_lower in self.core_goal.lower() 
            or query_lower in self.key_information.lower()
        )


class MemoryData(BaseModel):
    version: str = "2.0"
    last_updated: str = Field(default_factory=utc_now_iso_z)
    user: UserContext = Field(default_factory=UserContext)
    history: History = Field(default_factory=History)
    facts: list[MemoryFact] = Field(default_factory=list)
    profile: UserProfile = Field(default_factory=UserProfile)
    working_memory: WorkingMemory = Field(default_factory=WorkingMemory)
    episodic_events: list[EpisodicEvent] = Field(default_factory=list)
    archived_facts: list[MemoryFact] = Field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryData":
        if "profile" not in data:
            data["profile"] = {}
        if "working_memory" not in data:
            data["working_memory"] = {}
        if "episodic_events" not in data:
            data["episodic_events"] = []
        if "archived_facts" not in data:
            data["archived_facts"] = []
        return cls.model_validate(data)
    
    def get_facts_by_tier(self, tier: MemoryTier) -> list[MemoryFact]:
        return [f for f in self.facts if f.tier == tier]
    
    def archive_expired_facts(self):
        current_time = utc_now_iso_z()
        active_facts = []
        for fact in self.facts:
            if fact.tier == "core_identity":
                active_facts.append(fact)
            elif not fact.should_archive(current_time):
                active_facts.append(fact)
            else:
                self.archived_facts.append(fact)
        self.facts = active_facts


def create_empty_memory() -> MemoryData:
    return MemoryData()
