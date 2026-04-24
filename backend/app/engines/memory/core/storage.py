import json
import threading
from pathlib import Path
from typing import Any

from loguru import logger

from app.core.config import settings

from .models import MemoryData, create_empty_memory, utc_now_iso_z


class MemoryStorage:
    def __init__(self, storage_path: str | None = None):
        if storage_path:
            self._storage_path = Path(storage_path)
        else:
            self._storage_path = Path(settings.DATA_DIR) / "memory"
        self._storage_path.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str | None, tuple[MemoryData, float | None]] = {}
        self._lock = threading.RLock()

    def _get_memory_file(self, agent_id: str | None = None) -> Path:
        if agent_id:
            safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in agent_id)
            return self._storage_path / f"memory_{safe_id}.json"
        return self._storage_path / "memory.json"

    def _load_from_file(self, agent_id: str | None = None) -> MemoryData:
        file_path = self._get_memory_file(agent_id)
        if not file_path.exists():
            return create_empty_memory()
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
            return MemoryData.from_dict(data)
        except Exception as e:
            logger.warning(f"[Memory] Failed to load memory file: {e}")
            return create_empty_memory()

    def load(self, agent_id: str | None = None) -> MemoryData:
        with self._lock:
            file_path = self._get_memory_file(agent_id)
            try:
                current_mtime = file_path.stat().st_mtime if file_path.exists() else None
            except OSError:
                current_mtime = None

            cached = self._cache.get(agent_id)
            if cached is not None and cached[1] == current_mtime:
                return cached[0]

            memory_data = self._load_from_file(agent_id)
            self._cache[agent_id] = (memory_data, current_mtime)
            return memory_data

    def reload(self, agent_id: str | None = None) -> MemoryData:
        with self._lock:
            memory_data = self._load_from_file(agent_id)
            file_path = self._get_memory_file(agent_id)
            try:
                mtime = file_path.stat().st_mtime if file_path.exists() else None
            except OSError:
                mtime = None
            self._cache[agent_id] = (memory_data, mtime)
            return memory_data

    def save(self, memory_data: MemoryData, agent_id: str | None = None) -> bool:
        with self._lock:
            file_path = self._get_memory_file(agent_id)
            try:
                file_path.parent.mkdir(parents=True, exist_ok=True)
                memory_data.last_updated = utc_now_iso_z()
                temp_path = file_path.with_suffix(".tmp")
                with open(temp_path, "w", encoding="utf-8") as f:
                    json.dump(memory_data.to_dict(), f, ensure_ascii=False, indent=2)
                temp_path.replace(file_path)
                try:
                    mtime = file_path.stat().st_mtime
                except OSError:
                    mtime = None
                self._cache[agent_id] = (memory_data, mtime)
                logger.info(f"[Memory] Saved memory to {file_path}")
                return True
            except Exception as e:
                logger.error(f"[Memory] Failed to save memory: {e}")
                return False

    def clear(self, agent_id: str | None = None) -> MemoryData:
        with self._lock:
            empty = create_empty_memory()
            self.save(empty, agent_id)
            return empty

    def add_fact(
        self,
        content: str,
        category: str = "context",
        confidence: float = 0.5,
        agent_id: str | None = None,
        source: str = "manual",
        source_error: str | None = None,
    ) -> MemoryData:
        with self._lock:
            memory_data = self.load(agent_id)
            from .models import MemoryFact
            fact = MemoryFact(
                content=content.strip(),
                category=category,
                confidence=confidence,
                source=source,
                source_error=source_error,
            )
            memory_data.facts.append(fact)
            self.save(memory_data, agent_id)
            return memory_data

    def delete_fact(self, fact_id: str, agent_id: str | None = None) -> MemoryData:
        with self._lock:
            memory_data = self.load(agent_id)
            memory_data.facts = [f for f in memory_data.facts if f.id != fact_id]
            self.save(memory_data, agent_id)
            return memory_data

    def update_fact(
        self,
        fact_id: str,
        content: str | None = None,
        category: str | None = None,
        confidence: float | None = None,
        agent_id: str | None = None,
    ) -> MemoryData:
        with self._lock:
            memory_data = self.load(agent_id)
            for i, fact in enumerate(memory_data.facts):
                if fact.id == fact_id:
                    if content is not None:
                        fact.content = content.strip()
                    if category is not None:
                        fact.category = category
                    if confidence is not None:
                        fact.confidence = confidence
                    memory_data.facts[i] = fact
                    break
            self.save(memory_data, agent_id)
            return memory_data


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
