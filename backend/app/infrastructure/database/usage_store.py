import json
import os
import threading
from datetime import datetime, timezone
from loguru import logger
from app.core.config import settings


class UsageStore:
    def __init__(self):
        self._dir = os.path.join(settings.DATA_DIR, "store")
        os.makedirs(self._dir, exist_ok=True)
        self._path = os.path.join(self._dir, "usage_records.json")
        self._lock = threading.Lock()
        self._records: list[dict] | None = None

    def _load(self) -> list[dict]:
        if self._records is not None:
            return self._records
        if not os.path.exists(self._path):
            self._records = []
            return self._records
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                self._records = json.load(f)
                if not isinstance(self._records, list):
                    self._records = []
                return self._records
        except Exception as e:
            logger.warning(f"[UsageStore] Failed to load: {e}")
            self._records = []
            return self._records

    def _save(self):
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._records, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[UsageStore] Failed to save: {e}")

    def record(
        self,
        provider: str,
        model: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        agent_id: str | None = None,
        conv_id: str | None = None,
        is_stream: bool = False,
    ):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "provider": provider,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "agent_id": agent_id,
            "conv_id": conv_id,
            "is_stream": is_stream,
        }
        with self._lock:
            self._load()
            self._records.append(entry)
            if len(self._records) > 10000:
                self._records = self._records[-10000:]
            self._save()
        return entry

    def get_records(self, days: int | None = None) -> list[dict]:
        with self._lock:
            records = list(self._load())
        if days is None:
            return records
        cutoff = datetime.now(timezone.utc)
        from datetime import timedelta
        cutoff = cutoff - timedelta(days=days)
        cutoff_str = cutoff.isoformat()
        return [r for r in records if r.get("timestamp", "") >= cutoff_str]

    def get_summary(self, days: int | None = None) -> dict:
        records = self.get_records(days)
        total_requests = len(records)
        total_prompt = sum(r.get("prompt_tokens", 0) for r in records)
        total_completion = sum(r.get("completion_tokens", 0) for r in records)
        total_tokens = sum(r.get("total_tokens", 0) for r in records)

        by_provider: dict[str, dict] = {}
        for r in records:
            p = r.get("provider", "unknown")
            if p not in by_provider:
                by_provider[p] = {
                    "name": p,
                    "requests": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                }
            by_provider[p]["requests"] += 1
            by_provider[p]["prompt_tokens"] += r.get("prompt_tokens", 0)
            by_provider[p]["completion_tokens"] += r.get("completion_tokens", 0)
            by_provider[p]["total_tokens"] += r.get("total_tokens", 0)

        by_day: dict[str, int] = {}
        for r in records:
            ts = r.get("timestamp", "")
            if ts:
                day_key = ts[:10]
                by_day[day_key] = by_day.get(day_key, 0) + 1

        recent: list[dict] = []
        for r in reversed(records[-50:]):
            recent.append({
                "timestamp": r.get("timestamp", ""),
                "provider": r.get("provider", ""),
                "model": r.get("model", ""),
                "total_tokens": r.get("total_tokens", 0),
                "conv_id": r.get("conv_id"),
            })

        return {
            "total_requests": total_requests,
            "total_prompt_tokens": total_prompt,
            "total_completion_tokens": total_completion,
            "total_tokens": total_tokens,
            "by_provider": list(by_provider.values()),
            "by_day": by_day,
            "recent": recent[-20:],
        }


usage_store = UsageStore()
