from .models import MemoryData


MEMORY_INJECTION_TEMPLATE = """You have access to the user's memory profile. Use this context to personalize your responses.

<user_memory>
{memory_content}
</user_memory>

Instructions:
- Use the user context to understand their current situation
- Reference relevant facts naturally when appropriate
- Respect user preferences in your responses
- Do not explicitly mention "I remember from your memory" unless relevant
"""


class MemoryInjector:
    def __init__(self, max_facts: int = 20, max_tokens_estimate: int = 2000):
        self._max_facts = max_facts
        self._max_tokens_estimate = max_tokens_estimate

    def _estimate_tokens(self, text: str) -> int:
        return len(text) // 4

    def format_memory_for_injection(self, memory_data: MemoryData) -> str:
        sections = []
        total_tokens = 0

        user_context_parts = []
        if memory_data.user.work_context.summary:
            user_context_parts.append(f"Work Context: {memory_data.user.work_context.summary}")
        if memory_data.user.personal_context.summary:
            user_context_parts.append(f"Personal Context: {memory_data.user.personal_context.summary}")
        if memory_data.user.top_of_mind.summary:
            user_context_parts.append(f"Current Focus: {memory_data.user.top_of_mind.summary}")

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
                line = f"- [{fact.category}] {fact.content}"
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

        return {
            "has_work_context": bool(memory_data.user.work_context.summary),
            "has_personal_context": bool(memory_data.user.personal_context.summary),
            "has_top_of_mind": bool(memory_data.user.top_of_mind.summary),
            "total_facts": len(memory_data.facts),
            "facts_by_category": facts_by_category,
            "last_updated": memory_data.last_updated,
        }
