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
        self._migrate_search_text()

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
            return None
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

        # 构建 search_text：拼接所有消息的 content
        search_parts = []
        for msg in conv.get("messages", []):
            content = msg.get("content", "")
            if isinstance(content, str) and content:
                search_parts.append(content)
        search_text = " ".join(search_parts)

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
                "search_text": search_text,
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

    def search_conversations(self, keyword: str, agent_id: str | None = None) -> list[dict]:
        """搜索对话：匹配标题和消息内容，返回匹配结果及关键词片段"""
        if not keyword or not keyword.strip():
            return []
        q = keyword.strip().lower()
        with self._lock:
            index = self._load_index()
        results = []
        for conv_id, meta in index.items():
            if agent_id and meta.get("agent_id") != agent_id:
                continue
            title = meta.get("title", "")
            search_text = meta.get("search_text", "")
            combined = (title + " " + search_text).lower()
            if q not in combined:
                continue
            # 提取匹配片段：在 search_text 中找到关键词，取前后 30 字
            snippet = ""
            src = search_text or title
            src_lower = src.lower()
            pos = src_lower.find(q)
            if pos >= 0:
                start = max(0, pos - 30)
                end = min(len(src), pos + len(q) + 30)
                snippet = src[start:end]
                if start > 0:
                    snippet = "..." + snippet
                if end < len(src):
                    snippet = snippet + "..."
            else:
                snippet = title
            results.append({
                "id": conv_id,
                "title": title,
                "snippet": snippet,
                "updated_at": meta.get("updated_at", ""),
            })
        results.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return results

    def _migrate_search_text(self):
        """为索引中缺少 search_text 的对话补全搜索文本"""
        with self._lock:
            index = self._load_index()
        needs_update = False
        for conv_id, meta in index.items():
            if "search_text" in meta and meta["search_text"]:
                continue
            # 从对话文件中读取消息，构建 search_text
            conv = self.get(conv_id)
            if not conv:
                continue
            search_parts = []
            for msg in conv.get("messages", []):
                content = msg.get("content", "")
                if isinstance(content, str) and content:
                    search_parts.append(content)
            meta["search_text"] = " ".join(search_parts)
            needs_update = True
        if needs_update:
            with self._lock:
                self._save_index()
            logger.info("[ConvStore] Migrated search_text for existing conversations")

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
