import json
from pathlib import Path

from loguru import logger

from app.core.config import settings

from .models import (
    EpisodicEvent,
    MemoryData,
    MemoryFact,
    UserContext,
    History,
    UserProfile,
    create_empty_agent_memory,
    create_empty_user_space,
)
from .storage import get_memory_storage


def _count_profile_fields(profile: UserProfile) -> int:
    count = sum(1 for f in [
        profile.name, profile.nickname, profile.age, profile.gender,
        profile.occupation, profile.location, profile.timezone,
        profile.language, profile.notes,
    ] if f)
    if profile.interests:
        count += 1
    if profile.hobbies:
        count += 1
    if profile.preferences:
        count += 1
    return count


def _count_context_fields(ctx: UserContext) -> int:
    return sum(
        1 for s in [ctx.work_context, ctx.personal_context, ctx.top_of_mind]
        if s.summary
    )


def _count_history_fields(history: History) -> int:
    return sum(
        1 for s in [history.recent_months, history.earlier_context, history.long_term_background]
        if s.summary
    )


def _merge_profiles(base: UserProfile, incoming: UserProfile) -> UserProfile:
    if _count_profile_fields(incoming) > _count_profile_fields(base):
        return incoming
    return base


def _merge_user_context(base: UserContext, incoming: UserContext) -> UserContext:
    if _count_context_fields(incoming) > _count_context_fields(base):
        return incoming
    return base


def _merge_history(base: History, incoming: History) -> History:
    if _count_history_fields(incoming) > _count_history_fields(base):
        return incoming
    return base


def _ensure_facts_layer(raw_data: dict) -> dict:
    for fact in raw_data.get("facts", []):
        if "layer" not in fact or not fact["layer"]:
            fact["layer"] = "user"
    for fact in raw_data.get("archived_facts", []):
        if "layer" not in fact or not fact["layer"]:
            fact["layer"] = "user"
    return raw_data


def _dedup_facts(facts: list[MemoryFact]) -> list[MemoryFact]:
    seen: dict[str, MemoryFact] = {}
    for fact in facts:
        key = fact.content.casefold()
        if key in seen:
            if fact.confidence > seen[key].confidence:
                seen[key] = fact
        else:
            seen[key] = fact
    return list(seen.values())


def _dedup_events(events: list[EpisodicEvent]) -> list[EpisodicEvent]:
    seen: set[str] = set()
    result: list[EpisodicEvent] = []
    for event in events:
        key = f"{event.core_goal.casefold()}|{event.key_information.casefold()}"
        if key not in seen:
            seen.add(key)
            result.append(event)
    return result


async def migrate_v2_to_v3() -> dict:
    storage = get_memory_storage()
    memory_dir = Path(settings.DATA_DIR) / "memory"

    if not memory_dir.exists():
        logger.info("[Migration] Memory directory does not exist, nothing to migrate")
        return {"files_scanned": 0, "agents_migrated": 0, "facts_merged": 0, "events_merged": 0}

    legacy_files = sorted(memory_dir.glob("memory_*.json"))

    if not legacy_files:
        logger.info("[Migration] No legacy memory files found")
        return {"files_scanned": 0, "agents_migrated": 0, "facts_merged": 0, "events_merged": 0}

    user_space = create_empty_user_space()
    agents_migrated = 0

    for file_path in legacy_files:
        logger.info(f"[Migration] Processing {file_path.name}")

        try:
            with open(file_path, encoding="utf-8") as f:
                raw_data = json.load(f)
            _ensure_facts_layer(raw_data)
            memory_data = MemoryData.from_dict(raw_data)
        except Exception as e:
            logger.error(f"[Migration] Failed to load {file_path.name}: {e}")
            continue

        stem = file_path.stem
        agent_id = stem[len("memory_"):]

        user_space.profile = _merge_profiles(user_space.profile, memory_data.profile)
        user_space.user = _merge_user_context(user_space.user, memory_data.user)
        user_space.history = _merge_history(user_space.history, memory_data.history)

        user_space.facts.extend(memory_data.facts)
        user_space.episodic_events.extend(memory_data.episodic_events)
        user_space.archived_facts.extend(memory_data.archived_facts)

        agent_memory = create_empty_agent_memory(agent_id)
        agent_memory.working_memory = memory_data.working_memory
        storage.save_agent_memory(agent_memory, agent_id)
        agents_migrated += 1

        logger.info(
            f"[Migration] Migrated agent {agent_id}: "
            f"{len(memory_data.facts)} facts, {len(memory_data.episodic_events)} events"
        )

    user_space.facts = _dedup_facts(user_space.facts)
    user_space.episodic_events = _dedup_events(user_space.episodic_events)
    user_space.archived_facts = _dedup_facts(user_space.archived_facts)

    storage.save_user_space(user_space)

    stats = {
        "files_scanned": len(legacy_files),
        "agents_migrated": agents_migrated,
        "facts_merged": len(user_space.facts),
        "events_merged": len(user_space.episodic_events),
    }

    logger.info(
        f"[Migration] Complete: {stats['files_scanned']} files, "
        f"{stats['agents_migrated']} agents, "
        f"{stats['facts_merged']} unique facts, "
        f"{stats['events_merged']} unique events"
    )

    return stats
