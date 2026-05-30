from __future__ import annotations

from loguru import logger

from .models import (
    UserSpace,
    AgentMemory,
    MemoryTier,
    TIER_SEARCH_WEIGHT,
    utc_now_iso_z,
    DistilledSection,
)


_LONG_TERM_DISTILL_PROMPT = """你是一个记忆蒸馏器。请将以下用户的长期偏好事实提炼为一段精炼摘要。

规则：
- 用第三人称（"用户喜欢..."而非"你喜欢..."）
- 保留所有关键信息，使其更紧凑
- 自然地将相关事实分组
- 不超过200字
- 不要添加事实中没有的信息
- 不要提及"记忆"或"事实"

待蒸馏的长期偏好事实：
{facts}

只输出摘要段落，不要输出其他内容。"""


_TEMPORARY_DISTILL_PROMPT = """你是一个记忆蒸馏器。请将以下用户的临时上下文事实提炼为一段精炼摘要。

规则：
- 用第三人称
- 保留所有关键信息，使其更紧凑
- 不超过100字
- 不要添加事实中没有的信息
- 不要提及"记忆"或"事实"

待蒸馏的临时上下文事实：
{facts}

只输出摘要段落，不要输出其他内容。"""


_EVENTS_TIMELINE_PROMPT = """你是一个记忆蒸馏器。请将以下情景事件提炼为一段时间线摘要。

规则：
- 按时间顺序组织
- 用第三人称
- 不超过150字
- 保留最重要的目标和结果
- 不要添加事件中没有的信息
- 不要提及"记忆"或"事实"

待蒸馏的情景事件：
{events}

只输出时间线摘要，不要输出其他内容。"""


_AGENT_DISTILL_PROMPT = """你是一个记忆蒸馏器。请将以下Agent的领域知识事实提炼为一段精炼摘要。

规则：
- 用第三人称
- 保留所有关键领域知识
- 不超过150字
- 不要添加事实中没有的信息
- 不要提及"记忆"或"事实"

待蒸馏的Agent领域事实：
{facts}

只输出摘要段落，不要输出其他内容。"""


class MemoryDistiller:

    async def distill_user_space(self, user_space: UserSpace, llm_adapter) -> DistilledSection:
        if len(user_space.facts) < 15:
            return user_space.distilled

        core_identity_facts = user_space.get_facts_by_tier("core_identity")
        long_term_facts = user_space.get_facts_by_tier("long_term_preference")
        temporary_facts = user_space.get_facts_by_tier("temporary_context")
        events = user_space.episodic_events

        core_identity_summary = ""
        if core_identity_facts:
            core_identity_summary = "\n".join(f"- {f.content}" for f in core_identity_facts)

        long_term_summary = ""
        if long_term_facts:
            facts_text = "\n".join(f"[{f.category}] {f.content}" for f in long_term_facts)
            try:
                response = await llm_adapter.chat(
                    messages=[{"role": "user", "content": _LONG_TERM_DISTILL_PROMPT.format(facts=facts_text)}],
                    temperature=0.3,
                    max_tokens=500,
                )
                long_term_summary = response.strip() if isinstance(response, str) else ""
            except Exception as e:
                logger.warning(f"[MemoryDistiller] Failed to distill long_term_preference: {e}")
                long_term_summary = user_space.distilled.long_term

        temporary_summary = ""
        if temporary_facts:
            facts_text = "\n".join(f"[{f.category}] {f.content}" for f in temporary_facts)
            try:
                response = await llm_adapter.chat(
                    messages=[{"role": "user", "content": _TEMPORARY_DISTILL_PROMPT.format(facts=facts_text)}],
                    temperature=0.3,
                    max_tokens=500,
                )
                temporary_summary = response.strip() if isinstance(response, str) else ""
            except Exception as e:
                logger.warning(f"[MemoryDistiller] Failed to distill temporary_context: {e}")
                temporary_summary = user_space.distilled.temporary

        events_timeline = ""
        if events:
            events_text = "\n".join(
                f"[{e.timestamp[:10]}] {e.core_goal} → {e.key_information}"
                for e in events
            )
            try:
                response = await llm_adapter.chat(
                    messages=[{"role": "user", "content": _EVENTS_TIMELINE_PROMPT.format(events=events_text)}],
                    temperature=0.3,
                    max_tokens=500,
                )
                events_timeline = response.strip() if isinstance(response, str) else ""
            except Exception as e:
                logger.warning(f"[MemoryDistiller] Failed to distill episodic_events: {e}")
                events_timeline = user_space.distilled.events_timeline

        distilled = DistilledSection(
            core_identity=core_identity_summary,
            long_term=long_term_summary,
            temporary=temporary_summary,
            events_timeline=events_timeline,
            updated_at=utc_now_iso_z(),
        )

        logger.info(
            f"[MemoryDistiller] Distilled user space: "
            f"core={len(core_identity_facts)}, long={len(long_term_facts)}, "
            f"temp={len(temporary_facts)}, events={len(events)}"
        )

        return distilled

    async def distill_agent_memory(self, agent_memory: AgentMemory, llm_adapter) -> str:
        if len(agent_memory.agent_facts) < 10:
            return agent_memory.domain_summary

        facts_text = "\n".join(f"[{f.category}] {f.content}" for f in agent_memory.agent_facts)

        try:
            response = await llm_adapter.chat(
                messages=[{"role": "user", "content": _AGENT_DISTILL_PROMPT.format(facts=facts_text)}],
                temperature=0.3,
                max_tokens=500,
            )
            summary = response.strip() if isinstance(response, str) else ""
            if summary:
                logger.info(
                    f"[MemoryDistiller] Distilled agent memory: "
                    f"{len(agent_memory.agent_facts)} facts -> {len(summary)} chars"
                )
                return summary
        except Exception as e:
            logger.warning(f"[MemoryDistiller] Failed to distill agent memory: {e}")

        return agent_memory.domain_summary
