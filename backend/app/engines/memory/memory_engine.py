from __future__ import annotations

import asyncio
import re
import shutil
import threading
from collections import OrderedDict, deque
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from app.core.utils import utc_now, utc_now_dt

from app.core.config import settings
from app.runtime.provider.llm.adapter import llm_adapter
from .models import (
    MemoryData,
    ProfileData,
    FactItem,
    SummaryData,
    SummarySection,
    FACT_CATEGORIES,
    FACT_SCOPE_AGENT,
    FACT_SCOPE_CONVERSATION,
    SCOPE_GLOBAL,
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
)
from .store import (
    MemoryStore,
    agent_memory_dir,
    resolve_owner_agent_key,
    resolve_track_dir,
    sanitize_track_key,
)
from app.core.domain_policy import TRACK_OWNER, TRACK_USERS, TRACK_GROUPS
from .fact_manager import FactManager
from .extractor import MemoryExtractor
from .context_builder import ContextBuilder

if TYPE_CHECKING:
    from .vector_manager import VectorSearchManager


# ═══════════════════════════════════════════════════════════════════════
# 锁协议（并发安全设计，Phase 4 文档化）
# ═══════════════════════════════════════════════════════════════════════
# 本模块存在两级锁，职责不同、互不嵌套（避免死锁）：
#
# 1) store 锁（threading.RLock，MemoryStore 内部）：
#    保护 SQLite 单库读写。所有同步方法（load_data/save_data/mutate/
#    append_daily 等）内部自持；async 调用方须经 asyncio.to_thread 包裹，
#    因为 store 的同步 API 在 worker 线程中执行，asyncio.Lock 不可用。
#
# 2) 引擎级写锁（asyncio.Lock，self._async_lock，经 write_lock 暴露）：
#    串行化「读-改-写」跨步序列（API 端点 / 工作流工具 / 提取器写入段），
#    防止与蒸馏/画像更新并发时相互覆盖。
#
# 规则：
#   - 纯内存内变更（无跨 await 的中间态）→ 只走 store 锁（mutate 原子化）。
#   - 跨 await 的读-改-写序列 → 先拿 write_lock，再在锁内用 store 同步 API
#     （经 to_thread）完成，保证整段序列原子。
#   - 严禁在持有 write_lock 时再 await 任何可能反向获取 store 锁的代码
#     （本层所有 store 调用均已 to_thread，不重入 write_lock）。
#   - forget_facts / remember_fact 等门面方法已封装上述顺序，调用方勿再
#     直接摸 engine._store / _async_lock。
# ═══════════════════════════════════════════════════════════════════════



class MemoryEngine:
    """记忆引擎门面：组合存储、事实管理、LLM 提取、上下文组装等组件。"""

    def __init__(
        self,
        storage_path: Path | str | None = None,
        agent_id: str | None = None,
        embedding_provider=None,
        conversation_base_dir: Path | None = None,
    ):
        self._agent_id = agent_id or "_default"
        self._embedding_provider = embedding_provider

        if storage_path:
            path = Path(storage_path)
        else:
            path = agent_memory_dir(self._agent_id)

        self._store = MemoryStore(path)
        # 会话级 store 的根目录：轨道引擎指向自身轨道目录（users/{key}/conversations/…），
        # agents/ 引擎保持 None → 沿用 get_conversation_store 的 agents/{agent}/conversations 语义
        self._conversation_base_dir = Path(conversation_base_dir) if conversation_base_dir else None
        self._fact_manager = FactManager(self._store)
        self._async_lock = asyncio.Lock()
        self._extractor = MemoryExtractor(
            self._store, self._fact_manager, self._async_lock,
            agent_id=self._agent_id, conversation_base_dir=self._conversation_base_dir,
        )
        self._context_builder = ContextBuilder(self._store)
        
        self._vector_manager: VectorSearchManager | None = None

    # --- 会话级 store 访问（轨道感知） ---

    def _get_conv_store(self, conversation_id: str) -> MemoryStore:
        """返回本引擎对应的会话级 MemoryStore（轨道目录感知）。"""
        if self._conversation_base_dir is not None:
            return get_conversation_store_at(self._conversation_base_dir, conversation_id)
        return get_conversation_store(self._agent_id, conversation_id)

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

    async def remember_fact(self, fact: FactItem, conversation_id: str | None = None) -> None:
        """写库 + 向量入库（事实↔向量生命周期联动，Phase 3）。

        同步 add_fact 已把事实写进 store；此处补齐向量索引，使手动创建/工作流
        创建的事实立即可被语义检索。embedding 失败不抛（与 update_profile_from_message
        的 B2.3 降级策略一致），保证记忆主体写入不被向量子系统阻断。
        """
        await asyncio.to_thread(self.add_fact, fact)
        try:
            vm = self._get_vector_manager()
            await vm.add_fact(fact, conversation_id)
        except Exception as e:
            logger.warning(f"[Memory] Vector add after remember_fact failed: {e}")

    async def forget_fact_vector(self, fact_id: str) -> None:
        """向量摘除（删库后即时清向量，Phase 3）。失败仅告警不阻断。"""
        try:
            if self._vector_manager is not None:
                await self._vector_manager.remove(fact_id)
        except Exception as e:
            logger.warning(f"[Memory] Vector remove after delete_fact failed: {e}")

    async def sync_fact_vector(self, fact: FactItem, conversation_id: str | None = None) -> None:
        """事实更新后重同步向量：先摘旧向量再按新内容重嵌（Phase 3）。"""
        try:
            vm = self._get_vector_manager()
            await vm.remove(fact.id)
            await vm.add_fact(fact, conversation_id)
        except Exception as e:
            logger.warning(f"[Memory] Vector sync after update_fact failed: {e}")

    def clear_facts(self) -> None:
        self._fact_manager.clear_facts()

    def set_fact_pinned(self, fact_id: str, pinned: bool) -> bool:
        """置顶/取消置顶一条事实（store 锁内原子改写）。

        置顶事实在注入时绕过置信度与过期闸门并恒排最前（陪伴场景：
        生日、纪念日、过敏源等关键信息不因预算截断而丢失）。
        注意：该事实被矛盾归档替代后新事实不自动继承置顶。
        """
        def _apply(data):
            for f in data.facts:
                if f.id == fact_id and f.is_latest:
                    f.pinned = bool(pinned)
                    return True
            return False

        return bool(self._store.mutate(_apply))

    def forget_facts(self, matcher) -> int:
        """按匹配器遗忘事实（引擎写锁 + store 原子 mutate，返回删除条数）。

        matcher: callable(data) -> int，在 store 锁内 load→fn(data)→save，
        返回被遗忘（降置信）的事实条数。供自然语言 forget 操作调用，
        替代生产代码直接摸 engine._store.mutate。
        """
        return self._store.mutate(matcher)

    def promote_conversation_facts(self, conversation_id: str, fact_ids: list[str] | None = None) -> int:
        """方案A：将对话级facts提升到Agent级。

        提升后从对话级store中删除已提升的facts，避免注入时重复。

        Args:
            conversation_id: 来源对话ID
            fact_ids: 指定要提升的fact ID列表。为None时提升所有符合条件的facts。

        Returns:
            提升的fact数量
        """
        conv_store = self._get_conv_store(conversation_id)
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
                    if exp_time <= utc_now_dt():
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
            # （mutate 原子读改写：不覆盖并发的对话 facts 写入）
            def _remove_promoted(conv_data: MemoryData) -> None:
                conv_data.facts = [f for f in conv_data.facts if f.id not in promoted_ids]

            conv_store.mutate(_remove_promoted)

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
            conv_store = self._get_conv_store(conversation_id)
            # 摘要写入走 mutate 原子读改写（B3-1）：不覆盖并发的 facts/摘要写入
            conv_store.mutate(lambda data: self._markdown_to_summaries(data, content))
        else:
            self._store.mutate(lambda data: self._markdown_to_summaries(data, content))

    def parse_summary(self) -> dict[str, str]:
        data = self._store.load_data()
        return {
            "用户画像": data.summaries.user_profile.summary,
            "偏好设置": data.summaries.preferences.summary,
            "兴趣目标": data.summaries.interests.summary,
            "近期状态": data.summaries.recent_state.summary,
            "事件时间线": data.summaries.timeline.summary,
        }

    async def extract_knowledge(self, conversation: str, existing_knowledge: str = "", llm_adapter=None) -> str | None:
        """使用LLM从对话中提取知识点，并与现有知识库合并。"""
        return await self._extractor.extract_knowledge(conversation, existing_knowledge, llm_adapter)

    def clear_summaries(self) -> None:
        data = self._store.load_data()
        data.summaries = SummaryData()
        self._store.save_data(data)

    # --- 蒸馏游标 ---

    def get_distilled_turns(self, conversation_id: str | None = None) -> int:
        """读取蒸馏游标（上次蒸馏时的完整轮次数，防多 worker/重启重复蒸馏）。

        conversation_id 非空读对话级 store，否则读 Agent 级 store。
        """
        store = self._get_conv_store(conversation_id) if conversation_id else self._store
        return int(store.load_data().profile.distilled_turns or 0)

    def set_distilled_turns(self, conversation_id: str | None, turns: int) -> None:
        """写入蒸馏游标（store 原子 mutate，Phase 4 落盘替代内存 dict）。"""
        store = self._get_conv_store(conversation_id) if conversation_id else self._store

        def op(data: MemoryData) -> None:
            data.profile.distilled_turns = int(turns)

        store.mutate(op)

    # --- 每日记录 ---

    def load_daily(self, date: str | None = None, conversation_id: str | None = None) -> str:
        if conversation_id:
            conv_store = self._get_conv_store(conversation_id)
            return conv_store.load_daily(date)
        return self._store.load_daily(date)

    def append_daily(self, content: str, date: str | None = None, conversation_id: str | None = None) -> None:
        if conversation_id:
            conv_store = self._get_conv_store(conversation_id)
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
        conv_store = self._get_conv_store(conversation_id)
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
                    raw = llm_adapter.get_provider()
                    # 关键装配：LLMProvider.embed 是单文本协议（str → list[float]），
                    # 直接注入 VectorStore 会与批量协议错配——历史缺陷曾致
                    # vectors[i] 取到单个向量的第 i 个 float，全索引静默标量化。
                    # 统一经 LLMEmbeddingProvider（批量协议，直连 /embeddings）包装。
                    model = str(getattr(raw, "default_model", "") or "")
                    if "embed" not in model.lower():
                        model = "text-embedding-3-small"
                    from .vector_store import LLMEmbeddingProvider
                    self._embedding_provider = LLMEmbeddingProvider(raw, model=model)
                except Exception as e:
                    logger.warning(f"[Memory] Failed to access llm_adapter for embedding provider: {e}")

            if self._embedding_provider is None:
                raise RuntimeError(
                    "Embedding provider not available. "
                    "Ensure llm_adapter is configured with a provider that has embedding support."
                )

            from .vector_manager import VectorSearchManager
            # 向量索引跟随轨道目录（owner → agents/{key}/vectors，users → users/{key}/vectors）；
            # owner_key 与记忆同源（行级隔离，主人轨/平台用户轨互不串扰）
            self._vector_manager = VectorSearchManager(
                self._agent_id, self._embedding_provider,
                storage_path=self._store._path / "vectors",
                owner_key=self._store.owner_key,
            )
        return self._vector_manager

    @property
    def write_lock(self) -> asyncio.Lock:
        """引擎级写锁：与提取器写入段共用，供 API 端点/工作流工具串行化
        读-改-写序列，避免与蒸馏/画像更新并发时相互覆盖。"""
        return self._async_lock

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
        data = await asyncio.to_thread(self._store.load_data)
        for f in data.facts:
            if f.is_latest:
                facts.append(f)

        if conversation_id:
            conv_store = self._get_conv_store(conversation_id)
            conv_data = await asyncio.to_thread(conv_store.load_data)
            for f in conv_data.facts:
                if f.is_latest:
                    facts.append(f)
        
        return await vm.rebuild(facts, conversation_id)

    async def vector_delete_conversation(self, conversation_id: str) -> int:
        """删除对话相关向量"""
        if self._vector_manager:
            return await self._vector_manager.delete_conversation(conversation_id)
        return 0

    # --- 上下文 ---

    async def build_context_async(
        self, max_chars: int | None = None, query: str = "", conversation_id: str | None = None, allowed_scopes: set[str] | None = None
    ) -> str:
        conv_store = None
        if conversation_id:
            conv_store = self._get_conv_store(conversation_id)

        # 如果有查询，尝试向量召回增强
        retrieved_ids: set[str] | None = None
        if query:
            try:
                retrieved = await self.vector_retrieve(query, k=10)
                if retrieved:
                    retrieved_ids = {r.fact_id for r in retrieved}
            except Exception as e:
                logger.warning(f"[Memory] Vector retrieve failed: {e}")

        return self._context_builder.build_context(
            max_chars, query=query, conversation_store=conv_store, conversation_id=conversation_id,
            relevant_fact_ids=retrieved_ids, allowed_scopes=allowed_scopes,
        )

    def build_context_sync(
        self, max_chars: int | None = None, query: str = "", conversation_id: str | None = None, allowed_scopes: set[str] | None = None
    ) -> str:
        """同步上下文组装（与 build_context 的事件循环内回退分支相同，不含向量召回）。

        供 async 调用方配合 asyncio.to_thread 使用：worker 线程中检测不到运行中的
        事件循环，不能走 build_context 的分支（否则会嵌套 asyncio.run）。
        """
        conv_store = None
        if conversation_id:
            conv_store = self._get_conv_store(conversation_id)
        return self._context_builder.build_context(
            max_chars, query=query, conversation_store=conv_store, conversation_id=conversation_id, allowed_scopes=allowed_scopes,
        )

    def build_context(
        self, max_chars: int | None = None, query: str = "", conversation_id: str | None = None, allowed_scopes: set[str] | None = None
    ) -> str:
        """同步包装器：检测是否在事件循环中运行，选择合适的调用方式。"""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # 已在事件循环中，无法用 asyncio.run，使用同步回退
            return self.build_context_sync(max_chars, query=query, conversation_id=conversation_id, allowed_scopes=allowed_scopes)

        return asyncio.run(self.build_context_async(max_chars, query, conversation_id, allowed_scopes=allowed_scopes))

    # --- LLM 驱动的更新 ---

    async def extract_facts(
        self,
        message: str,
        llm_adapter=None,
        correction_hint: str = "",
        context_messages: str = "",
        default_scope: str = SCOPE_GLOBAL,
        group_id: str = "",
    ) -> tuple[str, list[FactItem]]:
        return await self._extractor.extract_facts(
            message,
            llm_adapter,
            correction_hint,
            context_messages,
            default_scope=default_scope,
            group_id=group_id,
        )

    async def update_profile_from_message(
        self,
        message: str,
        llm_adapter=None,
        correction_hint: str = "",
        context_messages: str = "",
        conversation_id: str | None = None,
        default_scope: str = SCOPE_GLOBAL,
        group_id: str = "",
    ) -> dict[str, str]:
        result = await self._extractor.update_profile_from_message(
            message,
            llm_adapter,
            correction_hint,
            context_messages,
            conversation_id=conversation_id,
            default_scope=default_scope,
            group_id=group_id,
        )

        # 对话级facts写入conversation store
        if conversation_id and result.get("facts"):
            conv_facts = [f for f in result["facts"] if f.category in FACT_SCOPE_CONVERSATION]
            if conv_facts:
                conv_store = self._get_conv_store(conversation_id)
                # conv facts 写入走 store.mutate（锁内原子读改写，B3-1）：
                # 原 load→merge→save 三步跨锁执行，与摘要/蒸馏写同一 conv store
                # 并发时后写者整体覆盖先写者（丢事实）
                await asyncio.to_thread(
                    conv_store.mutate,
                    lambda data: self._fact_manager.merge_facts(data, conv_facts),
                )

        # 增量向量化新提取的事实（embedding 失败不影响主流程，B2.3）
        new_facts = result.get("facts") or []
        if new_facts:
            try:
                await self.vector_dedup(new_facts, conversation_id)
            except Exception as e:
                logger.warning(f"[Memory] Vector dedup after profile update failed: {e}")

        return result

    # --- 重置 ---

    def reset_all(self) -> None:
        self._store.reset_all()

    # --- 内部兼容方法（测试使用） ---

    @property
    def _path(self):
        return self._store._path

    def _find_similar_fact(self, data: MemoryData, fact: FactItem):
        return self._fact_manager._find_similar_fact(data, fact)

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

    # 淘汰延迟一代再关闭（B3-7）：并发 fast-path（.get()）可能刚取得被淘汰 store
    # 的引用，立即 close 会造成"拿到即被关"；延迟一代给在途调用留出使用窗口，
    # fd 上界仅 maxsize+1。
    _graveyard: deque  # 元素为 (key, store) | None

    def __init__(self, maxsize: int = 100):
        super().__init__()
        self.maxsize = maxsize
        self._graveyard = deque(maxlen=1)
        self._graveyard.append(None)

    def __setitem__(self, key, value):
        if key in self:
            self.move_to_end(key)
        super().__setitem__(key, value)
        while len(self) > self.maxsize:
            oldest_key, oldest_val = self.popitem(last=False)
            # 先关闭上一代墓地的 store，再把本次淘汰的放入墓地
            dying = self._graveyard[0]
            if dying is not None:
                dying_key, dying_store = dying
                if hasattr(dying_store, "close"):
                    try:
                        dying_store.close()
                    except Exception:
                        # LRU 淘汰清理：store 可能已关闭，属预期情况
                        logger.debug(f"[Memory] LRU 淘汰关闭 store 异常（忽略）: {dying_key}", exc_info=True)
            self._graveyard.clear()
            self._graveyard.append((oldest_key, oldest_val))
            logger.debug(f"[Memory] LRU evicted conversation store: {oldest_key}")

    def __getitem__(self, key):
        self.move_to_end(key)
        return super().__getitem__(key)


_conversation_stores: _LRUDict = _LRUDict(maxsize=100)


def get_conversation_store_at(base_dir: Path, conversation_id: str) -> MemoryStore:
    """返回以 base_dir/conversations/{conversation_id} 为根的对话级 MemoryStore。

    供轨道引擎使用（如 users/{user_key}/conversations/…），与
    get_conversation_store 共享同一 LRU 缓存（键含根目录，互不冲突）。
    """
    base = Path(base_dir)
    key = f"@{base}:{conversation_id}"
    # 快路径用 .get()（原子且不做 move_to_end 变异，B3-7）：
    # 原 `key in` + `[]` 两步会被并发淘汰插刀（KeyError / move_to_end 竞态）
    store = _conversation_stores.get(key)
    if store is not None:
        return store
    with _engine_lock:
        store = _conversation_stores.get(key)
        if store is not None:
            return store
        store = MemoryStore(base / "conversations" / conversation_id)
        _conversation_stores[key] = store
        return store


def get_conversation_store(agent_id: str | None, conversation_id: str) -> MemoryStore:
    """返回对话级 MemoryStore，隔离 summaries/daily/dynamic_context。
    
    Args:
        agent_id: Agent ID，如果为None则使用默认Agent
        conversation_id: 对话ID
    
    Returns:
        对话级MemoryStore实例
    """
    key = f"{agent_id or '_default'}:{conversation_id}"
    # 快路径 .get()（同 get_conversation_store_at，B3-7）
    store = _conversation_stores.get(key)
    if store is not None:
        return store
    with _engine_lock:
        store = _conversation_stores.get(key)
        if store is not None:
            return store
        agent_key = agent_id or "_default"
        path = agent_memory_dir(agent_key) / "conversations" / conversation_id
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
        path = agent_memory_dir(key)
        engine = MemoryEngine(storage_path=path, agent_id=key)
        _engines[key] = engine
        return engine


def remove_engine(agent_id: str | None = None) -> None:
    """从注册表移除指定 Agent 的记忆引擎缓存（不落盘，仅清缓存）。

    替代生产代码直接摸 _engines.pop。删除内存后再次 get_memory_engine
    会重新构建。
    """
    key = agent_id or "_default"
    with _engine_lock:
        _engines.pop(key, None)


# --- 群友画像块（§8.5.10 本期实现：群成员轨读侧） ---

# 画像块默认限幅：成员数 / 每人事实条数 / 总字符数
GROUP_MEMBER_BLOCK_MAX_MEMBERS = 10
GROUP_MEMBER_BLOCK_FACTS_PER_MEMBER = 8
GROUP_MEMBER_BLOCK_MAX_CHARS = 3600


def build_group_members_block(
    members: list[dict],
    *,
    exclude_keys: set[str] | None = None,
    max_members: int = GROUP_MEMBER_BLOCK_MAX_MEMBERS,
    facts_per_member: int = GROUP_MEMBER_BLOCK_FACTS_PER_MEMBER,
    max_chars: int = GROUP_MEMBER_BLOCK_MAX_CHARS,
) -> str:
    """构建「群友画像块」：逐成员读 users 轨 top 事实摘要（同步 SQLite 读）。

    供平台群聊注入（context_service.inject_memory）与站内群聊
    （GroupChatManager）共用；单轨读取复用 get_track_engine，不复制存取逻辑。
    同步函数含 SQLite 读，调用方在事件循环内须用 asyncio.to_thread 包裹。

    Args:
        members: 成员条目列表，每项 {"sender_id": str, "sender_name": str,
            "user_key": str}
        exclude_keys: 需排除的 user_key 集合（如说话成员已单独注入完整记忆）
        max_members: 成员数上限（超出按传入顺序截断，调用方应让最近发言优先）
        facts_per_member: 每人事实条数上限（取最近生成的 top 条目）
        max_chars: 块总长限幅（超出即停止追加）

    Returns:
        形如「[群友] 昵称(sender_id)：\\n- 事实…」的拼接文本；
        无任何成员有事实时返回 ""（调用方跳过注入）。
    """
    exclude = exclude_keys or set()
    sections: list[str] = []
    used_chars = 0
    seen: set[str] = set()

    for member in members:
        if len(sections) >= max_members or used_chars >= max_chars:
            break
        key = str((member or {}).get("user_key") or "").strip()
        if not key or key in exclude or key in seen:
            continue
        seen.add(key)
        try:
            engine = get_track_engine(TRACK_USERS, key)
            data = engine.load_data()
        except Exception as e:
            logger.warning(f"[Memory] Group member track read failed: key={key}, error={e}")
            continue
        # 严格过滤私密事实：群友画像仅展示公开/群聊事实，严禁泄露他人私聊秘密
        facts = [
            f for f in data.facts
            if f.is_latest and getattr(f, "scope", "global") != "private"
        ][-facts_per_member:]
        if not facts:
            continue
        name = str((member.get("sender_name") or "").strip())
        sender_id = str((member.get("sender_id") or "").strip())
        if name and sender_id:
            header = f"[群友] {name}({sender_id})："
        elif name:
            header = f"[群友] {name}："
        else:
            header = f"[群友] ({sender_id})："
        section = "\n".join([header] + [f"- {f.content}" for f in facts])
        if used_chars + len(section) > max_chars:
            break
        sections.append(section)
        used_chars += len(section) + 2  # 段间空行

    if not sections:
        return ""
    return "\n\n".join(sections)


# --- 双轨引擎注册表（洋葱架构 §8.5.2 / §13 B18） ---

_track_engines: dict[str, MemoryEngine] = {}


def get_track_engine(track: str, user_key: str = "") -> MemoryEngine:
    """按记忆轨道返回引擎（owner / users / groups 三轨）。

    - owner：委托 get_memory_engine（目录别名解析见 store.resolve_track_dir），
      与工作台主 Agent 引擎是同一实例，保证读写一致（M2=B）。
    - users：users/{user_key}/ 目录独立引擎，读写逻辑复用 MemoryEngine。
    - groups：groups/{group_key}/ 目录独立引擎，用于独立粉丝群的群记忆。
    """
    if track == TRACK_OWNER:
        return get_memory_engine(resolve_owner_agent_key())
    if track in (TRACK_USERS, TRACK_GROUPS):
        safe_key = sanitize_track_key(user_key)
        key = f"{track}/{safe_key}"
        if key in _track_engines:
            return _track_engines[key]
        with _engine_lock:
            if key in _track_engines:
                return _track_engines[key]
            track_dir = resolve_track_dir(track, safe_key)
            engine = MemoryEngine(
                storage_path=track_dir,
                agent_id=key,
                conversation_base_dir=track_dir,
            )
            _track_engines[key] = engine
            return engine
    raise ValueError(f"Unknown memory track: {track!r}")
