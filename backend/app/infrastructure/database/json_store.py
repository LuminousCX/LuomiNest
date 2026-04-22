import json
import os
import threading
from datetime import datetime, timezone
from loguru import logger
from app.core.config import settings


class JsonStore:
    def __init__(self, filename: str):
        self._dir = os.path.join(settings.DATA_DIR, "store")
        os.makedirs(self._dir, exist_ok=True)
        self._path = os.path.join(self._dir, filename)
        self._lock = threading.Lock()
        self._cache: dict | None = None

    def _load(self) -> dict:
        if self._cache is not None:
            return self._cache
        if not os.path.exists(self._path):
            self._cache = {}
            return self._cache
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                self._cache = json.load(f)
                return self._cache
        except Exception as e:
            logger.warning(f"[Store] Failed to load {self._path}: {e}")
            self._cache = {}
            return self._cache

    def _save(self):
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[Store] Failed to save {self._path}: {e}")

    def get(self, key: str, default=None):
        with self._lock:
            return self._load().get(key, default)

    def set(self, key: str, value):
        with self._lock:
            data = self._load()
            data[key] = value
            self._save()

    def delete(self, key: str):
        with self._lock:
            data = self._load()
            if key in data:
                del data[key]
                self._save()

    def list_all(self) -> dict:
        with self._lock:
            return dict(self._load())

    def values(self) -> list:
        with self._lock:
            return list(self._load().values())

    def items(self) -> list:
        with self._lock:
            return list(self._load().items())

    def count(self) -> int:
        with self._lock:
            return len(self._load())

    def clear(self):
        with self._lock:
            self._cache = {}
            self._save()

    def update(self, key: str, updates: dict):
        with self._lock:
            data = self._load()
            if key in data and isinstance(data[key], dict):
                data[key].update(updates)
                data[key]["updated_at"] = datetime.now(timezone.utc).isoformat()
                self._save()
            elif key in data:
                data[key] = updates
                self._save()

    def invalidate(self):
        self._cache = None


agents_store = JsonStore("agents.json")
conversations_store = JsonStore("conversations.json")
groups_store = JsonStore("groups.json")
skills_store = JsonStore("skills.json")
mcp_servers_store = JsonStore("mcp_servers.json")
