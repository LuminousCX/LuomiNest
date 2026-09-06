from datetime import datetime

from app.core.utils import utc_now_dt

from .models import FactItem, MemoryData, FACT_SCOPE_AGENT, FACT_SCOPE_CONVERSATION, summaries_to_markdown
from .store import MemoryStore
from .fact_manager import _extract_content_words


class ContextBuilder:
    """上下文组装：按预算优先级将记忆注入 LLM prompt。"""

    MAX_INJECTION_CHARS = 4000

    def __init__(self, store: MemoryStore):
        self._store = store
        # 向量召回返回的 fact ID 集合，用于下游相关性排序/聚合
        self._relevant_fact_ids: set[str] = set()

    def build_context(self, max_chars: int | None = None, query: str = "", conversation_store=None, conversation_id: str | None = None) -> str:
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

        # 3. 记忆事实（query-aware：优先注入与当前问题相关的事实）
        # 隔离靠"facts存在哪个store"决定：
        #   - Agent级store中的facts → 全局可见（蒸馏提升后的）
        #   - 对话级store中的facts → 仅当前对话可见（新提取的，待提升）
        all_facts = []
        # Agent级：全局可见的共享facts
        for f in data.facts:
            if not f.is_latest:
                continue
            if f.category not in FACT_SCOPE_AGENT:
                continue
            if f.expires_at:
                try:
                    exp_time = datetime.fromisoformat(f.expires_at.replace("Z", "+00:00"))
                    if exp_time <= utc_now_dt():
                        continue
                except (ValueError, TypeError):
                    pass
            all_facts.append(f)
        # 对话级：当前对话的所有facts都可见（包括待提升的Agent级类facts）
        if conversation_store:
            conv_data = conversation_store.load_data()
            for f in conv_data.facts:
                if not f.is_latest:
                    continue
                if f.expires_at:
                    try:
                        exp_time = datetime.fromisoformat(f.expires_at.replace("Z", "+00:00"))
                        if exp_time <= utc_now_dt():
                            continue
                    except (ValueError, TypeError):
                        pass
                all_facts.append(f)

        # query-aware 排序：优先使用向量召回结果，再用关键词匹配
        if self._relevant_fact_ids:
            # 使用向量召回的结果排序
            def vector_relevance(f: FactItem) -> float:
                if f.id in self._relevant_fact_ids:
                    return 1.0 + f.confidence * 0.1
                return f.confidence * 0.1
            all_facts.sort(key=vector_relevance, reverse=True)
        elif query:
            # 回退到关键词匹配
            query_words = _extract_content_words(query.casefold())
            if query_words:
                def fact_relevance(f: FactItem) -> float:
                    fact_words = _extract_content_words(f.content.casefold())
                    if not fact_words:
                        return 0.0
                    overlap = len(query_words & fact_words) / max(len(query_words | fact_words), 1)
                    return overlap + f.confidence * 0.1
                all_facts.sort(key=fact_relevance, reverse=True)
        else:
            all_facts.sort(key=lambda f: f.confidence, reverse=True)
        
        # 重置相关fact ID集合
        self._relevant_fact_ids = set()

        if all_facts:
            fact_lines = []
            truncated = False
            for fact in all_facts:
                line = f"- [{fact.category}|{fact.confidence:.1f}] {fact.content}"
                if fact.source_error:
                    line += f" (避免: {fact.source_error})"
                if used_chars + len(line) + 20 > budget:
                    truncated = True
                    break
                fact_lines.append(line)
                used_chars += len(line) + 1
            if fact_lines:
                header = "=== [记忆事实] ==="
                if truncated:
                    header += f" (共{len(all_facts)}条，按置信度截断显示前{len(fact_lines)}条)"
                sections.append(header + "\n" + "\n".join(fact_lines))

        # 4. 知识记忆 - 始终从Agent级store读取
        knowledge = self._store.load_knowledge()
        if knowledge.strip() and used_chars + len(knowledge) + 30 <= budget:
            sections.append("=== [知识记忆] ===\n" + knowledge.strip())
            used_chars += len(knowledge) + 30

        # 5. 每日记录 - 按conversation_id隔离读取
        daily_content = ""
        if conversation_id:
            daily_content = self._store.load_daily(conversation_id=conversation_id)
        else:
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
