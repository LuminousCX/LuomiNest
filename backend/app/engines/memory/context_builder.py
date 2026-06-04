from datetime import datetime, timezone

from .models import FactItem, MemoryData, summaries_to_markdown
from .store import MemoryStore
from .fact_manager import _extract_content_words


class ContextBuilder:
    """上下文组装：按预算优先级将记忆注入 LLM prompt。"""

    MAX_INJECTION_CHARS = 4000

    def __init__(self, store: MemoryStore):
        self._store = store

    def build_context(self, max_chars: int | None = None, query: str = "", conversation_store=None) -> str:
        budget = max_chars or self.MAX_INJECTION_CHARS
        sections = []
        used_chars = 0

        data = self._store.load_data()

        # 1. 用户档案（最高优先级）- Static + Dynamic 分层注入
        profile_lines = []
        if data.profile.name:
            profile_lines.append(f"用户名字：{data.profile.name}")
        if data.profile.static_facts:
            profile_lines.append(f"稳定偏好：{'; '.join(data.profile.static_facts)}")
        if profile_lines:
            section = f"=== [用户档案 · 最高优先级] ===\n" + "\n".join(profile_lines)
            sections.append(section)
            used_chars += len(section)

        # 2. 动态上下文（当前正在做的事）- 优先从对话级store读取
        dynamic_context = []
        if conversation_store:
            conv_data = conversation_store.load_data()
            if conv_data.profile.dynamic_context:
                dynamic_context = conv_data.profile.dynamic_context
        if not dynamic_context and data.profile.dynamic_context:
            dynamic_context = data.profile.dynamic_context
        
        if dynamic_context:
            dynamic_lines = "\n".join(f"- {c}" for c in dynamic_context[-5:])
            section = f"=== [当前状态] ===\n{dynamic_lines}"
            if used_chars + len(section) + 20 <= budget:
                sections.append(section)
                used_chars += len(section) + 20

        # 3. 记忆事实（query-aware：优先注入与当前问题相关的事实）- 始终从Agent级store读取
        facts = sorted(data.facts, key=lambda f: f.confidence, reverse=True)
        valid_facts = []
        for fact in facts:
            if not fact.is_latest:
                continue
            if fact.expires_at:
                try:
                    exp_time = datetime.fromisoformat(fact.expires_at.replace("Z", "+00:00"))
                    if exp_time <= datetime.now(timezone.utc):
                        continue
                except (ValueError, TypeError):
                    pass
            valid_facts.append(fact)

        # query-aware 排序：与 query 相关的事实优先
        if query:
            query_words = _extract_content_words(query.casefold())
            if query_words:
                def fact_relevance(f: FactItem) -> float:
                    fact_words = _extract_content_words(f.content.casefold())
                    if not fact_words:
                        return 0.0
                    overlap = len(query_words & fact_words) / max(len(query_words | fact_words), 1)
                    return overlap + f.confidence * 0.1  # 相关性 + 少量置信度加权
                valid_facts.sort(key=fact_relevance, reverse=True)

        if valid_facts:
            fact_lines = []
            for fact in valid_facts:
                line = f"- [{fact.category}|{fact.confidence:.1f}] {fact.content}"
                if fact.source_error:
                    line += f" (避免: {fact.source_error})"
                if used_chars + len(line) + 20 > budget:
                    break
                fact_lines.append(line)
                used_chars += len(line) + 1
            if fact_lines:
                sections.append("=== [记忆事实] ===\n" + "\n".join(fact_lines))

        # 4. 知识记忆 - 始终从Agent级store读取
        knowledge = self._store.load_knowledge()
        if knowledge.strip() and used_chars + len(knowledge) + 30 <= budget:
            sections.append("=== [知识记忆] ===\n" + knowledge.strip())
            used_chars += len(knowledge) + 30

        # 5. 每日记录 - 优先从对话级store读取
        daily_content = ""
        if conversation_store:
            daily_content = conversation_store.load_daily()
        if not daily_content.strip():
            daily_content = self._store.load_daily()
        
        if daily_content.strip() and used_chars + len(daily_content) + 30 <= budget:
            sections.append("=== [每日记录] ===\n" + daily_content.strip())
            used_chars += len(daily_content) + 30

        # 6. AI总结（最低优先级，与档案/事实冲突时以档案为准）- 优先从对话级store读取
        summary_text = ""
        if conversation_store:
            conv_data = conversation_store.load_data()
            summary_text = summaries_to_markdown(conv_data)
        if not summary_text.strip():
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
