from __future__ import annotations

import re
from datetime import datetime

from app.engines.memory.core.models import (
    EpisodicEvent,
    MemoryFact,
    MemoryTier,
    UserSpace,
    AgentMemory,
    utc_now_iso_z,
)


class MarkdownParser:

    PROFILE_MAP = {
        "姓名": "name", "昵称": "nickname", "年龄": "age",
        "性别": "gender", "职业": "occupation", "位置": "location",
        "时区": "timezone", "语言": "language",
        "兴趣": "interests", "爱好": "hobbies",
    }

    CONTEXT_MAP = {
        "工作": "work_context",
        "个人": "personal_context",
        "近期关注": "top_of_mind",
    }

    TIER_MAP = {
        "核心身份": "core_identity",
        "长期偏好": "long_term_preference",
        "临时上下文": "temporary_context",
    }

    VALID_TIERS = {"core_identity", "long_term_preference", "temporary_context"}

    def parse_and_update(self, md: str, user_space: UserSpace, agent_id: str | None = None) -> dict:
        stats = {"facts_imported": 0, "events_imported": 0, "agent_facts_imported": 0}

        self._parse_profile(md, user_space)
        self._parse_context(md, user_space)
        stats["facts_imported"] = self._parse_facts(md, user_space)
        stats["events_imported"] = self._parse_events(md, user_space)

        if agent_id:
            stats["agent_facts_imported"] = self._parse_agent_section(md, agent_id)

        return stats

    def _parse_profile(self, md: str, us: UserSpace) -> None:
        match = re.search(r"## 用户档案(.*?)(?=## |\Z)", md, re.DOTALL)
        if not match:
            return
        for line in match.group(1).strip().split("\n"):
            m = re.match(r"- \*\*(.+?)\*\*[:：]\s*(.+)", line.strip())
            if not m:
                continue
            name, val = m.group(1).strip(), m.group(2).strip()
            attr = self.PROFILE_MAP.get(name)
            if not attr:
                continue
            if attr in ("interests", "hobbies"):
                current = getattr(us.profile, attr, [])
                new_items = [x.strip() for x in val.split(",") if x.strip()]
                merged = list(dict.fromkeys(current + new_items))
                setattr(us.profile, attr, merged)
            elif val and val != "未设置":
                setattr(us.profile, attr, val)

    def _parse_context(self, md: str, us: UserSpace) -> None:
        match = re.search(r"## 当前上下文(.*?)(?=## |\Z)", md, re.DOTALL)
        if not match:
            return
        for line in match.group(1).strip().split("\n"):
            m = re.match(r"- \*\*(.+?)\*\*[:：]\s*(.+)", line.strip())
            if not m:
                continue
            name, val = m.group(1).strip(), m.group(2).strip()
            ctx_attr = self.CONTEXT_MAP.get(name)
            if ctx_attr and val:
                section = getattr(us.user, ctx_attr)
                section.summary = val
                section.updated_at = utc_now_iso_z()

    def _parse_facts(self, md: str, us: UserSpace) -> int:
        imported = 0
        for title, tier in self.TIER_MAP.items():
            match = re.search(rf"## {re.escape(title)}(.*?)(?=## |\Z)", md, re.DOTALL)
            if not match:
                continue
            existing_contents = {f.content.casefold() for f in us.facts if f.tier == tier}
            for line in match.group(1).strip().split("\n"):
                stripped = line.strip()
                if not stripped.startswith("-"):
                    continue
                content = self._extract_fact_content(stripped)
                if not content or len(content) < 5:
                    continue
                if content.casefold() in existing_contents:
                    continue
                category = self._extract_category(stripped)
                fact = MemoryFact(
                    content=content,
                    category=category,
                    tier=tier,
                    layer="user",
                    confidence=1.0,
                    source="import",
                )
                us.facts.append(fact)
                existing_contents.add(content.casefold())
                imported += 1
        return imported

    def _parse_events(self, md: str, us: UserSpace) -> int:
        imported = 0
        match = re.search(r"## 重要事件(.*?)(?=## |\Z)", md, re.DOTALL)
        if not match:
            return 0
        existing_goals = {e.core_goal.casefold() for e in us.episodic_events}
        for line in match.group(1).strip().split("\n"):
            stripped = line.strip()
            if not stripped.startswith("-"):
                continue
            bracket_end = stripped.find("]")
            if bracket_end < 0:
                continue
            content = stripped[bracket_end + 1:].strip()
            if not content or content.casefold() in existing_goals:
                continue
            event = EpisodicEvent(core_goal=content[:200])
            us.episodic_events.append(event)
            existing_goals.add(content.casefold())
            imported += 1
        return imported

    def _parse_agent_section(self, md: str, agent_id: str) -> int:
        imported = 0
        match = re.search(r"### Agent 特有事实(.*?)(?=###|## |\Z)", md, re.DOTALL)
        if not match:
            return 0
        from app.engines.memory.core.storage import get_memory_storage
        storage = get_memory_storage()
        agent_memory = storage.load_agent_memory(agent_id)
        existing_contents = {f.content.casefold() for f in agent_memory.agent_facts}

        for line in match.group(1).strip().split("\n"):
            stripped = line.strip()
            if not stripped.startswith("-"):
                continue
            content = self._extract_fact_content(stripped)
            if not content or len(content) < 5:
                continue
            if content.casefold() in existing_contents:
                continue
            category = self._extract_category(stripped)
            tier = self._extract_tier(stripped) or "long_term_preference"
            fact = MemoryFact(
                content=content,
                category=category,
                tier=tier,
                layer="agent",
                confidence=1.0,
                source="import",
                source_agent_id=agent_id,
            )
            agent_memory.agent_facts.append(fact)
            existing_contents.add(content.casefold())
            imported += 1

        if imported > 0:
            storage.save_agent_memory(agent_memory, agent_id)
        return imported

    @staticmethod
    def _extract_fact_content(line: str) -> str:
        content = re.sub(r"^\-\s*\[[^\]]*\]\s*", "", line)
        content = re.sub(r"\s*\(置信度:\s*[\d.]+\)\s*$", "", content)
        return content.strip()

    @staticmethod
    def _extract_category(line: str) -> str:
        m = re.match(r"-\s*\[([^\]]+)\]", line)
        if m:
            cat = m.group(1).strip()
            if cat in ["preference", "knowledge", "context", "behavior", "goal", "correction"]:
                return cat
        return "context"

    @staticmethod
    def _extract_tier(line: str) -> str:
        m = re.search(r"\btier[=:]\s*(\w+)", line, re.IGNORECASE)
        if m:
            tier = m.group(1).strip()
            if tier in MarkdownParser.VALID_TIERS:
                return tier
        return ""
