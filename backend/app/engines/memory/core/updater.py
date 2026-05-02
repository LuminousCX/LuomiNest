import json
import re
from typing import Any

from loguru import logger

from app.runtime.provider.llm.adapter import llm_adapter

from .models import (
    MemoryData, MemoryFact, EpisodicEvent,
    FactCategory, MemoryTier, utc_now_iso_z,
    TIER_DEFAULT_CONFIDENCE,
)
from .storage import MemoryStorage


MEMORY_UPDATE_PROMPT = """You are a memory management system. Analyze the conversation and extract structured memory updates.

<current_memory>
{current_memory}
</current_memory>

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
1. Extract important information about the user from the conversation
2. For each new fact, provide:
   - content: The fact content (concise, in third person)
   - category: One of the categories above
   - tier: One of core_identity / long_term_preference / temporary_context
   - confidence: 0.0-1.0
3. If a new fact contradicts an existing one, use "correction" category
4. Ignore: file paths, URLs, timestamps, temporary error messages, code snippets
5. Ignore information about other people (focus on the user)
6. Also extract an episodic event if the conversation has a clear topic and outcome
7. DO NOT extract sensitive information (ID numbers, phone numbers, bank cards, passwords)
</instructions>

Output ONLY a JSON object:
{{
  "facts_to_add": [
    {{"content": "...", "category": "...", "tier": "...", "confidence": 0.8}}
  ],
  "fact_ids_to_remove": ["fact_xxx"],
  "episodic_event": {{
    "scene_tags": ["tag1", "tag2"],
    "core_goal": "what the user wanted",
    "key_information": "key details discussed",
    "final_result": "what was accomplished"
  }},
  "core_goal": "the user's primary intent in this conversation (one sentence)",
  "updates": {{
    "user_work_context": "optional summary",
    "user_personal_context": "optional summary",
    "user_top_of_mind": "optional summary"
  }}
}}

If no updates needed: {{"facts_to_add": [], "fact_ids_to_remove": [], "episodic_event": null, "core_goal": "", "updates": {{}}}}
"""

SENSITIVE_PATTERNS = [
    re.compile(r'\b\d{17}[\dXx]\b'),
    re.compile(r'\b1[3-9]\d{9}\b'),
    re.compile(r'\b\d{16,19}\b'),
    re.compile(r'(密码|口令|password|passwd|pwd)\s*[：:=]\s*\S+', re.IGNORECASE),
]


class MemoryUpdater:
    def __init__(self, storage: MemoryStorage, provider_name: str | None = None):
        self._storage = storage
        self._llm_adapter = llm_adapter
        self._provider_name = provider_name

    def _format_memory_for_prompt(self, memory_data: MemoryData) -> str:
        lines = []
        lines.append("=== User Context ===")
        if memory_data.user.work_context.summary:
            lines.append(f"Work: {memory_data.user.work_context.summary}")
        if memory_data.user.personal_context.summary:
            lines.append(f"Personal: {memory_data.user.personal_context.summary}")
        if memory_data.user.top_of_mind.summary:
            lines.append(f"Top of Mind: {memory_data.user.top_of_mind.summary}")

        lines.append("\n=== Facts ===")
        for fact in memory_data.facts[-30:]:
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
        for pattern in SENSITIVE_PATTERNS:
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

    async def update_from_conversation(
        self,
        messages: list[dict[str, Any]],
        thread_id: str,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        if not messages:
            return {"updated": False, "reason": "No messages to process"}

        memory_data = self._storage.load(agent_id)
        current_memory_str = self._format_memory_for_prompt(memory_data)
        conversation_str = self._format_conversation(messages)

        prompt = MEMORY_UPDATE_PROMPT.format(
            current_memory=current_memory_str,
            conversation=conversation_str,
        )

        try:
            response = await self._llm_adapter.chat(
                messages=[{"role": "user", "content": prompt}],
                provider_name=self._provider_name,
                temperature=0.3,
                max_tokens=1000,
            )
        except Exception as e:
            logger.error(f"[Memory] LLM call failed: {e}")
            return {"updated": False, "reason": str(e)}

        parsed = self._parse_llm_response(response)
        facts_added = 0
        facts_removed = 0
        updates_applied = {}

        facts_to_add = parsed.get("facts_to_add", [])
        for fact_data in facts_to_add:
            content = fact_data.get("content", "").strip()
            if not content or len(content) < 5:
                continue
            if self._should_skip_content(content):
                continue
            if self._is_duplicate_fact(content, memory_data.facts):
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

            new_fact = MemoryFact(
                content=content,
                category=category,
                tier=tier,
                confidence=confidence,
                source=thread_id,
            )

            removed_ids = memory_data.resolve_conflicts(new_fact)
            facts_removed += len(removed_ids)

            memory_data.facts.append(new_fact)
            facts_added += 1

        fact_ids_to_remove = parsed.get("fact_ids_to_remove", [])
        if fact_ids_to_remove:
            original_count = len(memory_data.facts)
            memory_data.facts = [
                f for f in memory_data.facts if f.id not in fact_ids_to_remove
            ]
            facts_removed += original_count - len(memory_data.facts)

        episodic_event_data = parsed.get("episodic_event")
        if episodic_event_data and isinstance(episodic_event_data, dict):
            scene_tags = episodic_event_data.get("scene_tags", [])
            core_goal = episodic_event_data.get("core_goal", "")
            if core_goal and scene_tags:
                event = EpisodicEvent(
                    conversation_id=thread_id,
                    agent_id=agent_id or "",
                    scene_tags=scene_tags[:5],
                    core_goal=core_goal[:200],
                    key_information=episodic_event_data.get("key_information", "")[:300],
                    final_result=episodic_event_data.get("final_result", "")[:200],
                )
                memory_data.episodic_events.append(event)
                if len(memory_data.episodic_events) > 100:
                    memory_data.episodic_events = memory_data.episodic_events[-100:]

        core_goal = parsed.get("core_goal", "")
        if core_goal and core_goal.strip():
            memory_data.working_memory.set_core_goal(core_goal.strip()[:200])

        memory_data.episodic_events = [
            e for e in memory_data.episodic_events
            if e.time_distance_days() < 180 or e.importance >= 0.8
        ]

        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if isinstance(content, list):
                content = " ".join(
                    c.get("text", "") if isinstance(c, dict) else str(c)
                    for c in content
                )
            content = str(content)[:300]
            if content:
                memory_data.working_memory.add_conversation(role, content)

        updates = parsed.get("updates", {})
        if updates.get("user_work_context"):
            memory_data.user.work_context.summary = updates["user_work_context"]
            memory_data.user.work_context.updated_at = utc_now_iso_z()
            updates_applied["work_context"] = updates["user_work_context"]
        if updates.get("user_personal_context"):
            memory_data.user.personal_context.summary = updates["user_personal_context"]
            memory_data.user.personal_context.updated_at = utc_now_iso_z()
            updates_applied["personal_context"] = updates["user_personal_context"]
        if updates.get("user_top_of_mind"):
            memory_data.user.top_of_mind.summary = updates["user_top_of_mind"]
            memory_data.user.top_of_mind.updated_at = utc_now_iso_z()
            updates_applied["top_of_mind"] = updates["user_top_of_mind"]

        memory_data.archive_expired_facts()

        if facts_added > 0 or facts_removed > 0 or updates_applied or episodic_event_data:
            self._storage.save(memory_data, agent_id)
            logger.info(
                f"[Memory] Updated: +{facts_added} facts, -{facts_removed} facts, "
                f"events={len(memory_data.episodic_events)}, "
                f"{len(updates_applied)} context updates"
            )
            return {
                "updated": True,
                "facts_added": facts_added,
                "facts_removed": facts_removed,
                "updates_applied": updates_applied,
            }

        return {"updated": False, "reason": "No changes needed"}
