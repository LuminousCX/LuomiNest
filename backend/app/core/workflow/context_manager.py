"""工作流上下文管理器

借鉴 claude-code 的多层压缩策略，为工作流引擎提供上下文管理：
1. 记忆注入：规划阶段自动将记忆中枢内容注入 system prompt
2. 三层压缩：
   - Layer 1 工具结果压缩：截断长工具输出，保留首尾关键信息
   - Layer 2 LLM 历史摘要：多轮迭代时对旧轮次生成 LLM 摘要
   - Layer 3 紧急截断：兜底按轮次丢弃最旧消息

参考：
- claude-code: microCompact（工具结果清理）+ autoCompact（LLM 摘要）+ reactiveCompact（截断）
- LuomiNest: app/core/context/__init__.py 的 ContextTruncator 和 LLMSummaryCompressor
"""
import json
from typing import Any

from loguru import logger

from app.core.context import ContextTruncator, TokenCounter

# ===== 阈值常量 =====
# Layer 1: 工具结果压缩阈值
TOOL_RESULT_MAX_CHARS = 2000  # 超过此长度的工具结果将被压缩
TOOL_RESULT_KEEP_HEAD = 800  # 保留头部字符数
TOOL_RESULT_KEEP_TAIL = 400  # 保留尾部字符数

# Layer 2: LLM 历史摘要阈值
HISTORY_SUMMARY_THRESHOLD_MESSAGES = 20  # 消息数超过此值触发摘要
HISTORY_SUMMARY_KEEP_RECENT = 6  # 保留最近 N 条消息不摘要
HISTORY_SUMMARY_MAX_TOKENS = 1024  # 摘要最大 token 数

# Layer 3: 紧急截断阈值
EMERGENCY_TRUNCATE_KEEP_TURNS = 3  # 保留最近 N 轮对话

# 记忆注入预算
MEMORY_INJECTION_MAX_CHARS = 3000  # 注入 system prompt 的记忆上下文最大字符数


class WorkflowContextManager:
    """工作流上下文管理器

    管理工作流执行过程中的上下文，提供三层压缩和记忆注入能力。
    所有方法均为静态或实例方法，不持有状态，可安全并发调用。
    """

    def __init__(self) -> None:
        self._token_counter = TokenCounter()
        self._truncator = ContextTruncator()

    # ===== 记忆注入 =====

    def inject_memory_context(
        self,
        system_prompt: str,
        query: str = "",
        conversation_id: str | None = None,
    ) -> str:
        """将记忆中枢内容注入 system prompt

        在工作流规划阶段自动调用，LLM 无需主动调用 memory.build_context 工具
        即可获取用户画像、事实、知识等记忆上下文。

        Args:
            system_prompt: 原始 system prompt
            query: 用户任务（用于 query-aware 检索）
            conversation_id: 对话 ID（用于对话级记忆隔离）

        Returns:
            拼接了记忆上下文的 system prompt
        """
        try:
            from app.engines.memory import get_memory_engine

            engine = get_memory_engine()
            if engine is None:
                logger.debug("[WorkflowCtx] Memory engine not initialized, skip injection")
                return system_prompt

            memory_ctx = engine.build_context(
                max_chars=MEMORY_INJECTION_MAX_CHARS,
                query=query,
                conversation_id=conversation_id,
            )

            if not memory_ctx or not memory_ctx.strip():
                logger.debug("[WorkflowCtx] Memory context is empty, skip injection")
                return system_prompt

            memory_block = f"\n\n<user_memory>\n{memory_ctx}\n</user_memory>"
            logger.debug(
                f"[WorkflowCtx] Injected memory context: {len(memory_ctx)} chars, "
                f"query={'yes' if query else 'no'}, conv={conversation_id or 'none'}"
            )
            return system_prompt + memory_block
        except Exception as e:
            logger.warning(f"[WorkflowCtx] Memory injection failed: {e}")
            return system_prompt

    # ===== Layer 1: 工具结果压缩 =====

    def compact_tool_result(self, result: str | None) -> str | None:
        """压缩工具执行结果（Layer 1）

        当工具结果超过 TOOL_RESULT_MAX_CHARS 时，保留首尾关键信息，
        中间用占位符替代。这是同步操作，不调用 LLM。

        借鉴 claude-code microCompact：清理旧 tool_result 内容，
        但这里是对单个结果做长度压缩，而非跨消息清理。

        Args:
            result: 工具执行结果文本

        Returns:
            压缩后的结果文本（若未超长则原样返回）
        """
        if not result:
            return result

        result_len = len(result)
        if result_len <= TOOL_RESULT_MAX_CHARS:
            return result

        head = result[:TOOL_RESULT_KEEP_HEAD]
        tail = result[-TOOL_RESULT_KEEP_TAIL:]
        skipped = result_len - TOOL_RESULT_KEEP_HEAD - TOOL_RESULT_KEEP_TAIL

        compacted = f"{head}\n\n[...已压缩 {skipped} 字符...]\n\n{tail}"
        logger.debug(
            f"[WorkflowCtx] Layer 1 compacted tool result: "
            f"{result_len} -> {len(compacted)} chars"
        )
        return compacted

    def compact_task_results(self, tasks: list[Any]) -> None:
        """批量压缩多个任务的执行结果

        在工作流执行完成后、生成最终摘要前调用，
        确保长工具结果不会导致最终摘要上下文膨胀。

        Args:
            tasks: WorkflowTask 列表（原地修改 task.result）
        """
        for task in tasks:
            if task.result and len(task.result) > TOOL_RESULT_MAX_CHARS:
                task.result = self.compact_tool_result(task.result)

    # ===== Layer 2: LLM 历史摘要 =====

    async def summarize_history(
        self,
        messages: list[dict[str, Any]],
        provider: str | None = None,
        model: str | None = None,
    ) -> list[dict[str, Any]]:
        """LLM 历史摘要压缩（Layer 2）

        当消息数超过 HISTORY_SUMMARY_THRESHOLD_MESSAGES 时，
        对旧消息调用 LLM 生成摘要，保留最近 HISTORY_SUMMARY_KEEP_RECENT 条。

        借鉴 claude-code autoCompact 的 9 段式摘要（简化为关键 4 段）：
        1. 用户原始请求和意图
        2. 已执行的工具调用和关键结果
        3. 当前工作流进度
        4. 待处理的任务

        Args:
            messages: 完整消息列表
            provider: LLM provider
            model: LLM model

        Returns:
            压缩后的消息列表（system + 摘要 + 最近消息）
        """
        if len(messages) <= HISTORY_SUMMARY_THRESHOLD_MESSAGES:
            return messages

        from app.core.context import split_history

        system_messages, to_summarize, recent = split_history(
            messages, HISTORY_SUMMARY_KEEP_RECENT
        )

        if not to_summarize:
            return messages

        summary_prompt = self._build_summary_prompt(to_summarize)

        try:
            from app.runtime.provider.llm.adapter import llm_adapter

            actual_provider = provider or llm_adapter.default_provider
            if model is None:
                provider_obj = llm_adapter.get_provider(actual_provider)
                model = provider_obj.default_model if provider_obj else ""

            result = await llm_adapter.chat(
                messages=summary_prompt,
                provider_name=actual_provider,
                model=model,
                temperature=0.3,
                max_tokens=HISTORY_SUMMARY_MAX_TOKENS,
            )

            summary_content = ""
            if isinstance(result, dict):
                summary_content = result.get("content", "") or ""
            elif isinstance(result, str):
                summary_content = result

            if not summary_content.strip():
                logger.warning("[WorkflowCtx] Layer 2 summary is empty, skip compression")
                return messages

            logger.info(
                f"[WorkflowCtx] Layer 2 summarized {len(to_summarize)} messages "
                f"into {len(summary_content)} chars"
            )

            return [
                *system_messages,
                {"role": "user", "content": f"[工作流历史摘要]\n{summary_content}"},
                {"role": "assistant", "content": "好的，我已了解之前的工作流执行情况。"},
                *recent,
            ]
        except Exception as e:
            logger.error(f"[WorkflowCtx] Layer 2 LLM summary failed: {e}", exc_info=True)
            return messages

    def _build_summary_prompt(
        self, messages_to_summarize: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """构建 LLM 摘要请求的消息列表

        借鉴 claude-code 的摘要模板，简化为 4 段关键信息。
        """
        history_text = self._messages_to_text(messages_to_summarize)

        instruction = f"""请基于以下工作流执行历史，生成简洁的摘要。

执行历史:
{history_text}

请按以下结构输出摘要（中文）：
1. **用户请求**：用户的原始任务和意图
2. **已执行操作**：已调用的工具及其关键结果（每个工具一行）
3. **当前进度**：工作流执行到哪个阶段，哪些任务已完成
4. **待处理事项**：尚未执行的任务或需要后续处理的项

要求：
- 保持简洁，只保留关键信息
- 保留工具名称和关键参数
- 保留失败任务的原因
- 不要包含完整的工具输出，只保留摘要"""

        return [{"role": "user", "content": instruction}]

    def _messages_to_text(self, messages: list[dict[str, Any]]) -> str:
        """将消息列表转换为可读文本"""
        lines: list[str] = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if isinstance(content, list):
                content = " ".join(
                    part.get("text", "") for part in content
                    if isinstance(part, dict) and part.get("type") == "text"
                )
            content_str = str(content)[:500]
            lines.append(f"[{role}] {content_str}")
        return "\n".join(lines)

    # ===== Layer 3: 紧急截断 =====

    def truncate_messages(
        self,
        messages: list[dict[str, Any]],
        keep_turns: int = EMERGENCY_TRUNCATE_KEEP_TURNS,
    ) -> list[dict[str, Any]]:
        """紧急截断（Layer 3）

        兜底策略：当 Layer 1 和 Layer 2 仍无法将上下文降到阈值以下时，
        按轮次丢弃最旧的消息。

        复用 app.core.context.ContextTruncator 的截断逻辑。

        Args:
            messages: 完整消息列表
            keep_turns: 保留最近 N 轮（user+assistant 算一轮）

        Returns:
            截断后的消息列表
        """
        if len(messages) <= 2:
            return messages

        result = self._truncator.truncate_by_dropping_oldest_turns(
            messages,
            drop_turns=max(1, len(messages) // 2 - keep_turns),
        )

        logger.info(
            f"[WorkflowCtx] Layer 3 truncated: {len(messages)} -> {len(result)} messages"
        )
        return result

    # ===== 综合上下文处理 =====

    async def process_context(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int = 0,
        provider: str | None = None,
        model: str | None = None,
    ) -> list[dict[str, Any]]:
        """综合应用三层压缩策略

        按由轻到重的顺序应用：
        1. 若 token 超限，先尝试 Layer 2 LLM 摘要
        2. 若仍超限，应用 Layer 3 紧急截断

        Layer 1（工具结果压缩）在任务执行时单独调用 compact_tool_result。

        Args:
            messages: 消息列表
            max_tokens: 最大 token 阈值（0 表示不检查）
            provider: LLM provider
            model: LLM model

        Returns:
            处理后的消息列表
        """
        if max_tokens <= 0:
            return messages

        result = messages
        current_tokens = self._token_counter.count_tokens(result)

        if current_tokens <= max_tokens:
            return result

        logger.info(
            f"[WorkflowCtx] Context over limit: {current_tokens}/{max_tokens} tokens, "
            f"applying Layer 2 summary..."
        )

        # Layer 2: LLM 摘要
        result = await self.summarize_history(result, provider, model)
        current_tokens = self._token_counter.count_tokens(result)

        if current_tokens <= max_tokens:
            logger.info(f"[WorkflowCtx] Layer 2 sufficient: {current_tokens} tokens")
            return result

        # Layer 3: 紧急截断
        logger.info(f"[WorkflowCtx] Layer 2 insufficient: {current_tokens} tokens, applying Layer 3...")
        result = self.truncate_messages(result)
        current_tokens = self._token_counter.count_tokens(result)

        logger.info(f"[WorkflowCtx] After Layer 3: {current_tokens} tokens")
        return result


# 全局单例
workflow_context_manager = WorkflowContextManager()
