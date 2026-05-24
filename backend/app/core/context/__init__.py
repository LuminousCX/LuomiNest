from loguru import logger


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

    def _estimate_tokens(self, text: str) -> int:
        chinese_count = len([c for c in text if "\u4e00" <= c <= "\u9fff"])
        other_count = len(text) - chinese_count
        return int(chinese_count * 0.6 + other_count * 0.3)


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
    def __init__(self, truncate_turns: int = 1, compression_threshold: float = 0.82) -> None:
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


class LLMSummaryCompressor:
    def __init__(
        self,
        keep_recent: int = 4,
        instruction_text: str | None = None,
        compression_threshold: float = 0.82,
    ) -> None:
        self.keep_recent = keep_recent
        self.compression_threshold = compression_threshold

        self.instruction_text = instruction_text or (
            "Based on our full conversation history, produce a concise summary of key takeaways and/or project progress.\n"
            "1. Systematically cover all core topics discussed and the final conclusion/outcome for each; clearly highlight the latest primary focus.\n"
            "2. If any tools were used, summarize tool usage (total call count) and extract the most valuable insights from tool outputs.\n"
            "3. If there was an initial user goal, state it first and describe the current progress/status.\n"
            "4. Write the summary in the user's language.\n"
        )

    def should_compress(self, messages: list[dict], current_tokens: int, max_tokens: int) -> bool:
        if max_tokens <= 0 or current_tokens <= 0:
            return False
        usage_rate = current_tokens / max_tokens
        return usage_rate > self.compression_threshold

    async def compress(self, messages: list[dict]) -> list[dict]:
        if len(messages) <= self.keep_recent + 1:
            return messages

        system_messages, messages_to_summarize, recent_messages = split_history(
            messages, self.keep_recent
        )

        if not messages_to_summarize:
            return messages

        instruction_message = {"role": "user", "content": self.instruction_text}
        llm_payload = messages_to_summarize + [instruction_message]

        try:
            from app.runtime.provider.llm.adapter import llm_adapter
            raw = await llm_adapter.chat(
                messages=llm_payload,
                provider_name=llm_adapter.default_provider,
                temperature=0.3,
                max_tokens=1024,
            )
            summary_content = raw.get("content", "") if isinstance(raw, dict) else str(raw)
        except Exception as e:
            logger.error(f"[Compressor] LLM summary failed: {e}")
            return messages

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
        compression_threshold: float = 0.82,
        llm_compress: bool = False,
        llm_compress_keep_recent: int = 4,
        llm_compress_instruction: str | None = None,
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
            )
        else:
            self.compressor = TruncateByTurnsCompressor(
                truncate_turns=truncate_turns,
                compression_threshold=compression_threshold,
            )

    async def process(self, messages: list[dict], trusted_token_usage: int = 0) -> list[dict]:
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

                if self.compressor.should_compress(result, total_tokens, self.max_context_tokens):
                    result = await self._run_compression(result, total_tokens)

            return result
        except Exception as e:
            logger.error(f"[Compressor] Context processing error: {e}", exc_info=True)
            return messages

    async def _run_compression(self, messages: list[dict], prev_tokens: int) -> list[dict]:
        logger.info(f"[Compressor] Compression triggered: {prev_tokens} tokens")

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


def get_context_manager(provider_name: str | None = None, model: str = "") -> ContextManager:
    from app.runtime.provider.llm.adapter import llm_adapter

    key = f"{provider_name}:{model}"

    if key in _context_managers:
        return _context_managers[key]

    context_window = 0
    try:
        provider = llm_adapter.get_provider(provider_name)
        context_window = getattr(provider, "context_window", 0) or 0
    except Exception:
        pass

    if context_window <= 0:
        context_window = 128000

    max_context_tokens = int(context_window * 0.82)

    manager = ContextManager(
        max_context_tokens=max_context_tokens,
        enforce_max_turns=-1,
        truncate_turns=1,
        compression_threshold=0.82,
        llm_compress=False,
        llm_compress_keep_recent=4,
    )

    _context_managers[key] = manager
    logger.info(f"[Compressor] Created ContextManager for {key}: max_tokens={max_context_tokens}")

    return manager
