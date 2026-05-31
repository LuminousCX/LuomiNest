import json
import os
import threading
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from app.core.config import settings


class PlatformLogEntry:
    __slots__ = ("id", "timestamp", "level", "event", "message", "instance_id", "adapter_type", "details")

    def __init__(
        self,
        id: str,
        timestamp: str,
        level: str,
        event: str,
        message: str,
        instance_id: str = "",
        adapter_type: str = "",
        details: dict[str, Any] | None = None,
    ):
        self.id = id
        self.timestamp = timestamp
        self.level = level
        self.event = event
        self.message = message
        self.instance_id = instance_id
        self.adapter_type = adapter_type
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "level": self.level,
            "event": self.event,
            "message": self.message,
            "instance_id": self.instance_id,
            "adapter_type": self.adapter_type,
            "details": self.details,
        }


class PlatformLogger:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._dir = os.path.join(settings.DATA_DIR, "platform_logs")
        os.makedirs(self._dir, exist_ok=True)
        self._index_path = os.path.join(self._dir, "_index.json")
        self._file_lock = threading.Lock()
        self._cache: dict[str, list[dict]] = {}
        self._max_entries_per_instance = 2000
        self._load_index()

    def _load_index(self):
        if os.path.exists(self._index_path):
            try:
                with open(self._index_path, "r", encoding="utf-8") as f:
                    self._index = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._index = {}
        else:
            self._index = {}

    def _save_index(self):
        try:
            with open(self._index_path, "w", encoding="utf-8") as f:
                json.dump(self._index, f, ensure_ascii=False, indent=2)
        except OSError as e:
            logger.error(f"[PlatformLogger] Failed to save index: {e}")

    def _get_log_path(self, instance_id: str) -> str:
        return os.path.join(self._dir, f"{instance_id}.json")

    def _load_logs(self, instance_id: str) -> list[dict]:
        if instance_id in self._cache:
            return self._cache[instance_id]
        path = self._get_log_path(instance_id)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    logs = json.load(f)
                self._cache[instance_id] = logs
                return logs
            except (json.JSONDecodeError, OSError):
                self._cache[instance_id] = []
                return []
        self._cache[instance_id] = []
        return []

    def _save_logs(self, instance_id: str, logs: list[dict]):
        path = self._get_log_path(instance_id)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(logs, f, ensure_ascii=False, indent=2)
            self._cache[instance_id] = logs
        except OSError as e:
            logger.error(f"[PlatformLogger] Failed to save logs for {instance_id}: {e}")

    def log(
        self,
        instance_id: str,
        level: str,
        event: str,
        message: str,
        adapter_type: str = "",
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        import uuid

        entry = {
            "id": str(uuid.uuid4())[:8],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "event": event,
            "message": message,
            "instance_id": instance_id,
            "adapter_type": adapter_type,
            "details": details or {},
        }

        with self._file_lock:
            logs = self._load_logs(instance_id)
            logs.append(entry)
            if len(logs) > self._max_entries_per_instance:
                logs = logs[-self._max_entries_per_instance:]
            self._save_logs(instance_id, logs)

            if instance_id not in self._index:
                self._index[instance_id] = {
                    "adapter_type": adapter_type,
                    "total_entries": 0,
                    "first_log": entry["timestamp"],
                    "last_log": entry["timestamp"],
                }
            self._index[instance_id]["total_entries"] = len(logs)
            self._index[instance_id]["last_log"] = entry["timestamp"]
            self._save_index()

        loguru_fn = getattr(logger, level, logger.info)
        loguru_fn(f"[PlatformLogger] [{adapter_type or instance_id}] [{event}] {message}")

        return entry

    def get_logs(
        self,
        instance_id: str,
        level: str | None = None,
        event: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        with self._file_lock:
            logs = self._load_logs(instance_id)

        if level:
            logs = [l for l in logs if l.get("level") == level]
        if event:
            logs = [l for l in logs if l.get("event") == event]

        total = len(logs)
        logs = logs[::-1]
        logs = logs[offset:offset + limit]

        return {
            "entries": logs,
            "total": total,
        }

    def get_all_logs(
        self,
        level: str | None = None,
        event: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> dict[str, Any]:
        all_entries: list[dict] = []
        with self._file_lock:
            for instance_id in list(self._index.keys()):
                logs = self._load_logs(instance_id)
                all_entries.extend(logs)

        all_entries.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        if level:
            all_entries = [e for e in all_entries if e.get("level") == level]
        if event:
            all_entries = [e for e in all_entries if e.get("event") == event]

        total = len(all_entries)
        entries = all_entries[offset:offset + limit]

        return {
            "entries": entries,
            "total": total,
        }

    def clear_logs(self, instance_id: str) -> bool:
        with self._file_lock:
            path = self._get_log_path(instance_id)
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    return False
            self._cache.pop(instance_id, None)
            self._index.pop(instance_id, None)
            self._save_index()
        return True

    def get_summary(self) -> dict[str, Any]:
        total_entries = sum(idx.get("total_entries", 0) for idx in self._index.values())
        instances = len(self._index)
        by_level = {"info": 0, "success": 0, "warning": 0, "error": 0}
        for instance_id in self._index:
            with self._file_lock:
                logs = self._load_logs(instance_id)
            for l in logs[-500:]:
                lvl = l.get("level", "info")
                if lvl in by_level:
                    by_level[lvl] += 1
        return {
            "totalEntries": total_entries,
            "totalInstances": instances,
            "byLevel": by_level,
        }


platform_logger = PlatformLogger()
