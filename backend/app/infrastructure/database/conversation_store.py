import json
import os
import threading
from datetime import datetime, timezone
from loguru import logger
from app.core.config import settings


class ConversationStore:
    def __init__(self):
        self._dir = os.path.join(settings.DATA_DIR, "conversations")
        os.makedirs(self._dir, exist_ok=True)
        self._index_path = os.path.join(self._dir, "_index.json")
        self._lock = threading.Lock()
        self._index_cache: dict | None = None

    def _load_index(self) -> dict:
        if self._index_cache is not None:
            return self._index_cache
        if not os.path.exists(self._index_path):
            self._index_cache = {}
            return self._index_cache
        try:
            with open(self._index_path, "r", encoding="utf-8") as f:
                self._index_cache = json.load(f)
                return self._index_cache
        except Exception as e:
            logger.warning(f"[ConvStore] Failed to load index: {e}")
            self._index_cache = {}
            return self._index_cache

    def _save_index(self):
        try:
            with open(self._index_path, "w", encoding="utf-8") as f:
                json.dump(self._index_cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[ConvStore] Failed to save index: {e}")

    def _conv_path(self, conv_id: str) -> str:
        safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in conv_id)
        return os.path.join(self._dir, f"{safe_id}.json")

    def get(self, conv_id: str) -> dict | None:
        path = self._conv_path(conv_id)
        if not os.path.exists(path):
            with self._lock:
                return self._load_index().get(conv_id)
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"[ConvStore] Failed to load conv {conv_id}: {e}")
            return None

    def set(self, conv_id: str, conv: dict):
        path = self._conv_path(conv_id)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(conv, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[ConvStore] Failed to save conv {conv_id}: {e}")
            return

        with self._lock:
            index = self._load_index()
            index[conv_id] = {
                "id": conv_id,
                "title": conv.get("title", "New Conversation"),
                "agent_id": conv.get("agent_id"),
                "model": conv.get("model"),
                "provider": conv.get("provider"),
                "last_message": (conv.get("messages", [{}])[-1].get("content", "")[:50]
                                 if conv.get("messages") else None),
                "created_at": conv.get("created_at", ""),
                "updated_at": conv.get("updated_at", ""),
            }
            self._save_index()

    def delete(self, conv_id: str):
        path = self._conv_path(conv_id)
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception as e:
                logger.error(f"[ConvStore] Failed to delete conv file {conv_id}: {e}")

        with self._lock:
            index = self._load_index()
            if conv_id in index:
                del index[conv_id]
                self._save_index()

    def items(self) -> list:
        with self._lock:
            return list(self._load_index().items())

    def values(self) -> list:
        with self._lock:
            return list(self._load_index().values())

    def count(self) -> int:
        with self._lock:
            return len(self._load_index())

    def list_conversations(self, agent_id: str | None = None) -> list[dict]:
        with self._lock:
            index = self._load_index()
        result = []
        for conv_id, meta in index.items():
            if agent_id and meta.get("agent_id") != agent_id:
                continue
            result.append(meta)
        result.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return result

    def migrate_from_json_store(self, old_store):
        old_data = old_store.list_all()
        if not old_data:
            return 0

        migrated = 0
        for conv_id, conv in old_data.items():
            if not isinstance(conv, dict):
                continue
            existing = self._conv_path(conv_id)
            if os.path.exists(existing):
                continue
            self.set(conv_id, conv)
            migrated += 1

        if migrated > 0:
            logger.success(f"[ConvStore] Migrated {migrated} conversations from old store")
        return migrated


conversation_store = ConversationStore()
