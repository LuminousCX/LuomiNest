from .models import MemoryData


MEMORY_INJECTION_TEMPLATE = """You have access to the user's memory profile. Use this context to personalize your responses.

<user_memory>
{memory_content}
</user_memory>

【关键指令 - 必须遵守】

1. 用户身份识别：
   - 当用户问"我是谁""你知道我是谁吗"等问题时，查看上面的"用户档案"部分
   - 根据档案中的姓名、昵称、职业、所在地等信息回答
   - 示例回答："你是小明，一名软件工程师，来自北京。你喜欢编程和阅读。"
   - 如果没有档案信息，回答："我还不太了解你呢，你愿意介绍一下自己吗？"

2. 个性化交流：
   - 使用用户档案中的信息来个性化你的回复
   - 参考用户的兴趣爱好、职业背景来提供相关建议
   - 尊重用户的偏好设置

3. 禁止行为：
   - 不要直接告诉用户"我在查看你的记忆"
   - 不要重复用户的问题作为回答
   - 不要回答"我是AI助手"来回应"我是谁"的问题
"""


class MemoryInjector:
    def __init__(self, max_facts: int = 20, max_tokens_estimate: int = 2000):
        self._max_facts = max_facts
        self._max_tokens_estimate = max_tokens_estimate

    def _estimate_tokens(self, text: str) -> int:
        return len(text) // 4

    def _sanitize_content(self, content: str) -> str:
        if not content:
            return ""
        sanitized = content.replace("&", "&amp;")
        sanitized = sanitized.replace("<", "&lt;")
        sanitized = sanitized.replace(">", "&gt;")
        return sanitized

    def _format_profile(self, memory_data: MemoryData) -> str | None:
        profile = memory_data.profile
        parts = []
        
        if profile.name:
            parts.append(f"姓名: {self._sanitize_content(profile.name)}")
        if profile.nickname:
            parts.append(f"昵称: {self._sanitize_content(profile.nickname)}")
        if profile.age:
            parts.append(f"年龄: {self._sanitize_content(profile.age)}")
        if profile.gender:
            parts.append(f"性别: {self._sanitize_content(profile.gender)}")
        if profile.occupation:
            parts.append(f"职业: {self._sanitize_content(profile.occupation)}")
        if profile.location:
            parts.append(f"所在地: {self._sanitize_content(profile.location)}")
        if profile.timezone:
            parts.append(f"时区: {self._sanitize_content(profile.timezone)}")
        if profile.language:
            parts.append(f"语言: {self._sanitize_content(profile.language)}")
        if profile.interests:
            interests_str = ", ".join(self._sanitize_content(i) for i in profile.interests[:10])
            parts.append(f"兴趣: {interests_str}")
        if profile.hobbies:
            hobbies_str = ", ".join(self._sanitize_content(h) for h in profile.hobbies[:10])
            parts.append(f"爱好: {hobbies_str}")
        if profile.preferences:
            for key, value in list(profile.preferences.items())[:5]:
                parts.append(f"{key}: {self._sanitize_content(value)}")
        if profile.notes:
            parts.append(f"备注: {self._sanitize_content(profile.notes[:500])}")
        
        if not parts:
            return None
        return "=== 用户档案 ===\n" + "\n".join(parts)

    def format_memory_for_injection(self, memory_data: MemoryData) -> str:
        sections = []
        total_tokens = 0

        profile_section = self._format_profile(memory_data)
        if profile_section:
            sections.append(profile_section)
            total_tokens += self._estimate_tokens(profile_section)

        user_context_parts = []
        if memory_data.user.work_context.summary:
            sanitized_summary = self._sanitize_content(memory_data.user.work_context.summary)
            user_context_parts.append(f"Work Context: {sanitized_summary}")
        if memory_data.user.personal_context.summary:
            sanitized_summary = self._sanitize_content(memory_data.user.personal_context.summary)
            user_context_parts.append(f"Personal Context: {sanitized_summary}")
        if memory_data.user.top_of_mind.summary:
            sanitized_summary = self._sanitize_content(memory_data.user.top_of_mind.summary)
            user_context_parts.append(f"Current Focus: {sanitized_summary}")

        if user_context_parts:
            section = "=== User Context ===\n" + "\n".join(user_context_parts)
            sections.append(section)
            total_tokens += self._estimate_tokens(section)

        sorted_facts = sorted(
            memory_data.facts,
            key=lambda f: f.confidence,
            reverse=True
        )[:self._max_facts]

        if sorted_facts:
            fact_lines = []
            fact_section_header = "=== Known Facts ==="
            fact_tokens = self._estimate_tokens(fact_section_header)

            for fact in sorted_facts:
                sanitized_content = self._sanitize_content(fact.content)
                line = f"- [{fact.category}] {sanitized_content}"
                line_tokens = self._estimate_tokens(line)
                if total_tokens + fact_tokens + line_tokens > self._max_tokens_estimate:
                    break
                fact_lines.append(line)
                fact_tokens += line_tokens

            if fact_lines:
                sections.append(fact_section_header + "\n" + "\n".join(fact_lines))
                total_tokens += fact_tokens

        return "\n\n".join(sections)

    def inject_memory_to_messages(
        self,
        messages: list[dict],
        memory_data: MemoryData,
        position: str = "start",
    ) -> list[dict]:
        if not messages:
            return messages

        memory_content = self.format_memory_for_injection(memory_data)
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
        facts_by_category: dict[str, int] = {}
        for fact in memory_data.facts:
            facts_by_category[fact.category] = facts_by_category.get(fact.category, 0) + 1

        profile = memory_data.profile
        has_profile = bool(
            profile.name or profile.nickname or profile.occupation or 
            profile.location or profile.interests or profile.hobbies
        )

        return {
            "has_work_context": bool(memory_data.user.work_context.summary),
            "has_personal_context": bool(memory_data.user.personal_context.summary),
            "has_top_of_mind": bool(memory_data.user.top_of_mind.summary),
            "has_profile": has_profile,
            "total_facts": len(memory_data.facts),
            "facts_by_category": facts_by_category,
            "last_updated": memory_data.last_updated,
        }
