import asyncio
import re
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from app.core.config import settings
from .models import (
    MemoryData,
    ProfileData,
    FactItem,
    SummaryData,
    SummarySection,
    FACT_CATEGORIES,
    _SUMMARY_SECTION_MAP,
    summaries_to_markdown,
)
from .prompts import (
    _CORRECTION_HINT,
    _CORRECTION_PATTERNS_EN,
    _CORRECTION_PATTERNS_ZH,
    _REINFORCEMENT_HINT,
    _REINFORCEMENT_PATTERNS_EN,
    _REINFORCEMENT_PATTERNS_ZH,
    _SUMMARY_EXTRACT_PROMPT,
)
from .store import MemoryStore
from .fact_manager import FactManager
from .extractor import MemoryExtractor
from .context_builder import ContextBuilder


class MemoryEngine:
    """记忆引擎门面：组合存储、事实管理、LLM 提取、上下文组装等组件。"""

    def __init__(self, storage_path: Path | str | None = None):
        if storage_path:
            path = Path(storage_path)
        else:
            path = Path(settings.DATA_DIR) / "memory"

        self._store = MemoryStore(path)
        self._fact_manager = FactManager(self._store)
        self._async_lock = asyncio.Lock()
        self._extractor = MemoryExtractor(self._store, self._fact_manager, self._async_lock)
        self._context_builder = ContextBuilder(self._store)

    # --- 数据访问 ---

    def load_data(self) -> MemoryData:
        return self._store.load_data()

    def save_data(self, data: MemoryData) -> None:
        self._store.save_data(data)

    # --- 记忆（兼容 Markdown 接口） ---

    def load_memory(self) -> str:
        data = self._store.load_data()
        return self._data_to_markdown(data)

    def save_memory(self, content: str) -> None:
        data = self._store.load_data()
        name_match = re.search(
            r"(?:name|姓名|名字)[：:]\s*(.+)", content, re.IGNORECASE
        )
        if name_match:
            data.profile.name = name_match.group(1).strip()
            data.profile.updated_at = datetime.now(timezone.utc).isoformat()
            self._store.save_data(data)

    # --- 档案 ---

    def parse_profile(self) -> dict[str, str]:
        data = self._store.load_data()
        profile = {}
        if data.profile.name:
            profile["name"] = data.profile.name
        return profile

    # --- 事实 ---

    def get_facts(self, category: str | None = None) -> list[FactItem]:
        return self._fact_manager.get_facts(category)

    def add_fact(self, fact: FactItem) -> None:
        self._fact_manager.add_fact(fact)

    def remove_fact(self, fact_id: str) -> bool:
        return self._fact_manager.remove_fact(fact_id)

    def update_fact(
        self,
        fact_id: str,
        content: str | None = None,
        category: str | None = None,
        confidence: float | None = None,
    ) -> bool:
        return self._fact_manager.update_fact(fact_id, content, category, confidence)

    def clear_facts(self) -> None:
        self._fact_manager.clear_facts()

    # --- 知识 ---

    def load_knowledge(self) -> str:
        return self._store.load_knowledge()

    def save_knowledge(self, content: str) -> None:
        self._store.save_knowledge(content)

    def parse_knowledge(self) -> list[dict[str, str]]:
        return self._store.parse_knowledge()

    def clear_knowledge(self) -> None:
        self._store.clear_knowledge()

    # --- 总结 ---

    def load_summary(self) -> str:
        data = self._store.load_data()
        return summaries_to_markdown(data)

    def save_summary(self, content: str) -> None:
        """保存摘要内容。"""
        data = self._store.load_data()
        self._markdown_to_summaries(data, content)
        self._store.save_data(data)

    def parse_summary(self) -> dict[str, str]:
        data = self._store.load_data()
        return {
            "用户画像": data.summaries.user_profile.summary,
            "偏好设置": data.summaries.preferences.summary,
            "兴趣目标": data.summaries.interests.summary,
            "近期状态": data.summaries.recent_state.summary,
            "事件时间线": data.summaries.timeline.summary,
        }

    async def merge_summary(self, old_summary: str, new_summary: str, llm_adapter=None) -> str | None:
        return await self._extractor.merge_summary(old_summary, new_summary, llm_adapter)

    async def extract_summary_sections(self, content: str, llm_adapter=None) -> dict | None:
        """使用LLM从摘要内容中提取五个部分。"""
        return await self._extractor.extract_summary_sections(content, llm_adapter)

    async def extract_knowledge(self, conversation: str, llm_adapter=None) -> str | None:
        """使用LLM从对话中提取知识点。"""
        return await self._extractor.extract_knowledge(conversation, llm_adapter)

    def clear_summaries(self) -> None:
        data = self._store.load_data()
        data.summaries = SummaryData()
        self._store.save_data(data)

    # --- 每日记录 ---

    def load_daily(self, date: str | None = None, conversation_id: str | None = None) -> str:
        return self._store.load_daily(date, conversation_id)

    def append_daily(self, content: str, date: str | None = None, conversation_id: str | None = None) -> None:
        self._store.append_daily(content, date, conversation_id)

    def list_dailies(self, conversation_id: str | None = None) -> list[str]:
        return self._store.list_dailies(conversation_id)

    def list_conversation_dailies(self) -> list[str]:
        return self._store.list_conversation_dailies()

    def clear_dailies(self) -> None:
        self._store.clear_dailies()

    # --- 上下文 ---

    def build_context(self, max_chars: int | None = None, query: str = "", conversation_id: str | None = None) -> str:
        conv_store = None
        if conversation_id:
            from .memory_engine import get_conversation_store
            agent_id = getattr(self, '_agent_id', None)
            conv_store = get_conversation_store(agent_id, conversation_id)
        return self._context_builder.build_context(max_chars, query=query, conversation_store=conv_store)

    # --- LLM 驱动的更新 ---

    async def extract_facts(
        self, message: str, llm_adapter=None, correction_hint: str = "", context_messages: str = ""
    ) -> tuple[str, list[FactItem]]:
        return await self._extractor.extract_facts(message, llm_adapter, correction_hint, context_messages)

    async def update_profile_from_message(
        self, message: str, llm_adapter=None, correction_hint: str = "", context_messages: str = ""
    ) -> dict[str, str]:
        return await self._extractor.update_profile_from_message(message, llm_adapter, correction_hint, context_messages)

    async def distill_conversation(
        self,
        messages: list[dict],
        llm_adapter=None,
        correction_hint: str = "",
    ) -> str | None:
        return await self._extractor.distill_conversation(messages, llm_adapter, correction_hint)

    # --- 重置 ---

    def reset_all(self) -> None:
        self._store.reset_all()

    # --- 内部兼容方法（测试和 API debug 端点使用） ---

    @property
    def _path(self):
        return self._store._path

    def _memory_file(self):
        return self._store._memory_file()

    def _knowledge_file(self):
        return self._store._knowledge_file()

    def _find_similar_fact(self, data: MemoryData, content: str):
        return self._fact_manager._find_similar_fact(data, content)

    def _deprecate_old_name_facts(self, data: MemoryData, old_name: str, new_name: str) -> None:
        self._fact_manager.deprecate_old_name_facts(data, old_name, new_name)

    # --- 内部转换 ---

    @staticmethod
    def _data_to_markdown(data: MemoryData) -> str:
        lines = ["# 用户档案\n"]
        if data.profile.name:
            lines.append(f"- name: {data.profile.name}")
        if data.facts:
            lines.append("\n## 记忆事实\n")
            for fact in data.facts:
                lines.append(f"- [{fact.category}|{fact.confidence:.1f}] {fact.content}")
        return "\n".join(lines)

    @staticmethod
    def _markdown_to_summaries(data: MemoryData, content: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        for cn_name, attr_name in _SUMMARY_SECTION_MAP.items():
            pattern = rf"##\s*{re.escape(cn_name)}\s*\n(.*?)(?=\n##\s|\Z)"
            match = re.search(pattern, content, re.DOTALL)
            if match:
                text = match.group(1).strip()
                section = getattr(data.summaries, attr_name)
                section.summary = text
                section.updated_at = now


# --- 引擎注册表 ---

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


_conversation_stores: dict[str, MemoryStore] = {}


def get_conversation_store(agent_id: str | None, conversation_id: str) -> MemoryStore:
    """返回对话级 MemoryStore，隔离 summaries/daily/dynamic_context。
    
    Args:
        agent_id: Agent ID，如果为None则使用默认Agent
        conversation_id: 对话ID
    
    Returns:
        对话级MemoryStore实例
    """
    key = f"{agent_id or '_default'}:{conversation_id}"
    if key in _conversation_stores:
        return _conversation_stores[key]
    with _engine_lock:
        if key in _conversation_stores:
            return _conversation_stores[key]
        agent_key = agent_id or "_default"
        path = Path(settings.DATA_DIR) / "memory" / "agents" / agent_key / "conversations" / conversation_id
        store = MemoryStore(path)
        _conversation_stores[key] = store
        return store


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
