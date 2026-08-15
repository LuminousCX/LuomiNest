import threading

from loguru import logger

from app.runtime.provider.llm.types import RouteHint


class TokenCounter:
    def count_tokens(self, messages: list[dict], trusted_token_usage: int = 0) -> int:
        if trusted_token_usage > 0:
            return trusted_token_usage

        total = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total += self._estimate_tokens(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict):
                        if part.get("type") == "text":
                            total += self._estimate_tokens(part.get("text", ""))
                        elif part.get("type") == "image_url":
                            total += 765

            tool_calls = msg.get("tool_calls")
            if tool_calls:
                import json
                total += self._estimate_tokens(json.dumps(tool_calls, ensure_ascii=False))

        return total

    def count_messages(self, messages: list[dict]) -> int:
        """Alias for count_tokens without trusted usage — for clarity in budget checks."""
        return self.count_tokens(messages)

    def _estimate_tokens(self, text: str) -> int:
        chinese_count = len([c for c in text if "\u4e00" <= c <= "\u9fff"])
        other_count = len(text) - chinese_count
        return int(chinese_count * 0.6 + other_count * 0.3)

    def get_context_window_for_model(self, provider: str, model: str) -> int:
        """获取模型的上下文窗口大小。

        优先级：Provider能力表 > 配置值 > 默认16384
        """
        try:
            from app.runtime.provider.llm.capabilities import get_capabilities
            caps = get_capabilities(provider, model)
            if caps.default_context_window > 0:
                return caps.default_context_window
        except ImportError:
            # capabilities 模块不可用属可选依赖降级，静默回退到配置值
            pass
        except Exception:
            # 能力表查询自身的异常（KeyError/ValueError 等）不可吞掉，否则
            # 配置错误会被静默回退的默认窗口 16384 掩盖
            logger.warning(
                f"[Context] get_capabilities 查询异常，回退配置默认窗口: "
                f"provider={provider}, model={model}",
                exc_info=True,
            )

        from app.core.config import get_settings
        settings = get_settings()
        if settings.LLM_CONTEXT_WINDOW_SIZE > 0:
            return settings.LLM_CONTEXT_WINDOW_SIZE

        return 16384


class ContextTruncator:
    @staticmethod
    def _split_system_rest(messages: list[dict]) -> tuple[list[dict], list[dict]]:
        first_non_system = 0
        for i, msg in enumerate(messages):
            if msg.get("role") != "system":
                first_non_system = i
                break
        return messages[:first_non_system], messages[first_non_system:]

    @staticmethod
    def _ensure_user_message(
        system_messages: list[dict],
        truncated: list[dict],
        original_messages: list[dict],
    ) -> list[dict]:
        if truncated and truncated[0].get("role") == "user":
            return system_messages + truncated

        first_user = next((m for m in original_messages if m.get("role") == "user"), None)
        if first_user is None:
            return system_messages + truncated

        return system_messages + [first_user] + truncated

    def fix_messages(self, messages: list[dict]) -> list[dict]:
        if not messages:
            return messages

        fixed: list[dict] = []
        pending_assistant: dict | None = None
        pending_tools: list[dict] = []

        def flush_pending_if_valid():
            nonlocal pending_assistant, pending_tools
            if pending_assistant is not None and pending_tools:
                fixed.append(pending_assistant)
                fixed.extend(pending_tools)
            pending_assistant = None
            pending_tools = []

        for msg in messages:
            if msg.get("role") == "tool":
                if pending_assistant is not None:
                    pending_tools.append(msg)
                continue

            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                flush_pending_if_valid()
                pending_assistant = msg
                continue

            flush_pending_if_valid()
            fixed.append(msg)

        flush_pending_if_valid()
        return fixed

    def truncate_by_dropping_oldest_turns(
        self,
        messages: list[dict],
        drop_turns: int = 1,
    ) -> list[dict]:
        if drop_turns <= 0:
            return messages

        system_messages, non_system_messages = self._split_system_rest(messages)

        if len(non_system_messages) // 2 <= drop_turns:
            truncated_non_system = []
        else:
            truncated_non_system = non_system_messages[drop_turns * 2:]

        index = next(
            (i for i, item in enumerate(truncated_non_system) if item.get("role") == "user"),
            None,
        )
        if index is not None:
            truncated_non_system = truncated_non_system[index:]

        result = self._ensure_user_message(system_messages, truncated_non_system, messages)
        return self.fix_messages(result)

    def truncate_by_halving(self, messages: list[dict]) -> list[dict]:
        if len(messages) <= 2:
            return messages

        system_messages, non_system_messages = self._split_system_rest(messages)

        messages_to_delete = len(non_system_messages) // 2
        if messages_to_delete == 0:
            return messages

        truncated_non_system = non_system_messages[messages_to_delete:]

        index = next(
            (i for i, item in enumerate(truncated_non_system) if item.get("role") == "user"),
            None,
        )
        if index is not None:
            truncated_non_system = truncated_non_system[index:]

        result = self._ensure_user_message(system_messages, truncated_non_system, messages)
        return self.fix_messages(result)


class TruncateByTurnsCompressor:
    def __init__(self, truncate_turns: int = 1, compression_threshold: float = 0.70) -> None:
        self.truncate_turns = truncate_turns
        self.compression_threshold = compression_threshold
        self._truncator = ContextTruncator()

    def should_compress(self, messages: list[dict], current_tokens: int, max_tokens: int) -> bool:
        if max_tokens <= 0 or current_tokens <= 0:
            return False
        usage_rate = current_tokens / max_tokens
        return usage_rate > self.compression_threshold

    async def compress(self, messages: list[dict]) -> list[dict]:
        return self._truncator.truncate_by_dropping_oldest_turns(
            messages,
            drop_turns=self.truncate_turns,
        )


def split_history(
    messages: list[dict], keep_recent: int
) -> tuple[list[dict], list[dict], list[dict]]:
    first_non_system = 0
    for i, msg in enumerate(messages):
        if msg.get("role") != "system":
            first_non_system = i
            break

    system_messages = messages[:first_non_system]
    non_system_messages = messages[first_non_system:]

    if len(non_system_messages) <= keep_recent:
        return system_messages, [], non_system_messages

    split_index = len(non_system_messages) - keep_recent

    while split_index > 0 and non_system_messages[split_index].get("role") != "user":
        split_index -= 1

    if split_index == 0:
        return system_messages, [], non_system_messages

    messages_to_summarize = non_system_messages[:split_index]
    recent_messages = non_system_messages[split_index:]

    return system_messages, messages_to_summarize, recent_messages


# ──────────────────────────────────────────────────────────────
# 结构化摘要 Prompt
# ──────────────────────────────────────────────────────────────

_STRUCTURED_SUMMARY_PROMPT = """请对以下对话历史生成结构化摘要，包含以下维度：

## 目标 (Goals)
用户的主要目标和意图

## 关键事实 (Key Facts)
对话中提到的重要事实和信息

## 决策 (Decisions)
已做出的决定或结论

## 进展 (Progress)
已完成的工作或讨论

## 待办 (Open Items)
未完成的事项或待解决的问题

对话历史：
{messages}

{existing_summary}

请保持摘要简洁，不超过 {max_length} 字符。"""


class LLMSummaryCompressor:
    """增强型 LLM 摘要压缩器。

    新增能力：
    - 预算分配：根据上下文窗口大小动态计算各部分 token 预算
    - 增量水位线：仅对新增消息生成摘要，避免重复处理
    - 防漂移机制：当原始消息可在预算内重建时，从原始消息重新生成摘要
    - 结构化摘要格式：按目标/事实/决策/进展/待办五维度输出
    """

    def __init__(
        self,
        keep_recent: int = 4,
        instruction_text: str | None = None,
        compression_threshold: float = 0.70,
        summary_provider: str | None = None,
        summary_model: str | None = None,
        max_tokens: int = 512,
        context_window: int = 0,
    ) -> None:
        self.keep_recent = keep_recent
        self.compression_threshold = compression_threshold
        self.summary_provider = summary_provider
        self.summary_model = summary_model
        self.max_tokens = max_tokens
        self.context_window = context_window

        self.token_counter = TokenCounter()

        # 增量水位线：已摘要到的最后一条消息 ID
        self._summary_up_to_msg_id: str | None = None
        # 缓存的最近一次摘要结果（用于增量合并）
        self._cached_summary: str | None = None

        # 保留自定义 instruction_text 的向后兼容
        self._custom_instruction = instruction_text

    # ── 预算分配 ──────────────────────────────────────────────

    def _calculate_budgets(self, context_window: int) -> dict:
        """计算各部分 token 预算。"""
        from app.core.config import get_settings
        settings = get_settings()

        history_budget = int(context_window * settings.LLM_CONTEXT_BUDGET_RATIO)
        summary_budget = int(history_budget * settings.LLM_SUMMARY_TARGET_RATIO)
        recent_budget = history_budget - summary_budget
        return {
            "history_total": history_budget,
            "summary": summary_budget,
            "recent": recent_budget,
            "rebuild_source": int(history_budget * 0.6),  # 防漂移重建预算
        }

    # ── 增量水位线 ────────────────────────────────────────────

    def _get_msg_id(self, msg: dict) -> str:
        """获取消息的唯一标识，用于水位线追踪。"""
        # 优先使用消息自带的 id，否则用 role + content hash
        if "id" in msg:
            return str(msg["id"])
        import hashlib
        content = msg.get("content", "")
        if isinstance(content, list):
            import json
            content = json.dumps(content, ensure_ascii=False)
        raw = f"{msg.get('role', '')}:{content}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    def _get_incremental_messages(
        self, messages: list[dict]
    ) -> tuple[list[dict], list[dict]]:
        """分离已摘要消息和新增消息。

        Returns:
            (已摘要部分, 新增部分)
        """
        if not self._summary_up_to_msg_id:
            return [], messages

        # 找到水位线位置
        watermark_idx = -1
        for i, msg in enumerate(messages):
            if self._get_msg_id(msg) == self._summary_up_to_msg_id:
                watermark_idx = i
                break

        if watermark_idx < 0:
            # 水位线消息未找到（可能被截断），全量重做
            return [], messages

        already_summarized = messages[: watermark_idx + 1]
        new_messages = messages[watermark_idx + 1:]
        return already_summarized, new_messages

    def _update_watermark(self, messages: list[dict]) -> None:
        """将水位线推进到当前消息列表末尾。"""
        if messages:
            self._summary_up_to_msg_id = self._get_msg_id(messages[-1])

    # ── 摘要生成 ──────────────────────────────────────────────

    def _build_summary_prompt(
        self,
        messages_text: str,
        existing_summary: str | None = None,
        max_length: int = 2000,
    ) -> str:
        """构建结构化摘要 prompt。"""
        if self._custom_instruction:
            # 向后兼容：使用自定义 instruction
            prompt = self._custom_instruction
            if existing_summary:
                prompt += f"\n\n已有摘要（请在此基础上更新）：\n{existing_summary}"
            return prompt

        existing_section = ""
        if existing_summary:
            existing_section = f"已有摘要（请在此基础上更新，保留仍然准确的信息，替换过时的部分）：\n{existing_summary}"

        return _STRUCTURED_SUMMARY_PROMPT.format(
            messages=messages_text,
            existing_summary=existing_section,
            max_length=max_length,
        )

    async def _call_llm_for_summary(self, llm_payload: list[dict], max_tokens: int) -> str:
        """调用 LLM 获取摘要文本。"""
        from app.runtime.provider.llm.adapter import llm_adapter

        chat_kwargs: dict = {
            "messages": llm_payload,
            "temperature": 0.3,
            "max_tokens": max_tokens,
            "route_hint": RouteHint.CHAT,
        }
        if self.summary_provider:
            chat_kwargs["provider_name"] = self.summary_provider
        else:
            chat_kwargs["provider_name"] = llm_adapter.default_provider
        if self.summary_model:
            chat_kwargs["model"] = self.summary_model

        raw = await llm_adapter.chat(**chat_kwargs)
        return raw.get("content", "") if isinstance(raw, dict) else str(raw)

    async def _summarize(self, messages: list[dict], existing_summary: str | None = None) -> str:
        """对消息列表生成摘要。"""
        from app.core.config import get_settings
        settings = get_settings()

        # 将消息序列化为文本
        messages_text_parts = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if isinstance(content, list):
                # 提取文本部分
                text_parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
                content = " ".join(text_parts)
            messages_text_parts.append(f"[{role}]: {content}")
        messages_text = "\n".join(messages_text_parts)

        max_length = settings.LLM_SUMMARY_MAX_LENGTH
        prompt = self._build_summary_prompt(messages_text, existing_summary, max_length)

        instruction_message = {"role": "user", "content": prompt}
        llm_payload = [instruction_message]

        return await self._call_llm_for_summary(llm_payload, self.max_tokens)

    async def _summarize_with_anti_drift(
        self,
        messages_to_summarize: list[dict],
        new_messages: list[dict],
        existing_summary: str | None,
        budgets: dict,
    ) -> str:
        """防漂移摘要。

        当原始前缀消息仍可重建时（token 数 < rebuild_source 预算），
        从原始消息重新生成摘要，避免"摘要的摘要"导致信息丢失。
        否则仅对新增消息摘要，然后与旧摘要合并。
        """
        from app.core.config import get_settings
        settings = get_settings()

        if not settings.LLM_ANTI_DRIFT_ENABLED:
            # 防漂移关闭，直接全量摘要
            all_msgs = messages_to_summarize + new_messages if messages_to_summarize else new_messages
            return await self._summarize(all_msgs, existing_summary)

        # 检查原始消息是否可在重建预算内容纳
        original_tokens = self.token_counter.count_messages(messages_to_summarize) if messages_to_summarize else 0

        if original_tokens <= budgets["rebuild_source"] or not messages_to_summarize:
            # 从原始消息重新摘要（含新增消息）
            all_msgs = messages_to_summarize + new_messages if messages_to_summarize else new_messages
            logger.debug(
                f"[Compressor] Anti-drift: rebuilding from original "
                f"(tokens={original_tokens}, budget={budgets['rebuild_source']})"
            )
            return await self._summarize(all_msgs, existing_summary)
        else:
            # 原始消息过多，仅对新增消息摘要，然后与旧摘要合并
            logger.debug(
                f"[Compressor] Anti-drift: incremental summarize only "
                f"(original_tokens={original_tokens} > budget={budgets['rebuild_source']})"
            )
            if new_messages:
                new_summary = await self._summarize(new_messages)
                if existing_summary:
                    # 合并旧摘要和新摘要
                    merged = await self._summarize(
                        [],
                        existing_summary=f"{existing_summary}\n\n新增内容摘要：\n{new_summary}",
                    )
                    return merged
                return new_summary
            return existing_summary or ""

    # ── 压缩入口 ──────────────────────────────────────────────

    def should_compress(self, messages: list[dict], current_tokens: int, max_tokens: int) -> bool:
        if max_tokens <= 0 or current_tokens <= 0:
            return False
        usage_rate = current_tokens / max_tokens
        return usage_rate > self.compression_threshold

    async def compress(
        self,
        messages: list[dict],
        force_rebuild: bool = False,
    ) -> list[dict]:
        """压缩消息列表。

        Args:
            messages: 完整消息列表
            force_rebuild: 强制重建完整摘要（忽略增量水位线）
        """
        if len(messages) <= self.keep_recent + 1:
            return messages

        system_messages, messages_to_summarize, recent_messages = split_history(
            messages, self.keep_recent
        )

        if not messages_to_summarize:
            return messages

        # 计算预算
        ctx_window = self.context_window or 128000
        budgets = self._calculate_budgets(ctx_window)

        # 增量水位线分离
        if force_rebuild:
            already_summarized = []
            new_messages = messages_to_summarize
            self._summary_up_to_msg_id = None
            self._cached_summary = None
        else:
            already_summarized, new_messages = self._get_incremental_messages(messages_to_summarize)

        existing_summary = self._cached_summary

        try:
            if not new_messages and existing_summary:
                # 没有新消息，复用旧摘要
                logger.debug("[Compressor] No new messages, reusing cached summary")
                summary_content = existing_summary
            elif already_summarized or existing_summary:
                # 增量模式：防漂移摘要
                summary_content = await self._summarize_with_anti_drift(
                    already_summarized, new_messages, existing_summary, budgets,
                )
            else:
                # 全量模式：首次摘要
                summary_content = await self._summarize(messages_to_summarize)

        except Exception as e:
            logger.error(f"[Compressor] LLM summary failed: {e}")
            # 降级策略：保留旧摘要，下一轮重试
            if existing_summary:
                logger.info("[Compressor] Falling back to cached summary")
                summary_content = existing_summary
            else:
                return messages

        # 更新水位线和缓存
        self._update_watermark(messages_to_summarize)
        self._cached_summary = summary_content

        result = []
        result.extend(system_messages)

        result.append({
            "role": "user",
            "content": f"[对话历史摘要] {summary_content}",
        })
        result.append({
            "role": "assistant",
            "content": "好的，我已了解之前的对话内容。",
        })

        result.extend(recent_messages)

        return result


class ContextManager:
    def __init__(
        self,
        max_context_tokens: int = 0,
        enforce_max_turns: int = -1,
        truncate_turns: int = 1,
        compression_threshold: float = 0.70,
        llm_compress: bool = False,
        llm_compress_keep_recent: int = 4,
        llm_compress_instruction: str | None = None,
        summary_provider: str | None = None,
        summary_model: str | None = None,
        summary_max_tokens: int = 512,
        context_window: int = 0,
    ) -> None:
        self.max_context_tokens = max_context_tokens
        self.enforce_max_turns = enforce_max_turns
        self.truncate_turns = truncate_turns

        self.token_counter = TokenCounter()
        self.truncator = ContextTruncator()

        if llm_compress:
            self.compressor = LLMSummaryCompressor(
                keep_recent=llm_compress_keep_recent,
                instruction_text=llm_compress_instruction,
                compression_threshold=compression_threshold,
                summary_provider=summary_provider,
                summary_model=summary_model,
                max_tokens=summary_max_tokens,
                context_window=context_window,
            )
        else:
            self.compressor = TruncateByTurnsCompressor(
                truncate_turns=truncate_turns,
                compression_threshold=compression_threshold,
            )

    async def process(
        self, messages: list[dict], trusted_token_usage: int = 0, chat_mode: str = "normal",
        force_compression: bool = False,
    ) -> dict:
        """处理上下文：截断 + 压缩。

        Args:
            force_compression: 强制触发压缩，忽略 should_compress 阈值判断。
                用于手动压缩端点，避免修改共享的 compressor.compression_threshold。

        Returns:
            dict: {"messages": list[dict], "context_tokens": int}
        """
        try:
            result = messages

            if self.enforce_max_turns != -1:
                system_msgs, non_system_msgs = self.truncator._split_system_rest(result)
                if len(non_system_msgs) // 2 > self.enforce_max_turns:
                    result = self.truncator.truncate_by_dropping_oldest_turns(
                        result,
                        drop_turns=len(non_system_msgs) // 2 - self.enforce_max_turns,
                    )

            if self.max_context_tokens > 0:
                total_tokens = self.token_counter.count_tokens(result, trusted_token_usage)

                if force_compression or self.compressor.should_compress(result, total_tokens, self.max_context_tokens):
                    result = await self._run_compression(result, total_tokens, force_compression)

            context_tokens = self.token_counter.count_tokens(result)
            logger.debug(
                f"[Compressor] process done: chat_mode={chat_mode}, "
                f"messages={len(result)}, context_tokens={context_tokens}, "
                f"forced={force_compression}"
            )
            return {"messages": result, "context_tokens": context_tokens}
        except Exception as e:
            logger.error(f"[Compressor] Context processing error: {e}", exc_info=True)
            context_tokens = self.token_counter.count_tokens(messages)
            return {"messages": messages, "context_tokens": context_tokens}

    async def _run_compression(
        self, messages: list[dict], prev_tokens: int, force_rebuild: bool = False,
    ) -> list[dict]:
        logger.info(f"[Compressor] Compression triggered: {prev_tokens} tokens")

        if isinstance(self.compressor, LLMSummaryCompressor):
            messages = await self.compressor.compress(messages, force_rebuild=force_rebuild)
        else:
            messages = await self.compressor.compress(messages)

        tokens_after = self.token_counter.count_tokens(messages)
        compress_rate = (tokens_after / self.max_context_tokens) * 100 if self.max_context_tokens > 0 else 0
        logger.info(
            f"[Compressor] Compression done: {prev_tokens} -> {tokens_after} tokens, "
            f"rate={compress_rate:.1f}%"
        )

        if self.compressor.should_compress(messages, tokens_after, self.max_context_tokens):
            logger.info("[Compressor] Still over limit, applying halving truncation...")
            messages = self.truncator.truncate_by_halving(messages)

        return messages


_context_managers: dict[str, ContextManager] = {}
_cache_lock = threading.Lock()


def invalidate_context_cache(provider: str | None = None, model: str | None = None) -> None:
    """失效上下文管理器缓存。

    - provider=None 且 model=None: 清空所有缓存
    - 仅 provider: 清空该 provider 下所有模型的缓存
    - provider + model: 清空特定 provider/model 的缓存
    """
    with _cache_lock:
        if provider is None and model is None:
            count = len(_context_managers)
            _context_managers.clear()
            logger.info(f"[Compressor] Context cache fully invalidated ({count} entries cleared)")
            return

        prefix = f"{provider}:" if provider else ""
        keys_to_remove = [
            k for k in _context_managers
            if k.startswith(prefix) and (not model or f":{model}:" in k)
        ]
        for k in keys_to_remove:
            del _context_managers[k]
        if keys_to_remove:
            logger.info(
                f"[Compressor] Context cache invalidated: {len(keys_to_remove)} entries "
                f"(provider={provider}, model={model})"
            )


def get_context_manager(
    provider_name: str | None = None,
    model: str = "",
    threshold_override: float | None = None,
    force_refresh: bool = False,
) -> ContextManager:
    from app.core.config import settings
    from app.runtime.provider.llm.adapter import llm_adapter

    # 从 settings 读取配置
    llm_compress = settings.LLM_COMPRESS_ENABLED
    compression_threshold = threshold_override if threshold_override is not None else settings.LLM_COMPRESSION_THRESHOLD
    context_window = settings.LLM_CONTEXT_WINDOW_SIZE
    strategy = settings.LLM_CONTEXT_STRATEGY

    # 当策略为 summarize 时，强制启用 LLM 压缩
    if strategy == "summarize":
        llm_compress = True

    # 复合缓存 key（包含 threshold、llm_compress 和 strategy）
    key = f"{provider_name}:{model}:t{compression_threshold}:c{int(llm_compress)}:s{strategy}"

    with _cache_lock:
        if not force_refresh and key in _context_managers:
            return _context_managers[key]

        # force_refresh 时移除旧缓存
        if force_refresh and key in _context_managers:
            del _context_managers[key]

    # context_window 未配置时从 provider 能力表获取
    token_counter = TokenCounter()
    if context_window <= 0:
        resolved_provider = provider_name or getattr(llm_adapter, "default_provider", "")
        context_window = token_counter.get_context_window_for_model(resolved_provider, model)

    if context_window <= 0:
        context_window = 128000

    # 注意：max_context_tokens 传入完整的上下文窗口容量，不预乘 compression_threshold。
    # should_compress 内部会用 current_tokens / max_tokens > threshold 判断，
    # 若此处预先乘以 threshold，会导致实际触发阈值变为 threshold²（如 0.70²=0.49）。
    max_context_tokens = int(context_window)

    manager = ContextManager(
        max_context_tokens=max_context_tokens,
        enforce_max_turns=-1,
        truncate_turns=1,
        compression_threshold=compression_threshold,
        llm_compress=llm_compress,
        llm_compress_keep_recent=4,
        summary_provider=settings.LLM_SUMMARY_PROVIDER or None,
        summary_model=settings.LLM_SUMMARY_MODEL or None,
        summary_max_tokens=settings.LLM_SUMMARY_MAX_TOKENS,
        context_window=context_window,
    )

    with _cache_lock:
        _context_managers[key] = manager
    logger.info(
        f"[Compressor] Created ContextManager for {key}: "
        f"max_tokens={max_context_tokens}, llm_compress={llm_compress}, "
        f"threshold={compression_threshold}, context_window={context_window}, "
        f"strategy={strategy}, force_refresh={force_refresh}"
    )

    return manager
