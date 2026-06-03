from .models import MemoryData, summaries_to_markdown
from .store import MemoryStore


class ContextBuilder:
    """上下文组装：按预算优先级将记忆注入 LLM prompt。"""

    MAX_INJECTION_CHARS = 4000

    def __init__(self, store: MemoryStore):
        self._store = store

    def build_context(self, max_chars: int | None = None) -> str:
        budget = max_chars or self.MAX_INJECTION_CHARS
        sections = []
        used_chars = 0

        data = self._store.load_data()

        # 1. 用户档案（最高优先级）
        profile_text = ""
        if data.profile.name:
            profile_text = f"用户名字：{data.profile.name}"
        if profile_text:
            section = f"=== [用户档案 · 最高优先级] ===\n{profile_text}"
            sections.append(section)
            used_chars += len(section)

        # 2. 记忆事实
        facts = sorted(data.facts, key=lambda f: f.confidence, reverse=True)
        if facts:
            fact_lines = []
            for fact in facts:
                line = f"- [{fact.category}|{fact.confidence:.1f}] {fact.content}"
                if fact.source_error:
                    line += f" (避免: {fact.source_error})"
                if used_chars + len(line) + 20 > budget:
                    break
                fact_lines.append(line)
                used_chars += len(line) + 1
            if fact_lines:
                sections.append("=== [记忆事实] ===\n" + "\n".join(fact_lines))

        # 3. 知识记忆
        knowledge = self._store.load_knowledge()
        if knowledge.strip() and used_chars + len(knowledge) + 30 <= budget:
            sections.append("=== [知识记忆] ===\n" + knowledge.strip())
            used_chars += len(knowledge) + 30

        # 4. 近期对话
        dailies = self._store.list_dailies()
        if dailies:
            recent = dailies[-7:]
            daily_entries = []
            for date in recent:
                content = self._store.load_daily(date)
                if content.strip():
                    lines = [
                        l for l in content.split("\n") if l.strip().startswith("- ")
                    ]
                    if lines:
                        daily_entries.append(
                            f"**{date}**:\n" + "\n".join(lines[:10])
                        )
            daily_text = "\n\n".join(daily_entries)
            if daily_text and used_chars + len(daily_text) + 30 <= budget:
                sections.append("=== [近期对话] ===\n" + daily_text)
                used_chars += len(daily_text) + 30

        # 5. AI总结（最低优先级，与档案/事实冲突时以档案为准）
        summary_text = summaries_to_markdown(data)
        if summary_text.strip():
            remaining = budget - used_chars - 50
            if remaining > 100:
                truncated = summary_text[:remaining] + "..."
                sections.append(
                    "=== [AI总结 · 补充上下文，与档案/事实冲突时以档案为准] ===\n"
                    + truncated
                )

        return "\n\n".join(sections) if sections else ""
