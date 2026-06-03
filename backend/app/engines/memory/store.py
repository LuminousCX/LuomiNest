import json
import re
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from app.core.config import settings
from .models import MemoryData, _SUMMARY_SECTION_MAP


class MemoryStore:
    """纯存储层：文件读写、缓存、线程锁、格式迁移。"""

    def __init__(self, storage_path: Path):
        self._path = Path(storage_path)
        self._path.mkdir(parents=True, exist_ok=True)
        (self._path / "daily").mkdir(exist_ok=True)
        self._lock = threading.RLock()
        self._cache: MemoryData | None = None
        self._auto_migrate()

    def _memory_file(self) -> Path:
        return self._path / "memory.json"

    def _knowledge_file(self) -> Path:
        return self._path / "knowledge.md"

    def _daily_file(self, date: str | None = None) -> Path:
        if date is None:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self._path / "daily" / f"{date}.md"

    def _read(self, path: Path) -> str:
        if not path.exists():
            return ""
        try:
            return path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"[Memory] Failed to read {path}: {e}")
            return ""

    def _write(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(path)
        logger.info(f"[Memory] Written {path}")

    # --- 格式迁移 ---

    def _auto_migrate(self) -> None:
        if self._memory_file().exists():
            return

        old_memory = self._path / "MEMORY.md"
        old_summary = self._path / "summary.md"

        if not old_memory.exists() and not old_summary.exists():
            return

        logger.info("[Memory] Auto-migrating from old format...")
        try:
            data = MemoryData()

            if old_memory.exists():
                content = old_memory.read_text(encoding="utf-8")
                name_match = re.search(
                    r"(?:姓名|name|Name)[：:]\s*(.+)", content, re.IGNORECASE
                )
                if name_match:
                    data.profile.name = name_match.group(1).strip()
                    data.profile.updated_at = datetime.now(timezone.utc).isoformat()

            if old_summary.exists():
                content = old_summary.read_text(encoding="utf-8")
                now = datetime.now(timezone.utc).isoformat()
                for cn_name, attr_name in _SUMMARY_SECTION_MAP.items():
                    pattern = rf"##\s*{re.escape(cn_name)}\s*\n(.*?)(?=\n##\s|\Z)"
                    match = re.search(pattern, content, re.DOTALL)
                    if match:
                        text = match.group(1).strip()
                        if text:
                            section = getattr(data.summaries, attr_name)
                            section.summary = text
                            section.updated_at = now

            self._write(self._memory_file(), data.model_dump_json(indent=2))
            self._cache = data

            if old_memory.exists():
                old_memory.unlink()
                logger.info("[Memory] Deleted old MEMORY.md")
            if old_summary.exists():
                old_summary.unlink()
                logger.info("[Memory] Deleted old summary.md")

            logger.info("[Memory] Auto-migration completed")
        except Exception as e:
            logger.error(f"[Memory] Auto-migration failed: {e}")

    def _migrate_summary_sections(self, raw: dict) -> None:
        summaries = raw.get("summaries", {})
        if not summaries:
            return
        if "preferences" in summaries and "interests" not in summaries:
            old_prefs = summaries["preferences"]
            if isinstance(old_prefs, dict) and old_prefs.get("summary"):
                summaries["interests"] = {
                    "summary": old_prefs["summary"],
                    "updated_at": old_prefs.get("updated_at", ""),
                }
                summaries["preferences"] = {"summary": "", "updated_at": ""}
                logger.info("[Memory] Migrated '兴趣偏好' to '兴趣目标'")

    # --- 数据读写 ---

    def load_data(self) -> MemoryData:
        with self._lock:
            if self._cache is not None:
                return self._cache
            path = self._memory_file()
            if not path.exists():
                self._cache = MemoryData()
                return self._cache
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                self._migrate_summary_sections(raw)
                self._cache = MemoryData.model_validate(raw)
                return self._cache
            except Exception as e:
                logger.warning(f"[Memory] Failed to load memory.json: {e}")
                self._cache = MemoryData()
                return self._cache

    def save_data(self, data: MemoryData) -> None:
        with self._lock:
            data.last_updated = datetime.now(timezone.utc).isoformat()
            self._write(self._memory_file(), data.model_dump_json(indent=2))
            self._cache = data

    # --- 知识 ---

    def load_knowledge(self) -> str:
        with self._lock:
            return self._read(self._knowledge_file())

    def save_knowledge(self, content: str) -> None:
        with self._lock:
            self._write(self._knowledge_file(), content)

    def parse_knowledge(self) -> list[dict[str, str]]:
        content = self.load_knowledge()
        if not content.strip():
            return []
        sections: list[dict[str, str]] = []
        lines = content.split("\n")
        current_title = ""
        current_lines: list[str] = []
        for line in lines:
            if line.startswith("## "):
                if current_title and current_lines:
                    sections.append(
                        {"title": current_title, "content": "\n".join(current_lines)}
                    )
                current_title = line.replace("## ", "").strip()
                current_lines = []
            elif line.strip().startswith("- "):
                current_lines.append(line.strip())
        if current_title and current_lines:
            sections.append({"title": current_title, "content": "\n".join(current_lines)})
        return sections

    # --- 每日记录 ---

    def load_daily(self, date: str | None = None) -> str:
        with self._lock:
            return self._read(self._daily_file(date))

    def append_daily(self, content: str, date: str | None = None) -> None:
        with self._lock:
            actual_date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
            path = self._daily_file(actual_date)
            existing = self._read(path)
            now = datetime.now(timezone.utc).strftime("%H:%M")
            if not existing:
                existing = f"# {actual_date}\n\n"
            entry = f"- [{now}] {content}\n"
            self._write(path, existing + entry)

    def list_dailies(self) -> list[str]:
        daily_dir = self._path / "daily"
        if not daily_dir.exists():
            return []
        files = sorted(daily_dir.glob("*.md"))
        return [f.stem for f in files]

    # --- 清空操作 ---

    def clear_knowledge(self) -> None:
        with self._lock:
            if self._knowledge_file().exists():
                self._knowledge_file().unlink()

    def clear_dailies(self) -> None:
        with self._lock:
            daily_dir = self._path / "daily"
            if daily_dir.exists() and daily_dir.is_dir():
                shutil.rmtree(daily_dir)
                daily_dir.mkdir(exist_ok=True)

    def reset_all(self) -> None:
        with self._lock:
            if self._memory_file().exists():
                self._memory_file().unlink()
            if self._knowledge_file().exists():
                self._knowledge_file().unlink()
            daily_dir = self._path / "daily"
            if daily_dir.exists() and daily_dir.is_dir():
                shutil.rmtree(daily_dir)
            (self._path / "daily").mkdir(exist_ok=True)
            self._cache = None
