from .models import MemoryData


MEMORY_INJECTION_TEMPLATE = """【记忆系统 - 豆包风格】

以下是关于用户的记忆信息，请使用这些信息来提供个性化、有上下文的回复。

{memory_content}

【记忆使用规则 - 必须严格遵守】

1. 核心目标锚定：
- 始终优先关注当前对话的核心目标
- 核心目标会一直保持在对话的最前面
- 即使进行多次工具调用或子任务，也不能偏离核心目标

2. 记忆使用方式：
- 当用户询问"我是谁"等问题时，查看用户核心档案
- 根据记忆信息自然地个性化回复，不要生硬地说"根据记忆"
- 只在相关场景注入对应的记忆，避免记忆干扰

3. 绝对禁止：
- 不要向用户透露记忆系统的存在
- 不要说"我记得你之前说过"之类的话
- 不要在回复中重复记忆内容
- 不要让用户感到被监视或记录

4. 跨会话记忆：
- 只有在用户明确提及或相关场景时才使用长期记忆
- 不要主动提及很久以前的记忆内容
- 对话之间的记忆是隔离的
"""


class MemoryInjector:
    def __init__(
        self, 
        max_facts: int = 15, 
        max_tokens_estimate: int = 2000,
        conversation_id: str | None = None,
    ):
        self._max_facts = max_facts
        self._max_tokens_estimate = max_tokens_estimate
        self._conversation_id = conversation_id

    def _estimate_tokens(self, text: str) -> int:
        return len(text) // 4

    def _sanitize_content(self, content: str) -> str:
        if not content:
            return ""
        sanitized = content.replace("&", "&amp;")
        sanitized = sanitized.replace("<", "&lt;")
        sanitized = sanitized.replace(">", "&gt;")
        return sanitized

    def _format_core_identity(self, memory_data: MemoryData) -> str | None:
        profile = memory_data.profile
        parts = []
        
        if profile.name:
            parts.append(f"姓名: {self._sanitize_content(profile.name)}")
        if profile.nickname:
            parts.append(f"昵称: {self._sanitize_content(profile.nickname)}")
        if profile.occupation:
            parts.append(f"职业: {self._sanitize_content(profile.occupation)}")
        if profile.location:
            parts.append(f"所在地: {self._sanitize_content(profile.location)}")
        if profile.age:
            parts.append(f"年龄: {self._sanitize_content(profile.age)}")
        
        if not parts:
            return None
        return "=== 【用户核心档案】 ===\n" + "\n".join(parts)

    def _format_core_goal(self, memory_data: MemoryData) -> str | None:
        if not memory_data.working_memory.core_goal:
            return None
        return "=== 【当前对话核心目标】 ===\n" + self._sanitize_content(
            memory_data.working_memory.core_goal
        )

    def _format_preferences(self, memory_data: MemoryData) -> str | None:
        profile = memory_data.profile
        preference_parts = []
        
        if profile.interests:
            interests_str = ", ".join(self._sanitize_content(i) for i in profile.interests[:5])
            preference_parts.append(f"兴趣: {interests_str}")
        if profile.hobbies:
            hobbies_str = ", ".join(self._sanitize_content(h) for h in profile.hobbies[:5])
            preference_parts.append(f"爱好: {hobbies_str}")
        if profile.preferences:
            for key, value in list(profile.preferences.items())[:5]:
                preference_parts.append(f"{key}: {self._sanitize_content(value)}")
        
        if not preference_parts:
            return None
        return "=== 【长期偏好】 ===\n" + "\n".join(preference_parts)

    def _format_relevant_facts(self, memory_data: MemoryData, query: str = "") -> str | None:
        sorted_facts = sorted(
            memory_data.facts,
            key=lambda f: (f.confidence, f.access_count, f.last_accessed_at),
            reverse=True
        )
        
        tier_order = ["core_identity", "long_term_preference", "temporary_context"]
        facts_by_tier: dict[str, list] = {}
        for fact in sorted_facts:
            if fact.tier not in facts_by_tier:
                facts_by_tier[fact.tier] = []
            facts_by_tier[fact.tier].append(fact)
        
        fact_lines = []
        fact_tokens = 0
        
        tier_names = {
            "core_identity": "核心身份",
            "long_term_preference": "长期偏好",
            "temporary_context": "临时上下文",
        }
        
        for tier in tier_order:
            if tier not in facts_by_tier:
                continue
            
            tier_facts = facts_by_tier[tier]
            if not tier_facts:
                continue
            
            for fact in tier_facts[:5]:
                if query and not (fact.content.lower() in query.lower() or query.lower() in fact.content.lower()):
                    continue
                
                sanitized_content = self._sanitize_content(fact.content)
                line = f"- [{tier_names.get(fact.tier, fact.tier)}] {sanitized_content}"
                line_tokens = self._estimate_tokens(line)
                if fact_tokens + line_tokens > 800:
                    break
                fact_lines.append(line)
                fact_tokens += line_tokens
                
                fact.record_access()
        
        if not fact_lines:
            return None
        return "=== 【相关记忆点】 ===\n" + "\n".join(fact_lines)

    def _format_episodic_events(self, memory_data: MemoryData, query: str = "") -> str | None:
        if not memory_data.episodic_events:
            return None
        
        relevant_events = []
        for event in memory_data.episodic_events[:10]:
            if query and not event.matches_query(query):
                continue
            relevant_events.append(event)
        
        if not relevant_events:
            return None
        
        event_lines = []
        for event in relevant_events[:3]:
            line = f"- [{', '.join(event.scene_tags) or '一般'}] {self._sanitize_content(event.core_goal)}"
            event_lines.append(line)
        
        return "=== 【相关历史事件】 ===\n" + "\n".join(event_lines)

    def _format_recent_context(self, memory_data: MemoryData) -> str | None:
        if not memory_data.working_memory.recent_conversations:
            return None
        
        recent = memory_data.working_memory.recent_conversations[-5:]
        lines = []
        for conv in recent:
            role = "用户" if conv["role"] == "user" else "助手"
            content = self._sanitize_content(conv["content"][:100])
            lines.append(f"{role}: {content}")
        
        return "=== 【最近对话摘要】 ===\n" + "\n".join(lines)

    def format_memory_for_injection(
        self, 
        memory_data: MemoryData,
        user_query: str = "",
    ) -> str:
        sections = []
        total_tokens = 0

        core_identity = self._format_core_identity(memory_data)
        if core_identity:
            sections.append(core_identity)
            total_tokens += self._estimate_tokens(core_identity)

        core_goal = self._format_core_goal(memory_data)
        if core_goal:
            sections.append(core_goal)
            total_tokens += self._estimate_tokens(core_goal)

        preferences = self._format_preferences(memory_data)
        if preferences and total_tokens + self._estimate_tokens(preferences) < self._max_tokens_estimate:
            sections.append(preferences)
            total_tokens += self._estimate_tokens(preferences)

        relevant_facts = self._format_relevant_facts(memory_data, user_query)
        if relevant_facts and total_tokens + self._estimate_tokens(relevant_facts) < self._max_tokens_estimate:
            sections.append(relevant_facts)
            total_tokens += self._estimate_tokens(relevant_facts)

        episodic_events = self._format_episodic_events(memory_data, user_query)
        if episodic_events and total_tokens + self._estimate_tokens(episodic_events) < self._max_tokens_estimate:
            sections.append(episodic_events)
            total_tokens += self._estimate_tokens(episodic_events)

        return "\n\n".join(sections)

    def inject_memory_to_messages(
        self,
        messages: list[dict],
        memory_data: MemoryData,
        position: str = "start",
        user_query: str = "",
    ) -> list[dict]:
        if not messages:
            return messages

        memory_content = self.format_memory_for_injection(memory_data, user_query)
        if not memory_content.strip():
            return messages

        system_content = MEMORY_INJECTION_TEMPLATE.format(memory_content=memory_content)

        new_messages = messages.copy()

        if position == "start":
            has_system = new_messages and new_messages[0].get("role") == "system"
            if has_system:
                existing = new_messages[0].get("content", "")
                if isinstance(existing, str):
                    new_messages[0] = {
                        "role": "system",
                        "content": existing + "\n\n" + system_content,
                    }
                else:
                    new_messages.insert(0, {"role": "system", "content": system_content})
            else:
                new_messages.insert(0, {"role": "system", "content": system_content})
        else:
            new_messages.append({"role": "system", "content": system_content})

        return new_messages

    def get_memory_summary(self, memory_data: MemoryData) -> dict:
        facts_by_tier: dict[str, int] = {}
        for fact in memory_data.facts:
            facts_by_tier[fact.tier] = facts_by_tier.get(fact.tier, 0) + 1

        profile = memory_data.profile
        has_profile = bool(
            profile.name or profile.nickname or profile.occupation or 
            profile.location or profile.interests or profile.hobbies
        )

        return {
            "version": memory_data.version,
            "has_core_goal": bool(memory_data.working_memory.core_goal),
            "has_profile": has_profile,
            "total_facts": len(memory_data.facts),
            "total_events": len(memory_data.episodic_events),
            "total_archived": len(memory_data.archived_facts),
            "facts_by_tier": facts_by_tier,
            "last_updated": memory_data.last_updated,
        }
