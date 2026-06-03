import asyncio
import json
import re
from datetime import datetime, timezone

from loguru import logger

from .models import MemoryData, FactItem, FACT_CATEGORIES, _SUMMARY_SECTION_MAP, summaries_to_markdown
from .prompts import _FACT_EXTRACT_PROMPT, _DISTILL_PROMPT, _MERGE_SUMMARY_PROMPT, _SUMMARY_EXTRACT_PROMPT, _KNOWLEDGE_EXTRACT_PROMPT
from .store import MemoryStore
from .fact_manager import FactManager


class MemoryExtractor:
    """LLM 交互层：事实提取、对话蒸馏、JSON 解析。"""

    FACT_CONFIDENCE_THRESHOLD = 0.7

    def __init__(self, store: MemoryStore, fact_manager: FactManager, async_lock: asyncio.Lock):
        self._store = store
        self._fact_manager = fact_manager
        self._async_lock = async_lock

    @staticmethod
    def _get_llm_adapter():
        from app.runtime.provider.llm.adapter import llm_adapter
        return llm_adapter

    # --- 事实提取 ---

    async def extract_facts(
        self, message: str, llm_adapter=None, correction_hint: str = "", context_messages: str = ""
    ) -> tuple[str, list[FactItem]]:
        stripped = message.strip()
        if not stripped:
            return "", []

        if llm_adapter is None:
            try:
                llm_adapter = self._get_llm_adapter()
            except Exception as e:
                logger.warning(f"[Memory] No LLM adapter available: {e}")
                return "", []

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
            )
            response_text = (
                result.strip() if isinstance(result, str) else str(result).strip()
            )
            logger.info(f"[Memory] LLM fact extract response: {response_text}")

            parsed = self._parse_llm_json(response_text)
            if parsed is None:
                return "", []

            profile_name = parsed.get("profile_name", "").strip()[:20]
            facts = self._parse_facts_from_raw(parsed.get("facts", []))

            return profile_name, facts

        except Exception as e:
            logger.warning(f"[Memory] Fact extraction failed: {e}")
            return "", []

    # --- 档案更新（LLM 调用 + 数据写入，异步锁保护写入段） ---

    async def update_profile_from_message(
        self, message: str, llm_adapter=None, correction_hint: str = "", context_messages: str = ""
    ) -> dict[str, str]:
        profile_name, facts = await self.extract_facts(message, llm_adapter, correction_hint, context_messages)

        updates = {}
        async with self._async_lock:
            data = self._store.load_data()

            if profile_name:
                old_name = data.profile.name
                data.profile.name = profile_name
                data.profile.updated_at = datetime.now(timezone.utc).isoformat()
                updates["name"] = profile_name

                if old_name and old_name != profile_name:
                    self._fact_manager.deprecate_old_name_facts(data, old_name, profile_name)

            self._fact_manager.merge_facts(data, facts)
            self._store.save_data(data)

        if updates:
            logger.info(f"[Memory] Profile updated: {updates}")

        return updates

    # --- 对话蒸馏（LLM 调用 + 数据写入，异步锁保护写入段） ---

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

        data = self._store.load_data()
        current_name = data.profile.name or "(未知)"
        current_facts = "\n".join(
            f"  - [{f.category}|{f.confidence:.1f}] {f.content}"
            for f in data.facts
        ) or "(无)"
        current_summary = summaries_to_markdown(data) or "(空)"

        prompt = _DISTILL_PROMPT.format(
            current_name=current_name,
            current_facts=current_facts,
            current_summary=current_summary,
            conversation_summary=conv_summary,
            correction_hint=correction_hint,
        )

        try:
            if llm_adapter is None:
                llm_adapter = self._get_llm_adapter()

            result = await llm_adapter.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2000,
            )
            response_text = (
                result.strip() if isinstance(result, str) else str(result).strip()
            )
            logger.info(f"[Memory] Distill response: {response_text[:300]}")

            parsed = self._parse_llm_json(response_text)
            if parsed is None:
                return None

            now = datetime.now(timezone.utc).isoformat()

            profile_name = parsed.get("profile_name", "").strip()
            valid_facts = self._parse_facts_from_raw(parsed.get("facts", []), source="distill")
            raw_summary = parsed.get("summary", {})
            static_facts = parsed.get("static_facts", [])
            dynamic_context = parsed.get("dynamic_context", [])

            async with self._async_lock:
                data = self._store.load_data()

                # 蒸馏只更新 Summary 和 Facts，不更新 Profile
                # Profile（name、static_facts、dynamic_context）由事实提取单独维护

                self._fact_manager.merge_facts(data, valid_facts)

                if isinstance(raw_summary, dict):
                    for cn_name, attr_name in _SUMMARY_SECTION_MAP.items():
                        text = raw_summary.get(cn_name, "").strip()
                        if text:
                            section = getattr(data.summaries, attr_name)
                            section.summary = text
                            section.updated_at = now

                self._store.save_data(data)

            logger.info(
                f"[Memory] Distill completed: name={data.profile.name}, facts={len(data.facts)}"
            )
            return summaries_to_markdown(data)

        except Exception as e:
            logger.warning(f"[Memory] Distillation failed: {e}")
            return None

    async def merge_summary(
        self, old_summary: str, new_summary: str, llm_adapter=None
    ) -> str | None:
        """将旧摘要与新观察合并为一份统一的摘要。"""
        if llm_adapter is None:
            try:
                llm_adapter = self._get_llm_adapter()
            except Exception as e:
                logger.warning(f"[Memory] No LLM adapter available: {e}")
                return None

        try:
            prompt = _MERGE_SUMMARY_PROMPT.format(
                old_summary=old_summary,
                new_summary=new_summary,
            )

            result = await llm_adapter.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2000,
            )
            response_text = (
                result.strip() if isinstance(result, str) else str(result).strip()
            )
            logger.info(f"[Memory] Merge response: {response_text[:300]}")

            return response_text

        except Exception as e:
            logger.warning(f"[Memory] Summary merge failed: {e}")
            return None

    async def extract_summary_sections(
        self, content: str, llm_adapter=None
    ) -> dict | None:
        """使用LLM从摘要内容中提取五个部分：用户画像、偏好设置、兴趣目标、近期状态、事件时间线。"""
        if llm_adapter is None:
            try:
                llm_adapter = self._get_llm_adapter()
            except Exception as e:
                logger.warning(f"[Memory] No LLM adapter available: {e}")
                return None

        try:
            prompt = _SUMMARY_EXTRACT_PROMPT.format(content=content)

            result = await llm_adapter.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=1000,
            )
            response_text = (
                result.strip() if isinstance(result, str) else str(result).strip()
            )
            logger.info(f"[Memory] Summary sections extract response: {response_text[:300]}")

            parsed = self._parse_llm_json(response_text)
            if parsed is None:
                return None

            return parsed

        except Exception as e:
            logger.warning(f"[Memory] Summary sections extract failed: {e}")
            return None

    async def extract_knowledge(
        self, conversation: str, llm_adapter=None
    ) -> str | None:
        """使用LLM从对话中提取知识点。"""
        if llm_adapter is None:
            try:
                llm_adapter = self._get_llm_adapter()
            except Exception as e:
                logger.warning(f"[Memory] No LLM adapter available: {e}")
                return None

        try:
            prompt = _KNOWLEDGE_EXTRACT_PROMPT.format(conversation=conversation)

            result = await llm_adapter.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=1500,
            )
            response_text = (
                result.strip() if isinstance(result, str) else str(result).strip()
            )
            logger.info(f"[Memory] Knowledge extract response: {response_text[:300]}")

            return response_text

        except Exception as e:
            logger.warning(f"[Memory] Knowledge extract failed: {e}")
            return None

    # --- 公共解析方法（消除 extract_facts 和 distill_conversation 的重复代码） ---

    @staticmethod
    def _parse_llm_json(response_text: str) -> dict | None:
        """从 LLM 响应中解析 JSON，处理 ``` 包裹等格式。"""
        json_str = response_text
        if "```" in json_str:
            json_match = re.search(
                r"```(?:json)?\s*(\{.*?\})\s*```", json_str, re.DOTALL
            )
            if json_match:
                json_str = json_match.group(1)
        json_str = json_str.strip()
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning(
                f"[Memory] Failed to parse LLM JSON response: {e}, raw: {response_text[:200]}"
            )
            return None

    def _parse_facts_from_raw(
        self, raw_facts: list, source: str = "conversation"
    ) -> list[FactItem]:
        """从 LLM 返回的原始事实列表中解析出有效的 FactItem。"""
        if not isinstance(raw_facts, list):
            return []

        facts = []
        for raw in raw_facts:
            content = raw.get("content", "").strip()
            category = raw.get("category", "context")
            confidence = raw.get("confidence", 0.8)
            source_error = raw.get("source_error", "")
            expires_at = raw.get("expires_at", "") or None
            supersedes = raw.get("supersedes", "") or None

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
                    source=source,
                    expires_at=expires_at,
                )
            )

            # 处理 LLM 标记的 supersedes：降低被替代事实的置信度
            if supersedes:
                data = self._store.load_data()
                self._fact_manager.apply_supersedes(data, supersedes, content)
                self._store.save_data(data)

        return facts
