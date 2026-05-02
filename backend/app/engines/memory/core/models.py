import uuid
import re
from datetime import datetime, timezone
from typing import Any, Literal
from loguru import logger
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

TIER_DECAY_DAYS: dict[MemoryTier, int] = {
    "core_identity": 0,
    "long_term_preference": 365,
    "temporary_context": 30,
}

TIER_DEFAULT_CONFIDENCE: dict[MemoryTier, float] = {
    "core_identity": 1.0,
    "long_term_preference": 0.7,
    "temporary_context": 0.5,
}


class MemoryFact(BaseModel):
    id: str = Field(default_factory=lambda: f"fact_{uuid.uuid4().hex[:8]}")
    content: str
    category: FactCategory = "context"
    tier: MemoryTier = "temporary_context"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    last_accessed_at: str = Field(default_factory=utc_now_iso_z)
    access_count: int = 0
    decay_days: int = 0
    created_at: str = Field(default_factory=utc_now_iso_z)
    source: str = "unknown"
    source_error: str | None = None

    def model_post_init(self, __context: Any) -> None:
        if self.decay_days == 0:
            self.decay_days = TIER_DECAY_DAYS.get(self.tier, 30)

    def should_archive(self, current_time_str: str) -> bool:
        if self.tier == "core_identity":
            return False
        try:
            current = datetime.fromisoformat(current_time_str.replace("Z", "+00:00"))
            last_accessed = datetime.fromisoformat(self.last_accessed_at.replace("Z", "+00:00"))
            days_since_access = (current - last_accessed).days
            return days_since_access > self.decay_days
        except (ValueError, TypeError, AttributeError, OverflowError):
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
        self.recent_conversations = self.recent_conversations[-20:]
        self.last_updated = utc_now_iso_z()

    def set_core_goal(self, goal: str):
        self.core_goal = goal
        self.core_goal_extracted_at = utc_now_iso_z()
        self.last_updated = utc_now_iso_z()

    def get_recent_full(self, n: int = 5) -> list[dict]:
        return self.recent_conversations[-n:] if self.recent_conversations else []

    def get_older_summarized(self, skip_last: int = 5) -> list[dict]:
        if len(self.recent_conversations) <= skip_last:
            return []
        return self.recent_conversations[:-skip_last]


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
        tag_match = any(
            tag.lower() in query_lower or query_lower in tag.lower()
            for tag in self.scene_tags
        )
        content_match = (
            query_lower in self.core_goal.lower()
            or query_lower in self.key_information.lower()
        )
        return tag_match or content_match

    def time_distance_days(self) -> int:
        try:
            created = datetime.fromisoformat(self.timestamp.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            return (now - created).days
        except (ValueError, TypeError) as e:
            logger.debug(f"[Memory] Failed to parse timestamp in time_distance_days: {e}")
            return 9999


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
            if fact.should_archive(current_time):
                self.archived_facts.append(fact)
            else:
                active_facts.append(fact)
        self.facts = active_facts

    def resolve_conflicts(self, new_fact: MemoryFact) -> list[str]:
        removed_ids = []
        if new_fact.category != "correction":
            return removed_ids
        new_lower = new_fact.content.lower()
        surviving = []
        for existing in self.facts:
            if existing.id == new_fact.id:
                surviving.append(existing)
                continue
            if existing.tier == new_fact.tier and self._facts_conflict(existing.content, new_lower):
                self.archived_facts.append(existing)
                removed_ids.append(existing.id)
            else:
                surviving.append(existing)
        self.facts = surviving
        return removed_ids

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return set(re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]{2,}', text.lower()))

    @staticmethod
    def _has_negation(words: set[str]) -> bool:
        negation_words = {
            "not", "no", "never", "neither", "nor", "nobody", "nothing",
            "nowhere", "hardly", "barely", "scarcely",
            "不", "没", "没有", "非", "无", "未", "别", "莫", "勿",
            "dislike", "hate", "avoid", "refuse", "reject",
            "不喜欢", "讨厌", "拒绝",
        }
        return bool(words & negation_words)

    @staticmethod
    def _get_value_words(text: str) -> set[str]:
        stop_words = {
            "user", "the", "a", "an", "is", "are", "was", "were", "be",
            "been", "being", "has", "have", "had", "do", "does", "did",
            "will", "would", "shall", "should", "may", "might", "can",
            "could", "must", "of", "in", "on", "at", "to", "for", "with",
            "by", "from", "as", "into", "about", "also", "and",
            "but", "or", "not", "no", "very", "just", "than", "that",
            "this", "these", "those", "it", "its", "he", "she", "they",
            "we", "you", "me", "him", "her", "them", "us",
            "的", "了", "在", "是", "我", "他", "她", "它", "们",
            "有", "和", "与", "也", "都", "就", "而", "及",
            "name",
        }
        words = set(re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]{2,}', text.lower()))
        return words - stop_words

    @staticmethod
    def _facts_conflict(existing: str, new_lower: str) -> bool:
        existing_lower = existing.lower()
        new_words = MemoryData._tokenize(new_lower)
        existing_words = MemoryData._tokenize(existing_lower)

        if not new_words or not existing_words:
            return False

        new_has_neg = MemoryData._has_negation(new_words)
        existing_has_neg = MemoryData._has_negation(existing_words)
        if new_has_neg != existing_has_neg:
            logger.debug(f"[Memory] Conflict rejected: negation mismatch "
                         f"existing={existing_has_neg} new={new_has_neg}")
            return False

        new_values = MemoryData._get_value_words(new_lower)
        existing_values = MemoryData._get_value_words(existing_lower)

        if new_values and existing_values:
            only_in_new = new_values - existing_values
            only_in_existing = existing_values - new_values
            if only_in_new and only_in_existing:
                logger.debug(f"[Memory] Conflict rejected: different value words "
                             f"new_only={only_in_new} existing_only={only_in_existing}")
                return False

        new_in_existing = len(new_words & existing_words) / len(new_words)
        existing_in_new = len(new_words & existing_words) / len(existing_words)

        if new_in_existing > 0.7 and existing_in_new > 0.5:
            logger.debug(f"[Memory] Conflict detected: bidirectional overlap "
                         f"new→exist={new_in_existing:.2f} exist→new={existing_in_new:.2f}")
            return True

        if new_in_existing > 0.85:
            logger.debug(f"[Memory] Conflict detected: high one-directional overlap "
                         f"new→exist={new_in_existing:.2f}")
            return True

        if new_values and existing_values:
            new_val_in_exist = len(new_values & existing_values) / len(new_values)
            exist_val_in_new = len(new_values & existing_values) / len(existing_values)
            if new_val_in_exist >= 0.65 and exist_val_in_new > 0.5:
                logger.debug(f"[Memory] Conflict detected: value-level bidirectional overlap "
                             f"new→exist={new_val_in_exist:.2f} exist→new={exist_val_in_new:.2f}")
                return True

        return False


def create_empty_memory() -> MemoryData:
    return MemoryData()
