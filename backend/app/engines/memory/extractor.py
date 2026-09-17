import asyncio
from pathlib import Path

from loguru import logger

from app.core.utils import parse_llm_json, utc_now, extract_llm_text
from app.runtime.provider.llm.adapter import llm_adapter
from app.runtime.provider.llm.types import RouteHint
from .models import FACT_SCOPE_AGENT, FactItem, FACT_CATEGORIES
from .prompts import _FACT_EXTRACT_PROMPT, _KNOWLEDGE_EXTRACT_PROMPT
from .store import MemoryStore
from .fact_manager import FactManager

# 事实内容入库上限（与 API 端点 CreateFactRequest 的 max_length=500 对齐，
# 防止 LLM 幻觉产出超长内容撑爆存储/向量索引/注入预算）
FACT_CONTENT_MAX_CHARS = 500


class MemoryExtractor:
    """LLM 交互层：事实提取、对话蒸馏、JSON 解析。"""

    FACT_CONFIDENCE_THRESHOLD = 0.7

    def __init__(self, store: MemoryStore, fact_manager: FactManager, async_lock: asyncio.Lock, agent_id: str | None = None, conversation_base_dir: Path | None = None):
        self._store = store
        self._agent_id = agent_id
        self._fact_manager = fact_manager
        self._async_lock = async_lock
        # 轨道引擎的对话级 store 根目录（users/{key}/conversations/…）；
        # None 时沿用 agents/{agent}/conversations 布局（owner 轨）
        self._conversation_base_dir = conversation_base_dir

    @staticmethod
    def _get_llm_adapter():
        return llm_adapter

    def _get_conv_store(self, conversation_id: str) -> MemoryStore:
        """对话级 store（轨道感知）：与 MemoryEngine._get_conv_store 同规则。"""
        if self._conversation_base_dir is not None:
            from .memory_engine import get_conversation_store_at
            return get_conversation_store_at(self._conversation_base_dir, conversation_id)
        from .memory_engine import get_conversation_store
        return get_conversation_store(self._agent_id, conversation_id)

    # --- 事实提取 ---

    async def _extract_raw(
        self, message: str, llm_adapter=None, correction_hint: str = "", context_messages: str = ""
    ) -> tuple[str, list[FactItem], list[tuple[str, str]]]:
        """LLM 提取 + 解析（不落库）。

        Returns:
            (profile_name, facts, supersedes_ops)
            supersedes_ops 为 (被替代文本, 新内容) 列表，由调用方在
            写入事务内统一应用——替代旧版每条 supersedes 一次全量
            load/save 的 N+1 写放大。
        """
        stripped = message.strip()
        if not stripped:
            return "", [], []

        if llm_adapter is None:
            try:
                llm_adapter = self._get_llm_adapter()
            except Exception as e:
                logger.warning(f"[Memory] No LLM adapter available: {e}")
                return "", [], []

        try:
            prompt = _FACT_EXTRACT_PROMPT.format(message=stripped)
            if correction_hint:
                prompt += "\n\n" + correction_hint
            if context_messages:
                prompt += f"\n\n对话上下文（最近几条消息）：\n{context_messages}"

            result = await llm_adapter.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=500,
                route_hint=RouteHint.CHAT,
            )
            response_text = extract_llm_text(result)
            logger.info(f"[Memory] LLM fact extract response: {response_text}")

            parsed = parse_llm_json(response_text)
            if parsed is None:
                return "", [], []

            profile_name = parsed.get("profile_name", "").strip()[:20]
            facts, supersedes_ops = await self._parse_facts_from_raw(parsed.get("facts", []))

            return profile_name, facts, supersedes_ops

        except Exception as e:
            logger.warning(f"[Memory] Fact extraction failed: {e}")
            return "", [], []

    async def extract_facts(
        self, message: str, llm_adapter=None, correction_hint: str = "", context_messages: str = ""
    ) -> tuple[str, list[FactItem]]:
        profile_name, facts, supersedes_ops = await self._extract_raw(
            message, llm_adapter, correction_hint, context_messages
        )

        # supersedes 统一应用：1 次 load + 1 次 save（旧版每条一次全量替换）
        if supersedes_ops:
            async with self._async_lock:
                data = await asyncio.to_thread(self._store.load_data)
                for supersedes_text, new_content in supersedes_ops:
                    self._fact_manager.apply_supersedes(data, supersedes_text, new_content)
                await asyncio.to_thread(self._store.save_data, data)

        return profile_name, facts

    # --- 档案更新（LLM 调用 + 数据写入，异步锁保护写入段） ---

    async def update_profile_from_message(
        self, message: str, llm_adapter=None, correction_hint: str = "", context_messages: str = "", conversation_id: str | None = None
    ) -> dict[str, str]:
        profile_name, facts, supersedes_ops = await self._extract_raw(
            message, llm_adapter, correction_hint, context_messages
        )

        # 给facts添加溯源信息
        for f in facts:
            if conversation_id and not f.source_conversation_id:
                f.source_conversation_id = conversation_id
            if message and not f.source_message:
                f.source_message = message[:200]

        updates = {}
        async with self._async_lock:
            data = await asyncio.to_thread(self._store.load_data)

            # supersedes 在同一事务段内统一应用（旧版在解析阶段逐条全量 save）
            for supersedes_text, new_content in supersedes_ops:
                self._fact_manager.apply_supersedes(data, supersedes_text, new_content)

            if profile_name:
                old_name = data.profile.name
                data.profile.name = profile_name
                data.profile.updated_at = utc_now()
                updates["name"] = profile_name

                if old_name and old_name != profile_name:
                    self._fact_manager.deprecate_old_name_facts(data, old_name, profile_name)

            # 只合并Agent级共享的facts（preference/knowledge/correction）
            from .models import FACT_SCOPE_AGENT
            agent_facts = [f for f in facts if f.category in FACT_SCOPE_AGENT]
            # merge_facts 为纯 CPU（分词+相似度），放线程池避免阻塞事件循环
            await asyncio.to_thread(self._fact_manager.merge_facts, data, agent_facts)
            await asyncio.to_thread(self._store.save_data, data)

        # 返回提取到的所有facts，由MemoryEngine层决定对话级facts的写入
        updates["facts"] = facts
        if updates.get("name"):
            logger.info(f"[Memory] Profile updated: name={updates['name']}")
        if facts:
            logger.info(f"[Memory] Extracted {len(facts)} facts ({len(agent_facts)} agent-scoped, {len(facts) - len(agent_facts)} conversation-scoped)")

        return updates

    async def extract_knowledge(
        self, conversation: str, existing_knowledge: str = "", llm_adapter=None
    ) -> str | None:
        """使用LLM从对话中提取知识点，并与现有知识库合并。"""
        if llm_adapter is None:
            try:
                llm_adapter = self._get_llm_adapter()
            except Exception as e:
                logger.warning(f"[Memory] No LLM adapter available: {e}")
                return None

        try:
            prompt = _KNOWLEDGE_EXTRACT_PROMPT.format(
                conversation=conversation,
                existing_knowledge=existing_knowledge or "(空)",
            )

            result = await llm_adapter.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=1500,
                route_hint=RouteHint.CHAT,
            )
            response_text = extract_llm_text(result)
            logger.info(f"[Memory] Knowledge extract response: {response_text[:300]}")

            return response_text

        except Exception as e:
            logger.warning(f"[Memory] Knowledge extract failed: {e}")
            return None

    # --- 公共解析方法（消除 extract_facts 和 distill_conversation 的重复代码） ---
    # JSON 解析已统一收口到 core.utils.parse_llm_json（原 _parse_llm_json 已删除）

    async def _parse_facts_from_raw(
        self, raw_facts: list, source: str = "conversation", conversation_id: str | None = None, original_message: str = ""
    ) -> tuple[list[FactItem], list[tuple[str, str]]]:
        """从 LLM 返回的原始事实列表解析出有效的 FactItem。

        纯解析、不落库：supersedes 关系以 (被替代文本, 新内容) 列表返回，
        由调用方在写入事务内统一应用——替代旧版每条 supersedes 一次
        全量 load/save 的 N+1 写放大（K 条 supersedes = K 次全量替换写）。
        仅 FACT_SCOPE_AGENT 类别收集 supersedes（与旧版落库规则一致，
        对话级 supersedes 不写 Agent 级 store）。
        """
        if not isinstance(raw_facts, list):
            return [], []

        facts: list[FactItem] = []
        supersedes_ops: list[tuple[str, str]] = []
        for raw in raw_facts:
            if not isinstance(raw, dict):
                logger.warning(f"[Memory] Skipping non-dict fact entry: {type(raw)}")
                continue
            content = raw.get("content", "").strip()[:FACT_CONTENT_MAX_CHARS]
            category = raw.get("category", "context")
            confidence = raw.get("confidence", 0.8)
            source_error = raw.get("source_error", "").strip()[:200]
            expires_at = raw.get("expires_at", "") or None
            supersedes = raw.get("supersedes", "") or None

            if not content:
                continue
            if category not in FACT_CATEGORIES:
                category = "context"
            try:
                # 夹取到 [0,1]：LLM 偶发返回越界置信度会污染排序权重
                confidence = min(1.0, max(0.0, float(confidence)))
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
                    source=source,
                    expires_at=expires_at,
                    source_conversation_id=conversation_id or "",
                    source_message=original_message[:200] if original_message else "",
                )
            )

            if supersedes and category in FACT_SCOPE_AGENT:
                supersedes_ops.append((str(supersedes), content))

        return facts, supersedes_ops
