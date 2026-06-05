from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field


FACT_CATEGORIES = ("preference", "knowledge", "context", "behavior", "goal", "correction")

# 事实作用域：Agent级共享 vs 对话级隔离
FACT_SCOPE_AGENT = {"preference", "knowledge", "correction"}
FACT_SCOPE_CONVERSATION = {"context", "behavior", "goal"}

_SUMMARY_SECTION_MAP = {
    "用户画像": "user_profile",
    "偏好设置": "preferences",
    "兴趣目标": "interests",
    "近期状态": "recent_state",
    "事件时间线": "timeline",
}


class ProfileData(BaseModel):
    name: str = ""
    updated_at: str = ""
    # Static: 长期稳定的事实（很少变化，如职业、技能、偏好）
    static_facts: list[str] = Field(default_factory=list)
    # Dynamic: 近期上下文和临时状态（频繁更新，如正在做的项目、短期计划）
    dynamic_context: list[str] = Field(default_factory=list)


class ArchivedFact(BaseModel):
    """归档的事实版本，记录变更历史。"""
    content: str
    category: str = ""
    confidence: float = 0.0
    archived_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    reason: str = ""  # 归档原因：superseded / conflict / expired / manual


class FactItem(BaseModel):
    id: str = Field(default_factory=lambda: f"fact_{uuid4().hex[:8]}")
    content: str
    category: str = "context"
    confidence: float = 0.8
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: str = "conversation"
    source_error: str = ""
    # 时间衰减：可选的过期时间，None = 永不过期
    expires_at: str | None = None
    # 关系图谱：是否是最新版本
    is_latest: bool = True
    # 关系图谱：替代了哪个 fact ID（用于矛盾追踪）
    supersedes_id: str | None = None
    # 溯源：来源对话ID和原始消息
    source_conversation_id: str = ""
    source_message: str = ""
    # 版本归档：历史版本列表
    history: list[ArchivedFact] = Field(default_factory=list)


class SummarySection(BaseModel):
    summary: str = ""
    updated_at: str = ""


class SummaryData(BaseModel):
    user_profile: SummarySection = Field(default_factory=SummarySection)
    preferences: SummarySection = Field(default_factory=SummarySection)
    interests: SummarySection = Field(default_factory=SummarySection)
    recent_state: SummarySection = Field(default_factory=SummarySection)
    timeline: SummarySection = Field(default_factory=SummarySection)


class MemoryData(BaseModel):
    version: str = "2.0"
    last_updated: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    profile: ProfileData = Field(default_factory=ProfileData)
    facts: list[FactItem] = Field(default_factory=list)
    summaries: SummaryData = Field(default_factory=SummaryData)


def summaries_to_markdown(data: MemoryData) -> str:
    """将 MemoryData 中的总结部分转为 Markdown 格式。"""
    lines = []
    sections = [
        ("用户画像", data.summaries.user_profile.summary),
        ("偏好设置", data.summaries.preferences.summary),
        ("兴趣目标", data.summaries.interests.summary),
        ("近期状态", data.summaries.recent_state.summary),
        ("事件时间线", data.summaries.timeline.summary),
    ]
    for title, content in sections:
        if content:
            lines.append(f"## {title}\n{content}")
    return "\n\n".join(lines)
