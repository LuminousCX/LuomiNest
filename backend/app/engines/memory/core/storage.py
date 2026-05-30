import copy
import json
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from app.core.config import settings

from .models import (
    AgentMemory,
    MemoryData,
    MemoryFact,
    UserSpace,
    create_empty_agent_memory,
    create_empty_memory,
    create_empty_user_space,
    utc_now_iso_z,
)

_MAX_BACKUPS = 5


class MemoryStorage:
    def __init__(self, storage_path: Path | str | None = None):
        if storage_path:
            self._storage_path = Path(storage_path)
        else:
            self._storage_path = Path(settings.DATA_DIR) / "memory"
        self._storage_path.mkdir(parents=True, exist_ok=True)
        (self._storage_path / "agents").mkdir(parents=True, exist_ok=True)
        (self._storage_path / "backups").mkdir(parents=True, exist_ok=True)
        self._user_space_cache: tuple[UserSpace, float | None] | None = None
        self._agent_cache: dict[str, tuple[AgentMemory, float | None]] = {}
        self._legacy_cache: dict[str | None, tuple[MemoryData, float | None]] = {}
        self._lock = threading.RLock()

    @staticmethod
    def _safe_id(agent_id: str) -> str:
        return "".join(c if c.isalnum() or c in "-_" else "_" for c in agent_id)

    def _user_space_file(self) -> Path:
        return self._storage_path / "user_space.json"

    def _agent_memory_file(self, agent_id: str) -> Path:
        return self._storage_path / "agents" / f"{self._safe_id(agent_id)}.json"

    def _legacy_memory_file(self, agent_id: str | None = None) -> Path:
        if agent_id:
            return self._storage_path / f"memory_{self._safe_id(agent_id)}.json"
        return self._storage_path / "memory.json"

    def _get_mtime(self, file_path: Path) -> float | None:
        try:
            return file_path.stat().st_mtime if file_path.exists() else None
        except OSError:
            return None

    def _backup_file(self, file_path: Path) -> None:
        if not file_path.exists():
            return
        backup_dir = self._storage_path / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stem = file_path.stem
        suffix = file_path.suffix
        existing = sorted(backup_dir.glob(f"{stem}_*{suffix}"))
        while len(existing) >= _MAX_BACKUPS:
            existing[0].unlink()
            existing.pop(0)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        shutil.copy2(file_path, backup_dir / f"{stem}_{ts}{suffix}")

    def _atomic_write(self, file_path: Path, data: dict) -> None:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = file_path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        temp_path.replace(file_path)

    def load_user_space(self) -> UserSpace:
        with self._lock:
            file_path = self._user_space_file()
            current_mtime = self._get_mtime(file_path)
            if self._user_space_cache is not None:
                cached_data, cached_mtime = self._user_space_cache
                if cached_mtime == current_mtime:
                    return copy.deepcopy(cached_data)
            user_space = self._load_user_space_from_file()
            self._user_space_cache = (copy.deepcopy(user_space), current_mtime)
            return user_space

    def _load_user_space_from_file(self) -> UserSpace:
        file_path = self._user_space_file()
        if not file_path.exists():
            return create_empty_user_space()
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
            return UserSpace.from_dict(data)
        except Exception as e:
            logger.warning(f"[Memory] Failed to load user space: {e}")
            return create_empty_user_space()

    def save_user_space(self, user_space: UserSpace) -> bool:
        with self._lock:
            file_path = self._user_space_file()
            try:
                self._backup_file(file_path)
                user_space.last_updated = utc_now_iso_z()
                self._atomic_write(file_path, user_space.to_dict())
                mtime = self._get_mtime(file_path)
                self._user_space_cache = (copy.deepcopy(user_space), mtime)
                logger.info(f"[Memory] Saved user space to {file_path}")
                return True
            except Exception as e:
                logger.error(f"[Memory] Failed to save user space: {e}")
                return False

    def load_agent_memory(self, agent_id: str) -> AgentMemory:
        with self._lock:
            file_path = self._agent_memory_file(agent_id)
            current_mtime = self._get_mtime(file_path)
            cached = self._agent_cache.get(agent_id)
            if cached is not None and cached[1] == current_mtime:
                return copy.deepcopy(cached[0])
            agent_memory = self._load_agent_memory_from_file(agent_id)
            self._agent_cache[agent_id] = (copy.deepcopy(agent_memory), current_mtime)
            return agent_memory

    def _load_agent_memory_from_file(self, agent_id: str) -> AgentMemory:
        file_path = self._agent_memory_file(agent_id)
        if not file_path.exists():
            return create_empty_agent_memory(agent_id)
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
            return AgentMemory.from_dict(data)
        except Exception as e:
            logger.warning(f"[Memory] Failed to load agent memory for {agent_id}: {e}")
            return create_empty_agent_memory(agent_id)

    def save_agent_memory(self, agent_memory: AgentMemory, agent_id: str) -> bool:
        with self._lock:
            file_path = self._agent_memory_file(agent_id)
            try:
                self._backup_file(file_path)
                agent_memory.last_updated = utc_now_iso_z()
                agent_memory.agent_id = agent_id
                self._atomic_write(file_path, agent_memory.to_dict())
                mtime = self._get_mtime(file_path)
                self._agent_cache[agent_id] = (copy.deepcopy(agent_memory), mtime)
                logger.info(f"[Memory] Saved agent memory to {file_path}")
                return True
            except Exception as e:
                logger.error(f"[Memory] Failed to save agent memory: {e}")
                return False

    def load(self, agent_id: str | None = None) -> MemoryData:
        with self._lock:
            file_path = self._legacy_memory_file(agent_id)
            current_mtime = self._get_mtime(file_path)
            cached = self._legacy_cache.get(agent_id)
            if cached is not None and cached[1] == current_mtime:
                return copy.deepcopy(cached[0])
            memory_data = self._load_legacy_from_file(agent_id)
            self._legacy_cache[agent_id] = (copy.deepcopy(memory_data), current_mtime)
            return memory_data

    def _load_legacy_from_file(self, agent_id: str | None = None) -> MemoryData:
        file_path = self._legacy_memory_file(agent_id)
        if not file_path.exists():
            return create_empty_memory()
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
            return MemoryData.from_dict(data)
        except Exception as e:
            logger.warning(f"[Memory] Failed to load legacy memory: {e}")
            return create_empty_memory()

    def save(self, memory_data: MemoryData, agent_id: str | None = None) -> bool:
        with self._lock:
            file_path = self._legacy_memory_file(agent_id)
            try:
                self._backup_file(file_path)
                memory_data.last_updated = utc_now_iso_z()
                self._atomic_write(file_path, memory_data.to_dict())
                mtime = self._get_mtime(file_path)
                self._legacy_cache[agent_id] = (copy.deepcopy(memory_data), mtime)
                logger.info(f"[Memory] Saved memory to {file_path}")
                return True
            except Exception as e:
                logger.error(f"[Memory] Failed to save memory: {e}")
                return False

    def clear(self, agent_id: str | None = None) -> bool:
        with self._lock:
            if agent_id:
                empty_agent = create_empty_agent_memory(agent_id)
                if not self.save_agent_memory(empty_agent, agent_id):
                    return False
            else:
                empty_user = create_empty_user_space()
                if not self.save_user_space(empty_user):
                    return False
            empty_legacy = create_empty_memory()
            if not self.save(empty_legacy, agent_id):
                return False
            return True

    def clear_thread(self, thread_id: str, agent_id: str | None = None) -> bool:
        with self._lock:
            if agent_id:
                agent_memory = self.load_agent_memory(agent_id)
                agent_memory.working_memory.thread_conversations.pop(thread_id, None)
                agent_memory.working_memory.thread_core_goals.pop(thread_id, None)
                if not self.save_agent_memory(agent_memory, agent_id):
                    return False
            legacy = self.load(agent_id)
            legacy.working_memory.thread_conversations.pop(thread_id, None)
            legacy.working_memory.thread_core_goals.pop(thread_id, None)
            if not self.save(legacy, agent_id):
                return False
            return True

    def add_fact(
        self,
        content: str,
        category: str = "context",
        confidence: float = 0.5,
        agent_id: str | None = None,
        source: str = "manual",
    ) -> MemoryFact:
        with self._lock:
            fact = MemoryFact(
                content=content.strip(),
                category=category,
                confidence=confidence,
                source=source,
                layer="agent" if agent_id else "user",
            )
            if agent_id:
                agent_memory = self.load_agent_memory(agent_id)
                agent_memory.agent_facts.append(fact)
                if not self.save_agent_memory(agent_memory, agent_id):
                    raise RuntimeError("Failed to add fact: save operation failed")
            else:
                user_space = self.load_user_space()
                user_space.facts.append(fact)
                if not self.save_user_space(user_space):
                    raise RuntimeError("Failed to add fact: save operation failed")
            return fact

    def delete_fact(self, fact_id: str, agent_id: str | None = None) -> bool:
        with self._lock:
            if agent_id:
                agent_memory = self.load_agent_memory(agent_id)
                original_count = len(agent_memory.agent_facts)
                agent_memory.agent_facts = [
                    f for f in agent_memory.agent_facts if f.id != fact_id
                ]
                if len(agent_memory.agent_facts) == original_count:
                    raise ValueError(f"Fact with id '{fact_id}' not found")
                return self.save_agent_memory(agent_memory, agent_id)
            else:
                user_space = self.load_user_space()
                original_count = len(user_space.facts)
                user_space.facts = [f for f in user_space.facts if f.id != fact_id]
                if len(user_space.facts) == original_count:
                    raise ValueError(f"Fact with id '{fact_id}' not found")
                return self.save_user_space(user_space)

    def update_fact(
        self,
        fact_id: str,
        content: str | None = None,
        category: str | None = None,
        confidence: float | None = None,
        agent_id: str | None = None,
    ) -> bool:
        with self._lock:
            if agent_id:
                agent_memory = self.load_agent_memory(agent_id)
                found = False
                for i, fact in enumerate(agent_memory.agent_facts):
                    if fact.id == fact_id:
                        found = True
                        if content is not None:
                            fact.content = content.strip()
                        if category is not None:
                            fact.category = category
                        if confidence is not None:
                            fact.confidence = confidence
                        agent_memory.agent_facts[i] = fact
                        break
                if not found:
                    raise ValueError(f"Fact with id '{fact_id}' not found")
                return self.save_agent_memory(agent_memory, agent_id)
            else:
                user_space = self.load_user_space()
                found = False
                for i, fact in enumerate(user_space.facts):
                    if fact.id == fact_id:
                        found = True
                        if content is not None:
                            fact.content = content.strip()
                        if category is not None:
                            fact.category = category
                        if confidence is not None:
                            fact.confidence = confidence
                        user_space.facts[i] = fact
                        break
                if not found:
                    raise ValueError(f"Fact with id '{fact_id}' not found")
                return self.save_user_space(user_space)

    def load_shared_memory(self, agent_id: str | None = None) -> MemoryData:
        logger.warning(
            "[Memory] load_shared_memory is deprecated, "
            "use load_user_space / load_agent_memory instead"
        )
        return self.load(agent_id)


_storage_instance: MemoryStorage | None = None
_storage_lock = threading.Lock()


def get_memory_storage() -> MemoryStorage:
    global _storage_instance
    if _storage_instance is not None:
        return _storage_instance
    with _storage_lock:
        if _storage_instance is not None:
            return _storage_instance
        _storage_instance = MemoryStorage()
        return _storage_instance
