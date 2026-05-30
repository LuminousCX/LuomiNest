from __future__ import annotations

import json
import re
from typing import Any

from loguru import logger

from .models import (
    UserSpace,
    AgentMemory,
    MemoryFact,
    EpisodicEvent,
    MemoryTier,
    FactCategory,
    TIER_DEFAULT_CONFIDENCE,
    TIER_SEARCH_WEIGHT,
    utc_now_iso_z,
)
from .storage import MemoryStorage, get_memory_storage
from .distiller import MemoryDistiller
from .event_bus import MemoryEventBus


_MEMORY_UPDATE_PROMPT = """You are a memory management system. Analyze the conversation and extract structured memory updates.

<current_user_facts>
{user_facts}
</current_user_facts>

<current_agent_facts>
{agent_facts}
</current_agent_facts>

<new_conversation>
{conversation}
</new_conversation>

<tier_definitions>
- core_identity: Permanent identity facts (name, occupation, core personality). Never decays. confidence=1.0
- long_term_preference: Stable preferences and habits (likes, dislikes, work style). Decays in 365 days. confidence=0.7
- temporary_context: Short-term goals and situations (current project, travel plans). Decays in 30 days. confidence=0.5
</tier_definitions>

<categories>
- preference: User preferences and likes/dislikes
- knowledge: Facts and information about the user
- context: Current situation or context
- behavior: User's typical behaviors or habits
- goal: User's goals or objectives
- correction: Corrections to previous memories
</categories>

<instructions>
1. Extract important information from the conversation
2. For each new fact, provide:
   - content: The fact content (concise, in third person)
   - category: One of the categories above
   - tier: One of core_identity / long_term_preference / temporary_context
   - confidence: 0.0-1.0
   - should_be_global: true if this fact applies to ALL agents (e.g., user name, core preferences), false if it's domain-specific
3. If a new fact contradicts an existing one, use "correction" category
4. Ignore: file paths, URLs, timestamps, temporary error messages, code snippets
5. Ignore information about other people (focus on the user)
6. Also extract an episodic event if the conversation has a clear topic and outcome
7. DO NOT extract sensitive information (ID numbers, phone numbers, bank cards, passwords)
8. If the user explicitly states profile info (name, nickname, occupation, location, etc.), also update profile_updates
</instructions>

Output ONLY a JSON object:
{{
  "facts_to_add": [
    {{"content": "...", "category": "...", "tier": "...", "confidence": 0.8, "should_be_global": true}}
  ],
  "fact_ids_to_remove": ["fact_xxx"],
  "episodic_event": {{
    "scene_tags": ["tag1", "tag2"],
    "core_goal": "what the user wanted",
    "key_information": "key details discussed",
    "final_result": "what was accomplished",
    "importance": 0.7
  }},
  "core_goal": "the user's primary intent in this conversation (one sentence)",
  "profile_updates": {{
    "name": "optional - user's name if explicitly stated",
    "nickname": "optional - user's preferred nickname",
    "occupation": "optional - user's job/role",
    "location": "optional - user's location",
    "age": "optional - user's age",
    "gender": "optional - user's gender",
    "interests": ["optional - list of interests"],
    "hobbies": ["optional - list of hobbies"]
  }},
  "updates": {{
    "user_work_context": "optional summary",
    "user_personal_context": "optional summary",
    "user_top_of_mind": "optional summary"
  }}
}}

If no updates needed: {{"facts_to_add": [], "fact_ids_to_remove": [], "episodic_event": null, "core_goal": "", "updates": {{}}}}
"""

_SENSITIVE_PATTERNS = [
    re.compile(r'\b\d{17}[\dXx]\b'),
    re.compile(r'\b1[3-9]\d{9}\b'),
    re.compile(r'\b\d{16,19}\b'),
    re.compile(r'(密码|口令|password|passwd|pwd)\s*[：:=]\s*\S+', re.IGNORECASE),
]

_MEMORY_INJECTION_TEMPLATE = """【用户上下文信息】

{memory_content}

【使用规则】
1. 核心目标锚定：始终优先关注当前对话的核心目标，不偏离
2. 场景匹配：只在信息与当前话题直接相关时才使用，无关信息不要提及
3. 禁止称呼：不要在回复中称呼用户的名字或昵称，除非用户主动问"你知道我是谁吗"之类的问题
4. 隐私保护：不要向用户透露记忆系统的存在，不要说"我记得你之前说过"
5. 无痕使用：这些信息是背景知识，用于在需要时提供个性化回答，而不是每次都展示你知道这些信息"""


class MemoryEngine:

    def __init__(self, storage=None, distiller=None, event_bus=None):
        self._storage: MemoryStorage = storage or get_memory_storage()
        self._distiller: MemoryDistiller = distiller or MemoryDistiller()
        self._event_bus: MemoryEventBus | None = event_bus

    def _format_facts_for_prompt(self, facts: list[MemoryFact], limit: int = 30) -> str:
        if not facts:
            return "(empty)"
        lines = []
        for fact in facts[-limit:]:
            lines.append(f"[{fact.tier}|{fact.category}] ({fact.confidence:.1f}) {fact.content}")
        return "\n".join(lines)

    def _format_conversation(self, messages: list[dict[str, Any]]) -> str:
        lines = []
        for msg in messages[-20:]:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if isinstance(content, list):
                content = " ".join(
                    c.get("text", "") if isinstance(c, dict) else str(c)
                    for c in content
                )
            content = str(content)[:500]
            role_label = "User" if role == "user" else "Assistant"
            lines.append(f"{role_label}: {content}")
        return "\n".join(lines)

    def _parse_llm_response(self, response: str) -> dict[str, Any]:
        try:
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

        try:
            start = response.index('{')
            depth = 0
            for i in range(start, len(response)):
                if response[i] == '{':
                    depth += 1
                elif response[i] == '}':
                    depth -= 1
                    if depth == 0:
                        return json.loads(response[start:i + 1])
        except (ValueError, json.JSONDecodeError):
            pass

        return {
            "facts_to_add": [],
            "fact_ids_to_remove": [],
            "episodic_event": None,
            "core_goal": "",
            "updates": {},
        }

    def _contains_sensitive_info(self, content: str) -> bool:
        for pattern in _SENSITIVE_PATTERNS:
            if pattern.search(content):
                return True
        return False

    def _is_duplicate_fact(self, content: str, existing_facts: list[MemoryFact]) -> bool:
        content_lower = content.strip().casefold()
        for fact in existing_facts:
            fact_lower = fact.content.strip().casefold()
            if fact_lower == content_lower:
                return True
            if len(content_lower) > 10 and len(fact_lower) > 10:
                if content_lower in fact_lower or fact_lower in content_lower:
                    return True
        return False

    def _should_skip_content(self, content: str) -> bool:
        skip_patterns = [
            r"^[/\\]",
            r"\.(txt|pdf|doc|png|jpg|jpeg|gif|mp3|mp4|wav)$",
            r"^[a-zA-Z]:\\",
            r"^https?://",
            r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}",
        ]
        content_stripped = content.strip()
        for pattern in skip_patterns:
            if re.search(pattern, content_stripped, re.IGNORECASE):
                return True
        if self._contains_sensitive_info(content_stripped):
            return True
        return False

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        other_chars = len(text) - chinese_chars
        return int(chinese_chars * 1.5 + other_chars * 0.25)

    async def update_from_conversation(
        self,
        messages: list[dict[str, Any]],
        thread_id: str,
        agent_id: str,
        llm_adapter,
    ) -> dict:
        if not messages:
            return {"updated": False, "reason": "No messages to process"}

        user_space = self._storage.load_user_space()
        agent_memory = self._storage.load_agent_memory(agent_id)

        user_facts_str = self._format_facts_for_prompt(user_space.facts)
        agent_facts_str = self._format_facts_for_prompt(agent_memory.agent_facts)
        conversation_str = self._format_conversation(messages)

        prompt = _MEMORY_UPDATE_PROMPT.format(
            user_facts=user_facts_str,
            agent_facts=agent_facts_str,
            conversation=conversation_str,
        )

        try:
            response = await llm_adapter.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1000,
            )
            if isinstance(response, dict):
                response = response.get("content", "")
        except Exception as e:
            logger.error(f"[MemoryEngine] LLM call failed: {e}")
            return {"updated": False, "reason": str(e)}

        parsed = self._parse_llm_response(response)

        facts_to_add = parsed.get("facts_to_add", [])
        if not isinstance(facts_to_add, list):
            facts_to_add = []
        fact_ids_to_remove = parsed.get("fact_ids_to_remove", [])
        if not isinstance(fact_ids_to_remove, list):
            fact_ids_to_remove = []
        updates = parsed.get("updates", {})
        if not isinstance(updates, dict):
            updates = {}

        global_facts_added = 0
        agent_facts_added = 0
        facts_removed = 0

        all_existing = user_space.facts + agent_memory.agent_facts

        for fact_data in facts_to_add:
            if not isinstance(fact_data, dict):
                continue
            content = fact_data.get("content", "").strip()
            if not content or len(content) < 5:
                continue
            if self._should_skip_content(content):
                continue
            if self._is_duplicate_fact(content, all_existing):
                continue

            category = fact_data.get("category", "context")
            if category not in ["preference", "knowledge", "context", "behavior", "goal", "correction"]:
                category = "context"

            tier = fact_data.get("tier", "temporary_context")
            if tier not in ["core_identity", "long_term_preference", "temporary_context"]:
                tier = "temporary_context"

            confidence = fact_data.get("confidence", None)
            if confidence is None:
                confidence = TIER_DEFAULT_CONFIDENCE.get(tier, 0.5)
            try:
                confidence = float(confidence)
                confidence = max(0.0, min(1.0, confidence))
            except (TypeError, ValueError):
                confidence = TIER_DEFAULT_CONFIDENCE.get(tier, 0.5)

            should_be_global = bool(fact_data.get("should_be_global", False))

            new_fact = MemoryFact(
                content=content,
                category=category,
                tier=tier,
                layer="user" if should_be_global else "agent",
                confidence=confidence,
                source=thread_id,
                source_agent_id=agent_id,
            )

            if should_be_global:
                removed_ids = user_space.resolve_conflicts(new_fact)
                facts_removed += len(removed_ids)
                user_space.facts.append(new_fact)
                global_facts_added += 1
            else:
                agent_memory.agent_facts.append(new_fact)
                agent_facts_added += 1

            all_existing.append(new_fact)

        if fact_ids_to_remove:
            original_user = len(user_space.facts)
            user_space.facts = [f for f in user_space.facts if f.id not in fact_ids_to_remove]
            facts_removed += original_user - len(user_space.facts)

            original_agent = len(agent_memory.agent_facts)
            agent_memory.agent_facts = [f for f in agent_memory.agent_facts if f.id not in fact_ids_to_remove]
            facts_removed += original_agent - len(agent_memory.agent_facts)

        episodic_event_data = parsed.get("episodic_event")
        if episodic_event_data and isinstance(episodic_event_data, dict):
            scene_tags = episodic_event_data.get("scene_tags", [])
            core_goal = episodic_event_data.get("core_goal", "")
            importance = episodic_event_data.get("importance", 0.5)
            try:
                importance = float(importance)
                importance = max(0.0, min(1.0, importance))
            except (TypeError, ValueError):
                importance = 0.5

            if core_goal and scene_tags:
                event = EpisodicEvent(
                    conversation_id=thread_id,
                    agent_id=agent_id,
                    scene_tags=scene_tags[:5],
                    core_goal=core_goal[:200],
                    key_information=episodic_event_data.get("key_information", "")[:300],
                    final_result=episodic_event_data.get("final_result", "")[:200],
                    importance=importance,
                )
                if importance >= 0.7:
                    user_space.episodic_events.append(event)
                    if len(user_space.episodic_events) > 100:
                        user_space.episodic_events = user_space.episodic_events[-100:]
                else:
                    agent_memory.agent_events.append(event)
                    if len(agent_memory.agent_events) > 100:
                        agent_memory.agent_events = agent_memory.agent_events[-100:]

        core_goal = parsed.get("core_goal", "")
        if core_goal and core_goal.strip():
            agent_memory.working_memory.set_core_goal_by_conversation(
                core_goal.strip()[:200], thread_id
            )

        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if isinstance(content, list):
                content = " ".join(
                    c.get("text", "") if isinstance(c, dict) else str(c)
                    for c in content
                )
            content = str(content)[:300]
            if not content:
                continue
            agent_memory.working_memory.add_conversation_for_thread(role, content, thread_id)

        if updates.get("user_work_context"):
            user_space.user.work_context.summary = updates["user_work_context"]
            user_space.user.work_context.updated_at = utc_now_iso_z()
        if updates.get("user_personal_context"):
            user_space.user.personal_context.summary = updates["user_personal_context"]
            user_space.user.personal_context.updated_at = utc_now_iso_z()
        if updates.get("user_top_of_mind"):
            user_space.user.top_of_mind.summary = updates["user_top_of_mind"]
            user_space.user.top_of_mind.updated_at = utc_now_iso_z()

        profile_updates = parsed.get("profile_updates", {})
        if isinstance(profile_updates, dict):
            profile = user_space.profile
            profile_changed = False
            for field in ["name", "nickname", "occupation", "location", "age", "gender"]:
                val = profile_updates.get(field)
                if val and isinstance(val, str) and val.strip():
                    setattr(profile, field, val.strip())
                    profile_changed = True
            for field in ["interests", "hobbies"]:
                val = profile_updates.get(field)
                if val and isinstance(val, list):
                    new_items = [str(v).strip() for v in val if str(v).strip()]
                    if new_items:
                        current = getattr(profile, field, []) or []
                        merged = list(dict.fromkeys(current + new_items))
                        setattr(profile, field, merged)
                        profile_changed = True
            if profile_changed:
                profile.updated_at = utc_now_iso_z()

        user_space.archive_expired_facts()

        self._storage.save_user_space(user_space)
        self._storage.save_agent_memory(agent_memory, agent_id)

        total_facts_added = global_facts_added + agent_facts_added

        if len(user_space.facts) >= 15:
            try:
                distilled = await self._distiller.distill_user_space(user_space, llm_adapter)
                user_space.distilled = distilled
                self._storage.save_user_space(user_space)
            except Exception as e:
                logger.warning(f"[MemoryEngine] User space distillation failed: {e}")

        if len(agent_memory.agent_facts) >= 10:
            try:
                domain_summary = await self._distiller.distill_agent_memory(agent_memory, llm_adapter)
                agent_memory.domain_summary = domain_summary
                self._storage.save_agent_memory(agent_memory, agent_id)
            except Exception as e:
                logger.warning(f"[MemoryEngine] Agent memory distillation failed: {e}")

        if self._event_bus:
            if global_facts_added > 0:
                await self._event_bus.publish("fact_added", agent_id, {
                    "layer": "user",
                    "count": global_facts_added,
                    "thread_id": thread_id,
                })
            if agent_facts_added > 0:
                await self._event_bus.publish("fact_added", agent_id, {
                    "layer": "agent",
                    "count": agent_facts_added,
                    "thread_id": thread_id,
                })

        logger.info(
            f"[MemoryEngine] Updated: +{global_facts_added} global, "
            f"+{agent_facts_added} agent, -{facts_removed} removed"
        )

        return {
            "updated": True,
            "facts_added": total_facts_added,
            "global_facts_added": global_facts_added,
            "agent_facts_added": agent_facts_added,
            "facts_removed": facts_removed,
        }

    async def inject_memory(
        self,
        messages: list[dict],
        agent_id: str,
        thread_id: str,
        model_context_window: int = 0,
        existing_msg_tokens: int = 0,
    ) -> list[dict]:
        if not messages:
            return messages

        user_space = self._storage.load_user_space()
        agent_memory = self._storage.load_agent_memory(agent_id)

        max_tokens = 2000
        if model_context_window and model_context_window > 0:
            available = max(0, model_context_window - existing_msg_tokens)
            if available == 0:
                return messages
            max_tokens = min(int(available * 0.15), 3000)

        sections = []
        total_tokens = 0

        core_goal = agent_memory.working_memory.get_core_goal_for(thread_id)
        if core_goal:
            section = f"=== 【当前对话核心目标】 ===\n{core_goal}"
            tokens = self._estimate_tokens(section)
            if total_tokens + tokens < max_tokens:
                sections.append(section)
                total_tokens += tokens

        distilled = user_space.distilled
        distilled_parts = []
        if distilled.core_identity:
            distilled_parts.append(f"核心身份: {distilled.core_identity}")
        if distilled.long_term:
            distilled_parts.append(f"长期偏好摘要: {distilled.long_term}")
        if distilled.temporary:
            distilled_parts.append(f"临时上下文摘要: {distilled.temporary}")
        if distilled.events_timeline:
            distilled_parts.append(f"事件时间线: {distilled.events_timeline}")
        if agent_memory.domain_summary:
            distilled_parts.append(f"领域知识摘要: {agent_memory.domain_summary}")
        if distilled_parts:
            section = "=== 【蒸馏摘要】 ===\n" + "\n".join(distilled_parts)
            tokens = self._estimate_tokens(section)
            if total_tokens + tokens < max_tokens:
                sections.append(section)
                total_tokens += tokens

        profile = user_space.profile
        profile_parts = []
        if profile.name:
            profile_parts.append(f"姓名: {profile.name}")
        if profile.nickname:
            profile_parts.append(f"昵称: {profile.nickname}")
        if profile.occupation:
            profile_parts.append(f"职业: {profile.occupation}")
        if profile.location:
            profile_parts.append(f"所在地: {profile.location}")
        if profile.interests:
            profile_parts.append(f"兴趣: {', '.join(profile.interests[:5])}")
        if profile.hobbies:
            profile_parts.append(f"爱好: {', '.join(profile.hobbies[:5])}")
        if profile_parts:
            section = "=== 【用户档案】 ===\n" + "\n".join(profile_parts)
            tokens = self._estimate_tokens(section)
            if total_tokens + tokens < max_tokens:
                sections.append(section)
                total_tokens += tokens

        long_term_facts = user_space.get_facts_by_tier("long_term_preference")
        if long_term_facts:
            lines = [f"- {f.content}" for f in long_term_facts[:5]]
            section = "=== 【长期偏好】 ===\n" + "\n".join(lines)
            tokens = self._estimate_tokens(section)
            if total_tokens + tokens < max_tokens:
                sections.append(section)
                total_tokens += tokens
                for f in long_term_facts[:5]:
                    f.record_access()

        temp_facts = user_space.get_facts_by_tier("temporary_context")
        if temp_facts:
            lines = [f"- {f.content}" for f in temp_facts[:5]]
            section = "=== 【临时上下文】 ===\n" + "\n".join(lines)
            tokens = self._estimate_tokens(section)
            if total_tokens + tokens < max_tokens:
                sections.append(section)
                total_tokens += tokens
                for f in temp_facts[:5]:
                    f.record_access()

        recent_convs = agent_memory.working_memory.get_conversations_for(thread_id)
        if recent_convs:
            recent = recent_convs[-3:]
            lines = []
            for conv in recent:
                role = "用户" if conv["role"] == "user" else "助手"
                lines.append(f"{role}: {conv['content'][:100]}")
            section = "=== 【最近对话摘要】 ===\n" + "\n".join(lines)
            tokens = self._estimate_tokens(section)
            if total_tokens + tokens < max_tokens:
                sections.append(section)
                total_tokens += tokens

        all_events = user_space.episodic_events + agent_memory.agent_events
        if all_events:
            all_events_sorted = sorted(all_events, key=lambda e: e.time_distance_days())
            lines = []
            for event in all_events_sorted[:3]:
                days_ago = event.time_distance_days()
                time_label = f"{days_ago}天前" if days_ago < 365 else f"{days_ago // 30}个月前"
                tags = ', '.join(event.scene_tags[:3]) if event.scene_tags else '一般'
                line = f"- [{time_label}|{tags}] {event.core_goal}"
                if event.key_information:
                    line += f" → {event.key_information[:80]}"
                lines.append(line)
            if lines:
                section = "=== 【相关历史事件】 ===\n" + "\n".join(lines)
                tokens = self._estimate_tokens(section)
                if total_tokens + tokens < max_tokens:
                    sections.append(section)
                    total_tokens += tokens

        if not sections:
            return messages

        memory_content = "\n\n".join(sections)
        system_content = _MEMORY_INJECTION_TEMPLATE.format(memory_content=memory_content)

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

    async def get_combined_view(self, agent_id: str) -> dict:
        user_space = self._storage.load_user_space()
        agent_memory = self._storage.load_agent_memory(agent_id)

        return {
            "user_space": user_space.to_dict(),
            "agent_memory": agent_memory.to_dict(),
        }

    async def search_facts(
        self, query: str, agent_id: str | None = None, top_k: int = 10
    ) -> list[MemoryFact]:
        user_space = self._storage.load_user_space()
        all_facts = list(user_space.facts)

        if agent_id:
            agent_memory = self._storage.load_agent_memory(agent_id)
            all_facts.extend(agent_memory.agent_facts)

        query_lower = query.lower()
        scored = []
        for fact in all_facts:
            content_lower = fact.content.lower()
            if query_lower in content_lower:
                weight = TIER_SEARCH_WEIGHT.get(fact.tier, 1.0)
                scored.append((fact, weight * 2.0))
                continue

            query_words = set(re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]{2,}', query_lower))
            content_words = set(re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]{2,}', content_lower))
            if query_words:
                overlap = query_words & content_words
                if overlap:
                    score = len(overlap) / len(query_words)
                    weight = TIER_SEARCH_WEIGHT.get(fact.tier, 1.0)
                    scored.append((fact, score * weight))

        scored.sort(key=lambda x: x[1], reverse=True)
        results = [fact for fact, _ in scored[:top_k]]
        for fact in results:
            fact.record_access()
        return results

    async def export_markdown(self, agent_id: str | None = None) -> str:
        user_space = self._storage.load_user_space()
        lines = ["# 用户记忆导出", ""]

        profile = user_space.profile
        if profile.name or profile.occupation or profile.location:
            lines.append("## 用户档案")
            if profile.name:
                lines.append(f"- 姓名: {profile.name}")
            if profile.nickname:
                lines.append(f"- 昵称: {profile.nickname}")
            if profile.occupation:
                lines.append(f"- 职业: {profile.occupation}")
            if profile.location:
                lines.append(f"- 所在地: {profile.location}")
            if profile.interests:
                lines.append(f"- 兴趣: {', '.join(profile.interests)}")
            if profile.hobbies:
                lines.append(f"- 爱好: {', '.join(profile.hobbies)}")
            lines.append("")

        if user_space.facts:
            lines.append("## 记忆事实")
            for tier in ["core_identity", "long_term_preference", "temporary_context"]:
                tier_facts = user_space.get_facts_by_tier(tier)
                if tier_facts:
                    lines.append(f"### {tier}")
                    for fact in tier_facts:
                        lines.append(
                            f"- [{fact.category}] {fact.content} (置信度: {fact.confidence:.1f})"
                        )
                    lines.append("")

        if user_space.episodic_events:
            lines.append("## 情景事件")
            for event in user_space.episodic_events:
                tags = ', '.join(event.scene_tags) if event.scene_tags else '一般'
                lines.append(f"- [{event.timestamp[:10]}|{tags}] {event.core_goal}")
                if event.key_information:
                    lines.append(f"  关键信息: {event.key_information}")
            lines.append("")

        if user_space.distilled.core_identity or user_space.distilled.long_term:
            lines.append("## 蒸馏摘要")
            if user_space.distilled.core_identity:
                lines.append(f"### 核心身份\n{user_space.distilled.core_identity}")
            if user_space.distilled.long_term:
                lines.append(f"### 长期偏好\n{user_space.distilled.long_term}")
            if user_space.distilled.temporary:
                lines.append(f"### 临时上下文\n{user_space.distilled.temporary}")
            if user_space.distilled.events_timeline:
                lines.append(f"### 事件时间线\n{user_space.distilled.events_timeline}")
            lines.append("")

        if agent_id:
            agent_memory = self._storage.load_agent_memory(agent_id)
            if agent_memory.agent_facts:
                lines.append("## Agent领域知识")
                for fact in agent_memory.agent_facts:
                    lines.append(
                        f"- [{fact.category}] {fact.content} (置信度: {fact.confidence:.1f})"
                    )
                lines.append("")
            if agent_memory.domain_summary:
                lines.append("## Agent领域摘要")
                lines.append(agent_memory.domain_summary)
                lines.append("")
            if agent_memory.agent_events:
                lines.append("## Agent情景事件")
                for event in agent_memory.agent_events:
                    tags = ', '.join(event.scene_tags) if event.scene_tags else '一般'
                    lines.append(f"- [{event.timestamp[:10]}|{tags}] {event.core_goal}")
                lines.append("")

        return "\n".join(lines)

    async def import_markdown(self, markdown_text: str, agent_id: str | None = None) -> dict:
        user_space = self._storage.load_user_space()
        agent_memory = self._storage.load_agent_memory(agent_id) if agent_id else None

        facts_imported = 0
        events_imported = 0
        agent_facts_imported = 0
        current_section = ""
        current_tier = ""

        for line in markdown_text.split("\n"):
            stripped = line.strip()
            if stripped.startswith("## "):
                current_section = stripped[3:].strip()
                current_tier = ""
            elif stripped.startswith("### "):
                sub = stripped[4:].strip()
                if sub in ["core_identity", "long_term_preference", "temporary_context"]:
                    current_tier = sub
                    current_section = "记忆事实"
            elif stripped.startswith("- [") and current_section == "记忆事实" and current_tier:
                bracket_end = stripped.find("]")
                if bracket_end < 0:
                    continue
                content_part = stripped[bracket_end + 1:].strip()
                category_match = re.match(
                    r'\[([^\]]+)\]\s*(.+?)(?:\s*\(置信度:\s*[\d.]+\))?\s*$', content_part
                )
                if category_match:
                    category = category_match.group(1)
                    content = category_match.group(2).strip()
                else:
                    content = content_part.strip()
                    category = "context"

                if content and len(content) >= 5:
                    if not self._is_duplicate_fact(content, user_space.facts):
                        valid_categories = [
                            "preference", "knowledge", "context",
                            "behavior", "goal", "correction",
                        ]
                        fact = MemoryFact(
                            content=content,
                            category=category if category in valid_categories else "context",
                            tier=current_tier,
                            layer="user",
                            source="import",
                        )
                        user_space.facts.append(fact)
                        facts_imported += 1

            elif stripped.startswith("- [") and current_section == "情景事件":
                bracket_end = stripped.find("]")
                if bracket_end < 0:
                    continue
                content_part = stripped[bracket_end + 1:].strip()
                if content_part:
                    event = EpisodicEvent(
                        core_goal=content_part[:200],
                    )
                    user_space.episodic_events.append(event)
                    events_imported += 1

            elif stripped.startswith("- [") and current_section == "Agent领域知识" and agent_memory:
                bracket_end = stripped.find("]")
                if bracket_end < 0:
                    continue
                content_part = stripped[bracket_end + 1:].strip()
                category_match = re.match(
                    r'\[([^\]]+)\]\s*(.+?)(?:\s*\(置信度:\s*[\d.]+\))?\s*$', content_part
                )
                if category_match:
                    category = category_match.group(1)
                    content = category_match.group(2).strip()
                else:
                    content = content_part.strip()
                    category = "context"

                if content and len(content) >= 5:
                    if not self._is_duplicate_fact(content, agent_memory.agent_facts):
                        valid_categories = [
                            "preference", "knowledge", "context",
                            "behavior", "goal", "correction",
                        ]
                        fact = MemoryFact(
                            content=content,
                            category=category if category in valid_categories else "context",
                            tier="long_term_preference",
                            layer="agent",
                            source="import",
                            source_agent_id=agent_id or "",
                        )
                        agent_memory.agent_facts.append(fact)
                        agent_facts_imported += 1

            elif stripped.startswith("- [") and current_section == "Agent情景事件" and agent_memory:
                bracket_end = stripped.find("]")
                if bracket_end < 0:
                    continue
                content_part = stripped[bracket_end + 1:].strip()
                if content_part:
                    event = EpisodicEvent(
                        core_goal=content_part[:200],
                        agent_id=agent_id or "",
                    )
                    agent_memory.agent_events.append(event)
                    events_imported += 1

        self._storage.save_user_space(user_space)
        if agent_memory and agent_facts_imported > 0:
            self._storage.save_agent_memory(agent_memory, agent_id)

        total_facts = facts_imported + agent_facts_imported
        logger.info(f"[MemoryEngine] Imported: {total_facts} facts, {events_imported} events")

        return {
            "imported": True,
            "facts_imported": total_facts,
            "events_imported": events_imported,
        }
