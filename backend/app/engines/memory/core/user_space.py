"""
全局用户记忆空间 — 跨 Agent 共享的用户身份、偏好、事实。

每个 Agent 读写自己的 working_memory（线程级隔离），
但 profile / facts / episodic_events / user_context 统一存入 user_memory.json。

调用方式：
    user_space = get_user_space()
    user_space.load() -> UserData
    user_space.merge_from(agent_memory) -> UserData  # Agent 发现新信息时合并进来
    user_space.snapshot_for(agent_id) -> MemoryData  # 给指定 Agent 返回一个只读快照
"""
from __future__ import annotations

import copy
import json
import threading
from pathlib import Path
from typing import Any

from loguru import logger

from app.core.config import settings

from .models import (
    MemoryData, MemoryFact, EpisodicEvent, UserContext, UserProfile,
    utc_now_iso_z, FactCategory, MemoryTier,
)


class UserData:
    """
    全局用户数据。与 MemoryData 结构对齐，但不含 working_memory（那部分是 Agent 私有的）。
    """

    def __init__(self):
        self.version: str = "2.0"
        self.last_updated: str = utc_now_iso_z()
        self.profile: UserProfile = UserProfile()
        self.facts: list[MemoryFact] = []
        self.episodic_events: list[EpisodicEvent] = []
        self.user_context: UserContext = UserContext()
        self.archived_facts: list[MemoryFact] = []

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "last_updated": self.last_updated,
            "profile": self.profile.model_dump(),
            "facts": [f.model_dump() for f in self.facts],
            "episodic_events": [e.model_dump() for e in self.episodic_events],
            "user_context": self.user_context.model_dump(),
            "archived_facts": [f.model_dump() for f in self.archived_facts],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UserData:
        ud = cls()
        ud.version = data.get("version", "2.0")
        ud.last_updated = data.get("last_updated", utc_now_iso_z())
        ud.profile = UserProfile.model_validate(data.get("profile", {}))
        ud.facts = [MemoryFact.model_validate(f) for f in data.get("facts", [])]
        ud.episodic_events = [EpisodicEvent.model_validate(e) for e in data.get("episodic_events", [])]
        ud.user_context = UserContext.model_validate(data.get("user_context", {}))
        ud.archived_facts = [MemoryFact.model_validate(f) for f in data.get("archived_facts", [])]
        return ud


class UserSpace:
    """
    全局用户记忆空间的管理器。

    存储路径: {DATA_DIR}/memory/user_memory.json
    线程安全，单例模式。
    """

    def __init__(self):
        self._file_path = Path(settings.DATA_DIR) / "memory" / "user_memory.json"
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._cache: UserData | None = None
        self._cache_mtime: float | None = None

    def load(self) -> UserData:
        with self._lock:
            if self._file_path.exists():
                try:
                    mtime = self._file_path.stat().st_mtime
                    if self._cache is not None and self._cache_mtime == mtime:
                        return copy.deepcopy(self._cache)
                except OSError:
                    pass

            if self._file_path.exists():
                try:
                    with open(self._file_path, encoding="utf-8") as f:
                        data = json.load(f)
                    ud = UserData.from_dict(data)
                    self._cache = copy.deepcopy(ud)
                    self._cache_mtime = self._file_path.stat().st_mtime
                    return ud
                except Exception as e:
                    logger.warning(f"[UserSpace] Failed to load: {e}")

            ud = UserData()
            self._cache = copy.deepcopy(ud)
            self._cache_mtime = None
            return ud

    def save(self, user_data: UserData) -> bool:
        with self._lock:
            try:
                user_data.last_updated = utc_now_iso_z()
                tmp = self._file_path.with_suffix(".tmp")
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(user_data.to_dict(), f, ensure_ascii=False, indent=2)
                tmp.replace(self._file_path)
                self._cache = copy.deepcopy(user_data)
                self._cache_mtime = self._file_path.stat().st_mtime
                logger.info("[UserSpace] Saved user memory")
                return True
            except Exception as e:
                logger.error(f"[UserSpace] Failed to save: {e}")
                return False

    def merge_from(self, agent_memory: MemoryData) -> dict[str, int]:
        """
        把一个 Agent 记忆中的 profile / facts / events / context 合并到全局。
        返回统计信息: {"facts_added": n, "facts_merged": n, "events_added": n, "profile_updated": bool}
        """
        user = self.load()
        stats = {"facts_added": 0, "facts_merged": 0, "events_added": 0, "profile_updated": False}

        # 1) Profile 合并（以非空字段覆盖）
        p = agent_memory.profile
        up = user.profile
        for field in ["name", "nickname", "age", "gender", "occupation", "location", "timezone", "language"]:
            val = getattr(p, field, "")
            if val and not getattr(up, field, ""):
                setattr(up, field, val)
                stats["profile_updated"] = True
        for lst_field in ["interests", "hobbies"]:
            existing = set(getattr(up, lst_field, []))
            for item in getattr(p, lst_field, []):
                if item and item not in existing:
                    getattr(up, lst_field).append(item)
                    existing.add(item)
                    stats["profile_updated"] = True
        for k, v in p.preferences.items():
            if k not in up.preferences:
                up.preferences[k] = v
                stats["profile_updated"] = True

        # 2) Facts 合并（按 content 去重，有冲突走 correction 逻辑）
        existing_contents = {f.content.strip().casefold(): f for f in user.facts}
        for fact in agent_memory.facts:
            key = fact.content.strip().casefold()
            if key in existing_contents:
                old = existing_contents[key]
                if fact.confidence > old.confidence:
                    old.confidence = fact.confidence
                    old.tier = fact.tier
                    stats["facts_merged"] += 1
            else:
                new_fact = fact.model_copy(deep=True)
                user.facts.append(new_fact)
                stats["facts_added"] += 1

        # 3) Episodic Events 合并（按 conversation_id 去重）
        existing_conv_ids = {e.conversation_id for e in user.episodic_events if e.conversation_id}
        for event in agent_memory.episodic_events:
            if event.conversation_id and event.conversation_id not in existing_conv_ids:
                user.episodic_events.append(event.model_copy(deep=True))
                existing_conv_ids.add(event.conversation_id)
                stats["events_added"] += 1

        # 4) UserContext 合并（非空覆盖）
        for section in ["work_context", "personal_context", "top_of_mind"]:
            agent_section = getattr(agent_memory.user, section, None)
            user_section = getattr(user.user_context, section, None)
            if agent_section and agent_section.summary and user_section and not user_section.summary:
                user_section.summary = agent_section.summary
                user_section.updated_at = agent_section.updated_at

        # 归档过期
        current_time = utc_now_iso_z()
        active = []
        for fact in user.facts:
            if fact.should_archive(current_time):
                user.archived_facts.append(fact)
            else:
                active.append(fact)
        user.facts = active

        # 事件上限
        if len(user.episodic_events) > 200:
            user.episodic_events = sorted(
                user.episodic_events, key=lambda e: e.importance, reverse=True
            )[:200]

        # facts 上限
        if len(user.facts) > 500:
            user.facts = sorted(
                user.facts, key=lambda f: f.confidence, reverse=True
            )[:500]

        self.save(user)
        logger.info(f"[UserSpace] Merged: {stats}")
        return stats

    def snapshot_for(self, agent_id: str | None = None) -> MemoryData:
        """
        生成一个只读的 MemoryData 快照，用于注入到 Agent 的上下文中。
        working_memory 部分由 Agent 自己管理，这里置空。
        """
        user = self.load()
        md = MemoryData()
        md.profile = copy.deepcopy(user.profile)
        md.facts = copy.deepcopy(user.facts)
        md.episodic_events = copy.deepcopy(user.episodic_events)
        md.user = copy.deepcopy(user.user_context)
        md.archived_facts = copy.deepcopy(user.archived_facts)
        md.last_updated = user.last_updated
        return md


_user_space_instance: UserSpace | None = None
_user_space_lock = threading.Lock()


def get_user_space() -> UserSpace:
    global _user_space_instance
    if _user_space_instance is not None:
        return _user_space_instance
    with _user_space_lock:
        if _user_space_instance is not None:
            return _user_space_instance
        _user_space_instance = UserSpace()
        return _user_space_instance
