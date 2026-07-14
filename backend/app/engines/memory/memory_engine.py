from __future__ import annotations

import asyncio
import re
import shutil
import threading
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from app.core.utils import utc_now

from app.core.config import settings
from .models import (
    MemoryData,
    ProfileData,
    FactItem,
    SummaryData,
    SummarySection,
    FACT_CATEGORIES,
    FACT_SCOPE_AGENT,
    FACT_SCOPE_CONVERSATION,
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

if TYPE_CHECKING:
    from .vector_manager import VectorSearchManager


class MemoryEngine:
    """记忆引擎门面：组合存储、事实管理、LLM 提取、上下文组装等组件。"""

    def __init__(self, storage_path: Path | str | None = None, agent_id: str | None = None, embedding_provider=None):
        self._agent_id = agent_id or "_default"
        self._embedding_provider = embedding_provider

        if storage_path:
            path = Path(storage_path)
        else:
            path = Path(settings.DATA_DIR) / "memory" / "agents" / self._agent_id

        self._store = MemoryStore(path)
        self._fact_manager = FactManager(self._store)
        self._async_lock = asyncio.Lock()
        self._extractor = MemoryExtractor(self._store, self._fact_manager, self._async_lock, agent_id=self._agent_id)
        self._context_builder = ContextBuilder(self._store)
        
        self._vector_manager: VectorSearchManager | None = None

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
            data.profile.updated_at = utc_now()
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

    def promote_conversation_facts(self, conversation_id: str, fact_ids: list[str] | None = None) -> int:
        """方案A：将对话级facts提升到Agent级。

        提升后从对话级store中删除已提升的facts，避免注入时重复。

        Args:
            conversation_id: 来源对话ID
            fact_ids: 指定要提升的fact ID列表。为None时提升所有符合条件的facts。

        Returns:
            提升的fact数量
        """
        conv_store = get_conversation_store(self._agent_id, conversation_id)
        conv_data = conv_store.load_data()
        agent_data = self._store.load_data()

        promoted_ids = set()
        for fact in conv_data.facts:
            if not fact.is_latest:
                continue
            # 如果指定了fact_ids，只提升指定的
            if fact_ids is not None and fact.id not in fact_ids:
                continue
            # 跳过已过期的事实
            if fact.expires_at:
                try:
                    exp_time = datetime.fromisoformat(fact.expires_at.replace("Z", "+00:00"))
                    if exp_time <= datetime.now(timezone.utc):
                        continue
                except (ValueError, TypeError):
                    # 保持兼容：当 expires_at 非法时，按“无有效过期时间”处理，不阻止提升。
                    logger.warning(
                        f"[Memory] Invalid expires_at for fact {fact.id}: {fact.expires_at!r}; "
                        "treating as non-expired during promotion."
                    )
            # 清除source_conversation_id，使其成为Agent级全局可见
            fact.source_conversation_id = ""
            # 写入Agent级store
            self._fact_manager.merge_facts(agent_data, [fact])
            promoted_ids.add(fact.id)
            logger.info(f"[Memory] Fact promoted to agent level: {fact.content[:50]}")

        if promoted_ids:
            self._store.save_data(agent_data)
            # 从对话级store中删除已提升的facts，避免注入时重复
            conv_data.facts = [f for f in conv_data.facts if f.id not in promoted_ids]
            conv_store.save_data(conv_data)

        return len(promoted_ids)

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

    def save_summary(self, content: str, conversation_id: str | None = None) -> None:
        """保存摘要内容。如果提供 conversation_id，只写入对话级store；否则写入Agent级store。"""
        if conversation_id:
            conv_store = get_conversation_store(self._agent_id, conversation_id)
            conv_data = conv_store.load_data()
            self._markdown_to_summaries(conv_data, content)
            conv_store.save_data(conv_data)
        else:
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
        if conversation_id:
            conv_store = get_conversation_store(self._agent_id, conversation_id)
            return conv_store.load_daily(date)
        return self._store.load_daily(date)

    def append_daily(self, content: str, date: str | None = None, conversation_id: str | None = None) -> None:
        if conversation_id:
            conv_store = get_conversation_store(self._agent_id, conversation_id)
            conv_store.append_daily(content, date)
        else:
            self._store.append_daily(content, date)

    def list_dailies(self, conversation_id: str | None = None) -> list[str]:
        return self._store.list_dailies(conversation_id)

    def list_conversation_dailies(self) -> list[str]:
        return self._store.list_conversation_dailies()

    def clear_dailies(self) -> None:
        self._store.clear_dailies()

    def clear_conversation_daily(self, conversation_id: str, date: str | None = None) -> None:
        """清除指定对话的daily记录"""
        self._store.clear_daily(conversation_id, date)

    def clear_conversation_data(self, conversation_id: str) -> None:
        """清除对话级store的所有数据（facts + summary + dynamic_context + daily）"""
        conv_store = get_conversation_store(self._agent_id, conversation_id)
        conv_store.save_data(MemoryData())
        self._store.clear_daily(conversation_id)

        # 清除向量索引中该对话的数据
        self.vector_delete_conversation(conversation_id)

    # --- 向量搜索 ---

    def _get_vector_manager(self) -> "VectorSearchManager":
        """延迟初始化向量管理器"""
        if self._vector_manager is None:
            if self._embedding_provider is None:
                try:
                    from app.runtime.provider.llm.adapter import llm_adapter
                    self._embedding_provider = llm_adapter.get_provider()
                except Exception as e:
                    logger.warning(f"[Memory] Failed to access llm_adapter for embedding provider: {e}")

            if self._embedding_provider is None:
                raise RuntimeError(
                    "Embedding provider not available. "
                    "Ensure llm_adapter is configured with a provider that has embedding support."
                )

            from .vector_manager import VectorSearchManager
            self._vector_manager = VectorSearchManager(self._agent_id, self._embedding_provider)
        return self._vector_manager

    async def vector_dedup(self, facts: list[FactItem], conversation_id: str | None = None) -> list[FactItem]:
        """向量语义去重后的 facts"""
        vm = self._get_vector_manager()
        return await vm.dedup_and_add(facts, conversation_id)

    async def vector_retrieve(self, query: str, k: int = 10) -> list:
        """向量语义召回相关 facts"""
        vm = self._get_vector_manager()
        return await vm.retrieve(query, k)

    async def vector_rebuild(self, conversation_id: str | None = None) -> int:
        """重建向量索引"""
        vm = self._get_vector_manager()
        
        facts = []
        data = self._store.load_data()
        for f in data.facts:
            if f.is_latest:
                facts.append(f)
        
        if conversation_id:
            conv_store = get_conversation_store(self._agent_id, conversation_id)
            conv_data = conv_store.load_data()
            for f in conv_data.facts:
                if f.is_latest:
                    facts.append(f)
        
        return await vm.rebuild(facts, conversation_id)

    async def vector_delete_conversation(self, conversation_id: str) -> int:
        """删除对话相关向量"""
        if self._vector_manager:
            return await self._vector_manager.delete_conversation(conversation_id)
        return 0

    def vector_save(self) -> None:
        """保存向量索引"""
        if self._vector_manager:
            self._vector_manager.save()

    # --- 上下文 ---

    async def build_context_async(self, max_chars: int | None = None, query: str = "", conversation_id: str | None = None) -> str:
        conv_store = None
        if conversation_id:
            agent_id = getattr(self, '_agent_id', None)
            conv_store = get_conversation_store(agent_id, conversation_id)

        # 如果有查询，尝试向量召回增强
        if query:
            try:
                retrieved = await self.vector_retrieve(query, k=10)
                if retrieved:
                    retrieved_ids = {r.fact_id for r in retrieved}
                    self._context_builder._relevant_fact_ids = retrieved_ids
            except Exception as e:
                logger.warning(f"[Memory] Vector retrieve failed: {e}")

        return self._context_builder.build_context(max_chars, query=query, conversation_store=conv_store, conversation_id=conversation_id)

    def build_context(self, max_chars: int | None = None, query: str = "", conversation_id: str | None = None) -> str:
        """同步包装器：检测是否在事件循环中运行，选择合适的调用方式。"""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # 已在事件循环中，无法用 asyncio.run，使用同步回退
            conv_store = None
            if conversation_id:
                conv_store = get_conversation_store(self._agent_id, conversation_id)
            return self._context_builder.build_context(max_chars, query=query, conversation_store=conv_store, conversation_id=conversation_id)

        return asyncio.run(self.build_context_async(max_chars, query, conversation_id))

    # --- LLM 驱动的更新 ---

    async def extract_facts(
        self, message: str, llm_adapter=None, correction_hint: str = "", context_messages: str = ""
    ) -> tuple[str, list[FactItem]]:
        return await self._extractor.extract_facts(message, llm_adapter, correction_hint, context_messages)

    async def update_profile_from_message(
        self, message: str, llm_adapter=None, correction_hint: str = "", context_messages: str = "", conversation_id: str | None = None
    ) -> dict[str, str]:
        result = await self._extractor.update_profile_from_message(message, llm_adapter, correction_hint, context_messages)

        # 对话级facts写入conversation store
        if conversation_id and result.get("facts"):
            conv_facts = [f for f in result["facts"] if f.category in FACT_SCOPE_CONVERSATION]
            if conv_facts:
                conv_store = get_conversation_store(self._agent_id, conversation_id)
                conv_data = conv_store.load_data()
                self._fact_manager.merge_facts(conv_data, conv_facts)
                conv_store.save_data(conv_data)

        return result

    async def distill_conversation(
        self,
        messages: list[dict],
        llm_adapter=None,
        correction_hint: str = "",
        conversation_id: str | None = None,
    ) -> str | None:
        return await self._extractor.distill_conversation(messages, llm_adapter, correction_hint, conversation_id)

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
        now = utc_now()
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


class _LRUDict(OrderedDict):
    """简单的 LRU 字典，超限时自动淘汰最久未使用的条目."""

    def __init__(self, maxsize: int = 100):
        super().__init__()
        self.maxsize = maxsize

    def __setitem__(self, key, value):
        if key in self:
            self.move_to_end(key)
        super().__setitem__(key, value)
        while len(self) > self.maxsize:
            oldest_key, oldest_val = self.popitem(last=False)
            # 清理被淘汰的 store
            if hasattr(oldest_val, "close"):
                try:
                    oldest_val.close()
                except Exception:
                    pass
            logger.debug(f"[Memory] LRU evicted conversation store: {oldest_key}")

    def __getitem__(self, key):
        self.move_to_end(key)
        return super().__getitem__(key)


_conversation_stores: _LRUDict = _LRUDict(maxsize=100)


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
        engine = MemoryEngine(storage_path=path, agent_id=key)
        _engines[key] = engine
        return engine
