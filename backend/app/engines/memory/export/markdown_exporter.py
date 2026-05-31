from __future__ import annotations

from datetime import datetime

from app.engines.memory.core.models import (
    UserSpace,
    AgentMemory,
    MemoryTier,
    utc_now_iso_z,
)
from app.engines.memory.core.storage import MemoryStorage


class MemoryExporter:

    def __init__(self, storage: MemoryStorage):
        self._storage = storage

    def export_full_memory(self, agent_id: str | None = None) -> str:
        user_space = self._storage.load_user_space()
        md = self._format_user_space(user_space)
        if agent_id:
            agent_memory = self._storage.load_agent_memory(agent_id)
            md += "\n\n---\n\n" + self._format_agent(agent_memory)
        md += f"\n\n---\n\n> 最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        return md

    def _format_user_space(self, us: UserSpace) -> str:
        lines = ["# 用户记忆档案", "", "## 用户档案"]

        p = us.profile
        lines.append(f"- **姓名**: {p.name or '未设置'}")
        if p.nickname:
            lines.append(f"- **昵称**: {p.nickname}")
        if p.age:
            lines.append(f"- **年龄**: {p.age}")
        if p.gender:
            lines.append(f"- **性别**: {p.gender}")
        if p.occupation:
            lines.append(f"- **职业**: {p.occupation}")
        if p.location:
            lines.append(f"- **位置**: {p.location}")
        if p.interests:
            lines.append(f"- **兴趣**: {', '.join(p.interests)}")
        if p.hobbies:
            lines.append(f"- **爱好**: {', '.join(p.hobbies)}")
        lines.append("")

        c = us.user
        if c.work_context.summary or c.personal_context.summary or c.top_of_mind.summary:
            lines.append("## 当前上下文")
            if c.work_context.summary:
                lines.append(f"- **工作**: {c.work_context.summary}")
            if c.personal_context.summary:
                lines.append(f"- **个人**: {c.personal_context.summary}")
            if c.top_of_mind.summary:
                lines.append(f"- **近期关注**: {c.top_of_mind.summary}")
            lines.append("")

        distilled = us.distilled
        if distilled.core_identity or distilled.long_term or distilled.temporary or distilled.events_timeline:
            lines.append("## 记忆摘要")
            if distilled.core_identity:
                lines.append(f"### 核心身份\n{distilled.core_identity}")
            if distilled.long_term:
                lines.append(f"### 长期偏好\n{distilled.long_term}")
            if distilled.temporary:
                lines.append(f"### 临时上下文\n{distilled.temporary}")
            if distilled.events_timeline:
                lines.append(f"### 事件时间线\n{distilled.events_timeline}")
            lines.append("")

        tier_config = [
            ("core_identity", "核心身份"),
            ("long_term_preference", "长期偏好"),
            ("temporary_context", "临时上下文"),
        ]
        for tier, title in tier_config:
            facts = us.get_facts_by_tier(tier)
            if facts:
                lines.append(f"## {title}")
                for f in facts:
                    lines.append(f"- [{f.category}] {f.content} (置信度: {f.confidence:.1f})")
                lines.append("")

        if us.episodic_events:
            lines.append("## 重要事件")
            for e in sorted(us.episodic_events, key=lambda x: x.timestamp, reverse=True)[:15]:
                ts = e.timestamp[:10] if e.timestamp else ""
                tags = ', '.join(e.scene_tags[:3]) if e.scene_tags else '一般'
                lines.append(f"- [{ts}|{tags}] {e.core_goal}")
                if e.key_information:
                    lines.append(f"  关键信息: {e.key_information}")
            lines.append("")

        return "\n".join(lines)

    def _format_agent(self, am: AgentMemory) -> str:
        lines = [f"## Agent {am.agent_id} 私有记忆"]

        if am.domain_summary:
            lines.append(f"### 领域经验摘要\n{am.domain_summary}\n")

        if am.agent_facts:
            lines.append("### Agent 特有事实")
            for f in am.agent_facts:
                lines.append(f"- [{f.category}] {f.content} (置信度: {f.confidence:.1f})")
            lines.append("")

        if am.agent_events:
            lines.append("### Agent 情景事件")
            for e in sorted(am.agent_events, key=lambda x: x.timestamp, reverse=True)[:10]:
                ts = e.timestamp[:10] if e.timestamp else ""
                tags = ', '.join(e.scene_tags[:3]) if e.scene_tags else '一般'
                lines.append(f"- [{ts}|{tags}] {e.core_goal}")
            lines.append("")

        return "\n".join(lines)
