import json
import re
from typing import Any

from loguru import logger

from app.runtime.provider.llm.adapter import llm_adapter

from .models import MemoryData, MemoryFact, FactCategory, utc_now_iso_z
from .storage import MemoryStorage


MEMORY_UPDATE_PROMPT = """You are a memory management system. Analyze the conversation and update the user's memory profile.

<current_memory>
{current_memory}
</current_memory>

<new_conversation>
{conversation}
</new_conversation>

<categories>
- preference: User preferences and likes/dislikes
- knowledge: Facts and information about the user
- context: Current situation or context
- behavior: User's typical behaviors or habits
- goal: User's goals or objectives
- correction: Corrections to previous memories
</categories>

<instructions>
1. Analyze the conversation for important information about the user
2. Extract relevant facts, preferences, and context
3. For each new fact, provide:
   - content: The fact content (concise, in third person)
   - category: One of the categories above
   - confidence: 0.0-1.0 (how certain is this fact)
4. If a new fact contradicts an existing one, use "correction" category
5. Ignore temporary information (file paths, timestamps, etc.)
6. Ignore information about other people (focus on the user)
</instructions>

Output ONLY a JSON object with this structure:
{{
  "facts_to_add": [
    {{"content": "...", "category": "...", "confidence": 0.8}}
  ],
  "fact_ids_to_remove": ["fact_xxx"],
  "updates": {{
    "user_work_context": "optional summary",
    "user_personal_context": "optional summary",
    "user_top_of_mind": "optional summary"
  }}
}}

If no updates needed, output: {{"facts_to_add": [], "fact_ids_to_remove": [], "updates": {{}}}}
"""


class MemoryUpdater:
    def __init__(self, storage: MemoryStorage):
        self._storage = storage
        self._llm_adapter = llm_adapter

    def _format_memory_for_prompt(self, memory_data: MemoryData) -> str:
        lines = []
        lines.append("=== User Context ===")
        if memory_data.user.work_context.summary:
            lines.append(f"Work: {memory_data.user.work_context.summary}")
        if memory_data.user.personal_context.summary:
            lines.append(f"Personal: {memory_data.user.personal_context.summary}")
        if memory_data.user.top_of_mind.summary:
            lines.append(f"Top of Mind: {memory_data.user.top_of_mind.summary}")

        lines.append("\n=== History ===")
        if memory_data.history.recent_months.summary:
            lines.append(f"Recent: {memory_data.history.recent_months.summary}")
        if memory_data.history.earlier_context.summary:
            lines.append(f"Earlier: {memory_data.history.earlier_context.summary}")
        if memory_data.history.long_term_background.summary:
            lines.append(f"Background: {memory_data.history.long_term_background.summary}")

        lines.append("\n=== Facts ===")
        for fact in memory_data.facts[-30:]:
            lines.append(f"[{fact.category}] ({fact.confidence:.1f}) {fact.content}")

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
            json_match = re.search(r"\{[\s\S]*\}", response)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
        return {"facts_to_add": [], "fact_ids_to_remove": [], "updates": {}}

    def _is_duplicate_fact(self, content: str, existing_facts: list[MemoryFact]) -> bool:
        content_lower = content.strip().casefold()
        for fact in existing_facts:
            if fact.content.strip().casefold() == content_lower:
                return True
            if content_lower in fact.content.casefold() or fact.content.casefold() in content_lower:
                if len(content_lower) > 20 or len(fact.content) > 20:
                    return True
        return False

    def _should_skip_content(self, content: str) -> bool:
        skip_patterns = [
            r"^[/\\]",  # File paths
            r"\.(txt|pdf|doc|png|jpg|jpeg|gif|mp3|mp4|wav)$",  # File extensions
            r"^[a-zA-Z]:\\",  # Windows paths
            r"^https?://",  # URLs
            r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}",  # Timestamps
        ]
        content_stripped = content.strip()
        for pattern in skip_patterns:
            if re.search(pattern, content_stripped, re.IGNORECASE):
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

            confidence = fact_data.get("confidence", 0.5)
            try:
                confidence = float(confidence)
                confidence = max(0.0, min(1.0, confidence))
            except (TypeError, ValueError):
                confidence = 0.5

            new_fact = MemoryFact(
                content=content,
                category=category,
                confidence=confidence,
                source=thread_id,
            )
            memory_data.facts.append(new_fact)
            facts_added += 1

        fact_ids_to_remove = parsed.get("fact_ids_to_remove", [])
        if fact_ids_to_remove:
            original_count = len(memory_data.facts)
            memory_data.facts = [
                f for f in memory_data.facts if f.id not in fact_ids_to_remove
            ]
            facts_removed = original_count - len(memory_data.facts)

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

        if facts_added > 0 or facts_removed > 0 or updates_applied:
            self._storage.save(memory_data, agent_id)
            logger.info(
                f"[Memory] Updated: +{facts_added} facts, -{facts_removed} facts, "
                f"{len(updates_applied)} context updates"
            )
            return {
                "updated": True,
                "facts_added": facts_added,
                "facts_removed": facts_removed,
                "updates_applied": updates_applied,
            }

        return {"updated": False, "reason": "No changes needed"}
