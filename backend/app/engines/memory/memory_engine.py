import asyncio
import json
import re
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from loguru import logger
from pydantic import BaseModel, Field

from app.core.config import settings

_FACT_EXTRACT_PROMPT = """你是一个记忆提取助手。从用户消息中提取关键信息，包括用户名字和事实。

规则：
1. profile_name：只提取用户自己的名字，不提取别人的名字
2. 如果用户在问问题（"我叫什么？"）或假设性语句（"如果我叫小明"），profile_name留空
3. 名字长度不超过20个字符
4. 事实提取规则：
   - 只提取明确陈述或强暗示的信息，不提取假设性内容
   - 每条事实必须有明确的类别
   - 置信度：0.9-1.0（明确陈述）、0.7-0.8（强暗示）、0.5-0.6（推断模式）
   - 如果是纠正之前的信息，使用 correction 类别，并在 source_error 中记录之前的错误信息

类别：
- preference: 用户偏好（喜欢/不喜欢什么）
- knowledge: 用户知识/专长
- context: 用户当前背景（工作、项目等）
- behavior: 用户行为模式（习惯、风格等）
- goal: 用户目标/计划
- correction: 纠正之前的错误信息

请严格按以下JSON格式回复，不要添加任何其他内容：
{{"profile_name": "用户名字或空字符串", "facts": [{{"content": "事实内容", "category": "类别", "confidence": 0.9, "source_error": ""}}]}}

如果消息中不包含可提取的内容，返回：
{{"profile_name": "", "facts": []}}

用户消息：{message}"""

_CORRECTION_HINT = "特别注意：用户在最近的对话中表达了纠正/不满，请以 correction 类别、confidence >= 0.95 记录正确做法，并在 source_error 中记录之前的错误信息。"

_REINFORCEMENT_HINT = "特别注意：用户在最近的对话中确认了某个信息，请以 preference 或 behavior 类别、confidence >= 0.9 记录确认的做法。"

_DISTILL_PROMPT = """你是一个记忆蒸馏助手。根据当前记忆和近期对话，完成两项任务：

任务1：提取结构化事实（回填到用户档案）
从对话中提取所有可确认的事实信息，包括用户名字、偏好、背景等。

任务2：更新叙事性总结
保留已有的正确信息，只更新或补充。每个部分用简洁的要点列出，不要写长段落。事件时间线按时间倒序排列，最多保留20条。

规则：
1. 事实提取是最高优先级——如果对话中用户说了名字，必须提取
2. 如果用户纠正了之前的信息，用 correction 类别记录，source_error 填写被纠正的旧信息
3. 名字提取规则：只提取用户自己的名字，不提取别人或假设性的名字
4. 总结中的信息必须与提取的事实一致，不能矛盾
5. 维度划分规则：
   - 用户画像：客观身份事实（姓名、职业、年龄段、地区、技术栈等）
   - 偏好设置：交互行为偏好（回复风格、代码风格、是否希望被称呼名字等）
   - 兴趣目标：学习/生活兴趣（想学的技术、想去的地方、目标计划等）
   - 近期状态：临时状态（当前心情、本周状态等）
   - 事件时间线：重要事件、里程碑

请严格按以下JSON格式回复，不要添加任何其他内容：
{{
  "facts": [{{"content": "事实内容", "category": "类别", "confidence": 0.9, "source_error": ""}}],
  "profile_name": "",
  "summary": {{
    "用户画像": "",
    "偏好设置": "",
    "兴趣目标": "",
    "近期状态": "",
    "事件时间线": ""
  }}
}}

其中 profile_name 仅在对话中明确提到用户名字时填写，否则留空。
summary 的每个字段用 Markdown 要点格式填写（每行以 "- " 开头），如果某个部分没有新信息则保留原文。

当前记忆：
- 用户名字：{current_name}
- 已有事实：{current_facts}
- 当前总结：
{current_summary}

近期对话摘要：
{conversation_summary}

{correction_hint}"""

_SUMMARY_SECTION_MAP = {
    "用户画像": "user_profile",
    "偏好设置": "preferences",
    "兴趣目标": "interests",
    "近期状态": "recent_state",
    "事件时间线": "timeline",
}

_CORRECTION_PATTERNS_ZH = [
    "不对", "你理解错了", "你理解有误", "不是这样的", "错了",
    "重试", "重新来", "换一种", "改用", "别这样",
]
_CORRECTION_PATTERNS_EN = [
    "that's wrong", "you misunderstood", "try again", "redo",
    "not what i meant", "incorrect",
]
_REINFORCEMENT_PATTERNS_ZH = [
    "对，就是这样", "完全正确", "正是我想要的", "继续保持", "很好",
    "没错", "对的", "就是这样",
]
_REINFORCEMENT_PATTERNS_EN = [
    "yes exactly", "perfect", "that's right", "keep doing that",
    "this is great", "correct",
]

FACT_CATEGORIES = ("preference", "knowledge", "context", "behavior", "goal", "correction")


class ProfileData(BaseModel):
    name: str = ""
    updated_at: str = ""


class FactItem(BaseModel):
    id: str = Field(default_factory=lambda: f"fact_{uuid4().hex[:8]}")
    content: str
    category: str = "context"
    confidence: float = 0.8
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: str = "conversation"
    source_error: str = ""


class SummarySection(BaseModel):
    summary: str = ""
    updated_at: str = ""


class SummaryData(BaseModel):
    user_profile: SummarySection = Field(default_factory=SummarySection)
    preferences: SummarySection = Field(default_factory=SummarySection)
    interests: SummarySection = Field(default_factory=SummarySection)
    recent_state: SummarySection = Field(default_factory=SummarySection)
    timeline: SummarySection = Field(default_factory=SummarySection)


class MemoryData(BaseModel):
    version: str = "2.0"
    last_updated: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    profile: ProfileData = Field(default_factory=ProfileData)
    facts: list[FactItem] = Field(default_factory=list)
    summaries: SummaryData = Field(default_factory=SummaryData)


class MemoryEngine:
    MAX_FACTS = 100
    FACT_CONFIDENCE_THRESHOLD = 0.7
    MAX_INJECTION_CHARS = 4000

    def __init__(self, storage_path: Path | str | None = None):
        if storage_path:
            self._path = Path(storage_path)
        else:
            self._path = Path(settings.DATA_DIR) / "memory"
        self._path.mkdir(parents=True, exist_ok=True)
        (self._path / "daily").mkdir(exist_ok=True)
        self._lock = threading.RLock()
        self._async_lock = asyncio.Lock()
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

    def save_data(self, data: MemoryData) -> None:
        with self._lock:
            data.last_updated = datetime.now(timezone.utc).isoformat()
            self._write(self._memory_file(), data.model_dump_json(indent=2))
            self._cache = data

    def load_memory(self) -> str:
        data = self.load_data()
        return self._data_to_markdown(data)

    def save_memory(self, content: str) -> None:
        data = self.load_data()
        name_match = re.search(
            r"(?:name|姓名|名字)[：:]\s*(.+)", content, re.IGNORECASE
        )
        if name_match:
            data.profile.name = name_match.group(1).strip()
            data.profile.updated_at = datetime.now(timezone.utc).isoformat()
            self.save_data(data)

    def _data_to_markdown(self, data: MemoryData) -> str:
        lines = ["# 用户档案\n"]
        if data.profile.name:
            lines.append(f"- name: {data.profile.name}")
        if data.facts:
            lines.append("\n## 记忆事实\n")
            for fact in data.facts:
                lines.append(f"- [{fact.category}|{fact.confidence:.1f}] {fact.content}")
        return "\n".join(lines)

    def parse_profile(self) -> dict[str, str]:
        data = self.load_data()
        profile = {}
        if data.profile.name:
            profile["name"] = data.profile.name
        return profile

    def get_facts(self, category: str | None = None) -> list[FactItem]:
        data = self.load_data()
        if category:
            return [f for f in data.facts if f.category == category]
        return list(data.facts)

    def add_fact(self, fact: FactItem) -> None:
        data = self.load_data()
        existing = self._find_similar_fact(data, fact.content)
        if existing:
            if fact.confidence > existing.confidence:
                existing.content = fact.content
                existing.confidence = fact.confidence
                existing.category = fact.category
                existing.source_error = fact.source_error
        else:
            data.facts.append(fact)
        if len(data.facts) > self.MAX_FACTS:
            data.facts.sort(key=lambda f: f.confidence, reverse=True)
            data.facts = data.facts[: self.MAX_FACTS]
        self.save_data(data)

    def remove_fact(self, fact_id: str) -> bool:
        data = self.load_data()
        before = len(data.facts)
        data.facts = [f for f in data.facts if f.id != fact_id]
        if len(data.facts) < before:
            self.save_data(data)
            return True
        return False

    def clear_facts(self) -> None:
        """清空所有事实"""
        data = self.load_data()
        data.facts = []
        self.save_data(data)

    def clear_knowledge(self) -> None:
        """清空知识记忆"""
        with self._lock:
            if self._knowledge_file().exists():
                self._knowledge_file().unlink()

    def clear_dailies(self) -> None:
        """清空所有近期对话记录"""
        with self._lock:
            daily_dir = self._path / "daily"
            if daily_dir.exists() and daily_dir.is_dir():
                shutil.rmtree(daily_dir)
                daily_dir.mkdir(exist_ok=True)

    def clear_summaries(self) -> None:
        """重置AI总结"""
        data = self.load_data()
        data.summaries = SummaryData()
        self.save_data(data)

    def reset_all(self) -> None:
        """重置全部记忆到出厂状态"""
        with self._lock:
            # 删除所有文件
            if self._memory_file().exists():
                self._memory_file().unlink()
            if self._knowledge_file().exists():
                self._knowledge_file().unlink()
            daily_dir = self._path / "daily"
            if daily_dir.exists() and daily_dir.is_dir():
                shutil.rmtree(daily_dir)
            # 重新创建必要目录
            (self._path / "daily").mkdir(exist_ok=True)
            self._cache = None

    def update_fact(
        self,
        fact_id: str,
        content: str | None = None,
        category: str | None = None,
        confidence: float | None = None,
    ) -> bool:
        data = self.load_data()
        for fact in data.facts:
            if fact.id == fact_id:
                if content is not None:
                    fact.content = content
                if category is not None:
                    fact.category = category
                if confidence is not None:
                    fact.confidence = confidence
                self.save_data(data)
                return True
        return False

    def _find_similar_fact(self, data: MemoryData, content: str) -> FactItem | None:
        normalized = content.strip().casefold()
        for fact in data.facts:
            if fact.content.strip().casefold() == normalized:
                return fact
        return None

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

    def load_summary(self) -> str:
        data = self.load_data()
        return self._summaries_to_markdown(data)

    def save_summary(self, content: str) -> None:
        data = self.load_data()
        self._markdown_to_summaries(data, content)
        self.save_data(data)

    def parse_summary(self) -> dict[str, str]:
        data = self.load_data()
        result = {}
        mapping = {
            "用户画像": data.summaries.user_profile.summary,
            "偏好设置": data.summaries.preferences.summary,
            "兴趣目标": data.summaries.interests.summary,
            "近期状态": data.summaries.recent_state.summary,
            "事件时间线": data.summaries.timeline.summary,
        }
        for key, value in mapping.items():
            if value:
                result[key] = value
        return result

    def _summaries_to_markdown(self, data: MemoryData) -> str:
        lines = []
        sections = [
            ("用户画像", data.summaries.user_profile.summary),
            ("偏好设置", data.summaries.preferences.summary),
            ("兴趣目标", data.summaries.interests.summary),
            ("近期状态", data.summaries.recent_state.summary),
            ("事件时间线", data.summaries.timeline.summary),
        ]
        for title, content in sections:
            if content:
                lines.append(f"## {title}\n{content}")
        return "\n\n".join(lines)

    def _markdown_to_summaries(self, data: MemoryData, content: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        for cn_name, attr_name in _SUMMARY_SECTION_MAP.items():
            pattern = rf"##\s*{re.escape(cn_name)}\s*\n(.*?)(?=\n##\s|\Z)"
            match = re.search(pattern, content, re.DOTALL)
            if match:
                text = match.group(1).strip()
                section = getattr(data.summaries, attr_name)
                section.summary = text
                section.updated_at = now

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

    def build_context(self, max_chars: int | None = None) -> str:
        budget = max_chars or self.MAX_INJECTION_CHARS
        sections = []
        used_chars = 0

        data = self.load_data()

        profile_text = ""
        if data.profile.name:
            profile_text = f"用户名字：{data.profile.name}"
        if profile_text:
            section = f"=== [用户档案 · 最高优先级] ===\n{profile_text}"
            sections.append(section)
            used_chars += len(section)

        facts = sorted(data.facts, key=lambda f: f.confidence, reverse=True)
        if facts:
            fact_lines = []
            for fact in facts:
                line = f"- [{fact.category}|{fact.confidence:.1f}] {fact.content}"
                if fact.source_error:
                    line += f" (避免: {fact.source_error})"
                if used_chars + len(line) + 20 > budget:
                    break
                fact_lines.append(line)
                used_chars += len(line) + 1
            if fact_lines:
                sections.append("=== [记忆事实] ===\n" + "\n".join(fact_lines))

        knowledge = self.load_knowledge()
        if knowledge.strip() and used_chars + len(knowledge) + 30 <= budget:
            sections.append("=== [知识记忆] ===\n" + knowledge.strip())
            used_chars += len(knowledge) + 30

        dailies = self.list_dailies()
        if dailies:
            recent = dailies[-7:]
            daily_entries = []
            for date in recent:
                content = self.load_daily(date)
                if content.strip():
                    lines = [
                        l for l in content.split("\n") if l.strip().startswith("- ")
                    ]
                    if lines:
                        daily_entries.append(
                            f"**{date}**:\n" + "\n".join(lines[:10])
                        )
            daily_text = "\n\n".join(daily_entries)
            if daily_text and used_chars + len(daily_text) + 30 <= budget:
                sections.append("=== [近期对话] ===\n" + daily_text)
                used_chars += len(daily_text) + 30

        summary_text = self._summaries_to_markdown(data)
        if summary_text.strip():
            remaining = budget - used_chars - 50
            if remaining > 100:
                truncated = summary_text[:remaining] + "..."
                sections.append(
                    "=== [AI总结 · 补充上下文，与档案/事实冲突时以档案为准] ===\n"
                    + truncated
                )

        return "\n\n".join(sections) if sections else ""

    async def extract_facts(
        self, message: str, llm_adapter=None, correction_hint: str = ""
    ) -> tuple[str, list[FactItem]]:
        stripped = message.strip()
        if not stripped:
            return "", []

        if llm_adapter is None:
            try:
                from app.runtime.provider.llm.adapter import (
                    llm_adapter as default_adapter,
                )

                llm_adapter = default_adapter
            except Exception as e:
                logger.warning(f"[Memory] No LLM adapter available: {e}")
                return "", []

        try:
            prompt = _FACT_EXTRACT_PROMPT.format(message=stripped)
            if correction_hint:
                prompt += "\n\n" + correction_hint

            result = await llm_adapter.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=500,
            )
            response_text = (
                result.strip() if isinstance(result, str) else str(result).strip()
            )
            logger.info(f"[Memory] LLM fact extract response: {response_text}")

            json_str = response_text
            if "```" in json_str:
                json_match = re.search(
                    r"```(?:json)?\s*(\{.*?\})\s*```", json_str, re.DOTALL
                )
                if json_match:
                    json_str = json_match.group(1)
            json_str = json_str.strip()

            parsed = json.loads(json_str)
            profile_name = parsed.get("profile_name", "").strip()[:20]

            raw_facts = parsed.get("facts", [])
            if not isinstance(raw_facts, list):
                return profile_name, []

            facts = []
            for raw in raw_facts:
                content = raw.get("content", "").strip()
                category = raw.get("category", "context")
                confidence = raw.get("confidence", 0.8)
                source_error = raw.get("source_error", "")

                if not content:
                    continue
                if category not in FACT_CATEGORIES:
                    category = "context"
                try:
                    confidence = float(confidence)
                    if confidence < self.FACT_CONFIDENCE_THRESHOLD:
                        continue
                except (TypeError, ValueError):
                    confidence = 0.8

                facts.append(
                    FactItem(
                        content=content,
                        category=category,
                        confidence=confidence,
                        source_error=source_error,
                    )
                )

            return profile_name, facts

        except json.JSONDecodeError as e:
            logger.warning(
                f"[Memory] Failed to parse LLM fact response: {e}, raw: {response_text[:200]}"
            )
            return "", []
        except Exception as e:
            logger.warning(f"[Memory] Fact extraction failed: {e}")
            return "", []

    async def update_profile_from_message(
        self, message: str, llm_adapter=None, correction_hint: str = ""
    ) -> dict[str, str]:
        profile_name, facts = await self.extract_facts(message, llm_adapter, correction_hint)

        updates = {}
        async with self._async_lock:
            data = self.load_data()

            if profile_name:
                old_name = data.profile.name
                data.profile.name = profile_name
                data.profile.updated_at = datetime.now(timezone.utc).isoformat()
                updates["name"] = profile_name
                
                if old_name and old_name != profile_name:
                    self._deprecate_old_name_facts(data, old_name, profile_name)

            for fact in facts:
                if fact.category == "correction" and fact.source_error:
                    self._apply_correction(data, fact)

                existing = self._find_similar_fact(data, fact.content)
                if existing:
                    if fact.confidence > existing.confidence:
                        existing.content = fact.content
                        existing.confidence = fact.confidence
                        existing.category = fact.category
                        existing.source_error = fact.source_error
                else:
                    data.facts.append(fact)

            if len(data.facts) > self.MAX_FACTS:
                data.facts.sort(key=lambda f: f.confidence, reverse=True)
                data.facts = data.facts[: self.MAX_FACTS]

            self.save_data(data)

        if updates:
            logger.info(f"[Memory] Profile updated: {updates}")

        return updates

    def _deprecate_old_name_facts(self, data: MemoryData, old_name: str, new_name: str) -> None:
        old_name_lower = old_name.strip().casefold()
        new_name_lower = new_name.strip().casefold()
        
        for fact in data.facts:
            fact_content_lower = fact.content.strip().casefold()
            
            if fact.confidence >= 0.9:
                if old_name_lower in fact_content_lower:
                    if "名字" in fact_content_lower or "叫" in fact_content_lower or "名为" in fact_content_lower:
                        fact.confidence = min(fact.confidence, 0.3)
                elif new_name_lower not in fact_content_lower:
                    common_names = ["小红", "小洪", "小天", "胡天", "小一", "小黑", "黑子", "小明", "小白", "小米"]
                    for name in common_names:
                        if name.strip().casefold() in fact_content_lower:
                            if "名字" in fact_content_lower or "叫" in fact_content_lower or "名为" in fact_content_lower:
                                fact.confidence = min(fact.confidence, 0.3)
                                break

    def _apply_correction(self, data: MemoryData, correction_fact: FactItem) -> None:
        error_text = correction_fact.source_error.strip().casefold()
        if not error_text:
            return
        for fact in data.facts:
            if error_text in fact.content.casefold():
                fact.confidence = min(fact.confidence, 0.3)

    async def distill_conversation(
        self,
        messages: list[dict],
        llm_adapter=None,
        correction_hint: str = "",
    ) -> str | None:
        user_msgs = []
        for m in messages:
            if m.get("role") == "user":
                c = m.get("content", "")
                if isinstance(c, list):
                    c = " ".join(
                        p.get("text", "")
                        for p in c
                        if isinstance(p, dict) and p.get("type") == "text"
                    )
                user_msgs.append(str(c)[:300])

        assistant_msgs = []
        for m in messages:
            if m.get("role") == "assistant":
                c = m.get("content", "")
                if isinstance(c, str):
                    assistant_msgs.append(c[:300])

        if not user_msgs:
            return None

        conv_summary = "用户：\n" + "\n".join(f"- {m}" for m in user_msgs[-10:])
        if assistant_msgs:
            conv_summary += "\n\n助手回复摘要：\n" + "\n".join(
                f"- {m}" for m in assistant_msgs[-5:]
            )

        data = self.load_data()
        current_name = data.profile.name or "(未知)"
        current_facts = "\n".join(
            f"  - [{f.category}|{f.confidence:.1f}] {f.content}"
            for f in data.facts
        ) or "(无)"
        current_summary = self._summaries_to_markdown(data) or "(空)"

        prompt = _DISTILL_PROMPT.format(
            current_name=current_name,
            current_facts=current_facts,
            current_summary=current_summary,
            conversation_summary=conv_summary,
            correction_hint=correction_hint,
        )

        try:
            if llm_adapter is None:
                from app.runtime.provider.llm.adapter import (
                    llm_adapter as default_adapter,
                )

                llm_adapter = default_adapter

            result = await llm_adapter.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2000,
            )
            response_text = (
                result.strip() if isinstance(result, str) else str(result).strip()
            )
            logger.info(f"[Memory] Distill response: {response_text[:300]}")

            json_str = response_text
            if "```" in json_str:
                json_match = re.search(
                    r"```(?:json)?\s*(\{.*?\})\s*```", json_str, re.DOTALL
                )
                if json_match:
                    json_str = json_match.group(1)
            json_str = json_str.strip()

            parsed = json.loads(json_str)

            now = datetime.now(timezone.utc).isoformat()

            profile_name = parsed.get("profile_name", "").strip()
            raw_facts = parsed.get("facts", [])
            valid_facts = []
            if isinstance(raw_facts, list):
                for raw in raw_facts:
                    content = raw.get("content", "").strip()
                    if not content:
                        continue
                    category = raw.get("category", "context")
                    confidence = raw.get("confidence", 0.8)
                    source_error = raw.get("source_error", "")

                    if category not in FACT_CATEGORIES:
                        category = "context"
                    try:
                        confidence = float(confidence)
                        if confidence < self.FACT_CONFIDENCE_THRESHOLD:
                            continue
                    except (TypeError, ValueError):
                        confidence = 0.8

                    valid_facts.append(FactItem(
                        content=content,
                        category=category,
                        confidence=confidence,
                        source_error=source_error,
                        source="distill",
                    ))

            raw_summary = parsed.get("summary", {})

            async with self._async_lock:
                data = self.load_data()

                if profile_name and len(profile_name) <= 20:
                    data.profile.name = profile_name
                    data.profile.updated_at = now
                    logger.info(f"[Memory] Distill updated profile name: {profile_name}")

                for fact in valid_facts:
                    if fact.category == "correction" and fact.source_error:
                        self._apply_correction(data, fact)

                    existing = self._find_similar_fact(data, fact.content)
                    if existing:
                        if fact.confidence > existing.confidence:
                            existing.content = fact.content
                            existing.confidence = fact.confidence
                            existing.category = fact.category
                            existing.source_error = fact.source_error
                    else:
                        data.facts.append(fact)

                if len(data.facts) > self.MAX_FACTS:
                    data.facts.sort(key=lambda f: f.confidence, reverse=True)
                    data.facts = data.facts[: self.MAX_FACTS]

                if isinstance(raw_summary, dict):
                    for cn_name, attr_name in _SUMMARY_SECTION_MAP.items():
                        text = raw_summary.get(cn_name, "").strip()
                        if text:
                            section = getattr(data.summaries, attr_name)
                            section.summary = text
                            section.updated_at = now

                self.save_data(data)

            logger.info(
                f"[Memory] Distill completed: name={data.profile.name}, facts={len(data.facts)}"
            )
            return self._summaries_to_markdown(data)

        except json.JSONDecodeError as e:
            logger.warning(
                f"[Memory] Failed to parse distill response: {e}, raw: {response_text[:200]}"
            )
            return None
        except Exception as e:
            logger.warning(f"[Memory] Distillation failed: {e}")
            return None


_engines: dict[str, MemoryEngine] = {}
_engine_lock = threading.Lock()
_migrated = False


def _migrate_legacy() -> None:
    global _migrated
    if _migrated:
        return
    _migrated = True
    legacy = Path(settings.DATA_DIR) / "memory"
    target = legacy / "agents" / "_default"
    if target.exists():
        return
    old_json = legacy / "memory.json"
    if not old_json.exists():
        return
    logger.info("[Memory] Migrating legacy memory files to agents/_default/ ...")
    target.mkdir(parents=True, exist_ok=True)
    for name in ("memory.json", "knowledge.md"):
        src = legacy / name
        if src.exists():
            shutil.move(str(src), str(target / name))
    old_daily = legacy / "daily"
    if old_daily.exists() and old_daily.is_dir():
        shutil.move(str(old_daily), str(target / "daily"))
    logger.info("[Memory] Legacy migration completed")


def get_memory_engine(agent_id: str | None = None) -> MemoryEngine:
    key = agent_id or "_default"
    if key in _engines:
        return _engines[key]
    with _engine_lock:
        if key in _engines:
            return _engines[key]
        _migrate_legacy()
        path = Path(settings.DATA_DIR) / "memory" / "agents" / key
        engine = MemoryEngine(storage_path=path)
        _engines[key] = engine
        return engine
