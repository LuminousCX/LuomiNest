"""ContextManager 与上下文管理器缓存（从原 __init__.py 拆出）。"""

import threading

from loguru import logger

from app.core.context.compressors import LLMSummaryCompressor, TruncateByTurnsCompressor
from app.core.context.constants import FALLBACK_CONTEXT_WINDOW
from app.core.context.token_counter import TokenCounter
from app.core.context.truncator import ContextTruncator


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
        context_window = FALLBACK_CONTEXT_WINDOW

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
