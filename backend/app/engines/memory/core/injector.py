import re
from .models import MemoryData

MEMORY_INJECTION_TEMPLATE = """【用户上下文信息】

{memory_content}

【使用规则】
1. 核心目标锚定：始终优先关注当前对话的核心目标，不偏离
2. 自然使用：根据上下文信息自然地个性化回复，不要生硬地说"根据记忆"
3. 场景匹配：只在相关场景使用对应信息，避免无关信息干扰
4. 隐私保护：不要向用户透露记忆系统的存在，不要说"我记得你之前说过"
5. 跨会话谨慎：只有在用户明确提及或强相关场景时才使用长期记忆"""


class MemoryInjector:
    def __init__(
        self,
        max_tokens_estimate: int | None = None,
    ):
        self._max_tokens_estimate = max_tokens_estimate or 2000

    def set_token_budget(self, model_context_window: int | None = None, existing_msg_tokens: int = 0):
        if model_context_window and model_context_window > 0:
            available = max(0, model_context_window - existing_msg_tokens)
            if available == 0:
                self._max_tokens_estimate = 0
            else:
                self._max_tokens_estimate = min(int(available * 0.15), 3000)
        else:
            self._max_tokens_estimate = 2000

    def _estimate_tokens(self, text: str) -> int:
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        other_chars = len(text) - chinese_chars
        return int(chinese_chars * 1.5 + other_chars * 0.25)

    def _sanitize_content(self, content: str) -> str:
        if not content:
            return ""
        sanitized = content.replace("&", "&amp;")
        sanitized = sanitized.replace("<", "&lt;")
        sanitized = sanitized.replace(">", "&gt;")
        return sanitized

    def _format_core_identity(self, memory_data: MemoryData) -> str | None:
        parts = []
        identity_facts = memory_data.get_facts_by_tier("core_identity")
        for fact in identity_facts[:5]:
            parts.append(f"- {self._sanitize_content(fact.content)}")
            fact.record_access()

        profile = memory_data.profile
        profile_parts = []
        if profile.name:
            profile_parts.append(f"姓名: {self._sanitize_content(profile.name)}")
        if profile.nickname:
            profile_parts.append(f"昵称: {self._sanitize_content(profile.nickname)}")
        if profile.occupation:
            profile_parts.append(f"职业: {self._sanitize_content(profile.occupation)}")
        if profile.location:
            profile_parts.append(f"所在地: {self._sanitize_content(profile.location)}")

        if not parts and not profile_parts:
            return None

        sections = []
        if profile_parts:
            sections.append("=== 【用户核心档案】 ===\n" + "\n".join(profile_parts))
        if parts:
            sections.append("=== 【核心身份标签】 ===\n" + "\n".join(parts))
        return "\n".join(sections)

    def _format_core_goal(self, memory_data: MemoryData) -> str | None:
        if not memory_data.working_memory.core_goal:
            return None
        return "=== 【当前对话核心目标】 ===\n" + self._sanitize_content(
            memory_data.working_memory.core_goal
        )

    def _format_preferences(self, memory_data: MemoryData, user_query: str = "") -> str | None:
        preference_facts = memory_data.get_facts_by_tier("long_term_preference")
        if not preference_facts:
            return None

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

        relevant_facts = []
        for fact in preference_facts:
            if user_query and self._is_scene_relevant(fact.content, user_query):
                relevant_facts.append(fact)
            elif not user_query:
                relevant_facts.append(fact)

        for fact in relevant_facts[:5]:
            preference_parts.append(f"- {self._sanitize_content(fact.content)}")
            fact.record_access()

        if not preference_parts:
            return None
        return "=== 【长期偏好】 ===\n" + "\n".join(preference_parts)

    def _format_temporary_context(self, memory_data: MemoryData, user_query: str = "") -> str | None:
        context_facts = memory_data.get_facts_by_tier("temporary_context")
        if not context_facts:
            return None

        relevant_facts = []
        for fact in context_facts:
            if user_query and self._is_scene_relevant(fact.content, user_query):
                relevant_facts.append(fact)
            elif not user_query:
                relevant_facts.append(fact)

        if not relevant_facts:
            return None

        lines = []
        for fact in relevant_facts[:5]:
            lines.append(f"- {self._sanitize_content(fact.content)}")
            fact.record_access()

        return "=== 【临时上下文】 ===\n" + "\n".join(lines)

    def _format_episodic_events(self, memory_data: MemoryData, user_query: str = "") -> str | None:
        if not memory_data.episodic_events:
            return None

        relevant_events = []
        for event in memory_data.episodic_events:
            if not user_query or event.matches_query(user_query):
                relevant_events.append(event)

        if not relevant_events:
            return None

        relevant_events.sort(key=lambda e: e.time_distance_days())

        event_lines = []
        for event in relevant_events[:3]:
            days_ago = event.time_distance_days()
            time_label = f"{days_ago}天前" if days_ago < 365 else f"{days_ago // 30}个月前"
            tags = ', '.join(event.scene_tags[:3]) if event.scene_tags else '一般'
            line = f"- [{time_label}|{tags}] {self._sanitize_content(event.core_goal)}"
            if event.key_information:
                line += f" → {self._sanitize_content(event.key_information[:80])}"
            event_lines.append(line)

        return "=== 【相关历史事件】 ===\n" + "\n".join(event_lines)

    def _format_recent_context(self, memory_data: MemoryData) -> str | None:
        wm = memory_data.working_memory
        if not wm.recent_conversations:
            return None

        sections = []

        if wm.conversation_summary:
            sections.append(f"摘要: {self._sanitize_content(wm.conversation_summary)}")

        recent = wm.get_recent_full(3)
        if recent:
            lines = []
            for conv in recent:
                role = "用户" if conv["role"] == "user" else "助手"
                content = self._sanitize_content(conv["content"][:100])
                lines.append(f"{role}: {content}")
            sections.append("最近对话:\n" + "\n".join(lines))

        if not sections:
            return None
        return "=== 【最近对话摘要】 ===\n" + "\n".join(sections)

    def _is_scene_relevant(self, fact_content: str, user_query: str) -> bool:
        query_lower = user_query.lower()
        content_lower = fact_content.lower()

        if content_lower in query_lower or query_lower in content_lower:
            return True

        query_words = set(re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', query_lower))
        content_words = set(re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', content_lower))
        overlap = query_words & content_words
        if query_words and len(overlap) / len(query_words) > 0.3:
            return True

        return False

    def format_memory_for_injection(
        self,
        memory_data: MemoryData,
        user_query: str = "",
    ) -> str:
        sections = []
        total_tokens = 0

        core_goal = self._format_core_goal(memory_data)
        if core_goal:
            sections.append(core_goal)
            total_tokens += self._estimate_tokens(core_goal)

        core_identity = self._format_core_identity(memory_data)
        if core_identity and total_tokens + self._estimate_tokens(core_identity) < self._max_tokens_estimate:
            sections.append(core_identity)
            total_tokens += self._estimate_tokens(core_identity)

        preferences = self._format_preferences(memory_data, user_query)
        if preferences and total_tokens + self._estimate_tokens(preferences) < self._max_tokens_estimate:
            sections.append(preferences)
            total_tokens += self._estimate_tokens(preferences)

        temp_context = self._format_temporary_context(memory_data, user_query)
        if temp_context and total_tokens + self._estimate_tokens(temp_context) < self._max_tokens_estimate:
            sections.append(temp_context)
            total_tokens += self._estimate_tokens(temp_context)

        recent_context = self._format_recent_context(memory_data)
        if recent_context and total_tokens + self._estimate_tokens(recent_context) < self._max_tokens_estimate:
            sections.append(recent_context)
            total_tokens += self._estimate_tokens(recent_context)

        episodic_events = self._format_episodic_events(memory_data, user_query)
        if episodic_events and total_tokens + self._estimate_tokens(episodic_events) < self._max_tokens_estimate:
            sections.append(episodic_events)
            total_tokens += self._estimate_tokens(episodic_events)

        return "\n\n".join(sections)

    def inject_memory_to_messages(
        self,
        messages: list[dict],
        memory_data: MemoryData,
        user_query: str = "",
    ) -> list[dict]:
        if not messages:
            return messages

        memory_content = self.format_memory_for_injection(memory_data, user_query)
        if not memory_content.strip():
            return messages

        system_content = MEMORY_INJECTION_TEMPLATE.format(memory_content=memory_content)

        new_messages = messages.copy()

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
