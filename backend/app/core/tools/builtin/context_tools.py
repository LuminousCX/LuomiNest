"""上下文治理工具 — 供 LLM 自主触发的上下文压缩。

对齐 tool-system-optimization.md §4.3 T4：
- 工具名 compress_context，tier=core，scope=shared
- 执行逻辑复用 ChatService.compress_conversation()
- 返回压缩摘要与压缩前后 token 数

设计原则：
- 依赖通过 container 懒获取，避免 import 时循环依赖
- 压缩前由 ChatService 内部保留摘要（现有逻辑），不额外备份
- 触发策略：LLM 检测上下文过长时自主调用，不强制自动压缩
"""
from __future__ import annotations

from typing import Any

from loguru import logger

from app.core.tools.registry import ToolBase, ToolResult


class CompressContextTool(ToolBase):
    """上下文压缩工具 — LLM 检测对话上下文过长时自主调用。

    将当前对话的历史消息进行智能压缩，保留关键摘要，释放 token 空间。
    压缩前后 token 数作为元数据返回，供 LLM 判断压缩效果。
    """

    @property
    def name(self) -> str:
        return "compress_context"

    @property
    def tier(self) -> str:
        return "core"

    @property
    def description(self) -> str:
        return (
            "压缩当前对话的上下文，释放 token 空间。"
            "当对话历史过长、上下文接近模型限制时使用。"
            "压缩会保留关键摘要，去除冗余细节。"
            "返回压缩前后的 token 数对比。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "conversation_id": {
                    "type": "string",
                    "description": "要压缩的对话 ID",
                },
                "max_tokens": {
                    "type": "integer",
                    "description": "压缩后目标 token 上限（可选，默认按系统阈值自动计算）",
                },
            },
            "required": ["conversation_id"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        conv_id = arguments.get("conversation_id", "").strip()
        if not conv_id:
            return ToolResult.fail("缺少 conversation_id 参数")

        # 懒导入避免循环依赖
        try:
            from app.core.container import container
        except ImportError as e:
            logger.error(f"[CompressContext] 导入 container 失败: {e}")
            return ToolResult.fail(f"服务容器不可用: {e}")

        # 获取依赖
        chat_service = container.chat_service
        conversation_store = container.conversation_store
        adapter = container.llm_adapter

        # 加载对话
        try:
            conv = await conversation_store.get_async(conv_id)
        except Exception as e:
            logger.error(f"[CompressContext] 加载对话失败: conv_id={conv_id}, error={e}")
            return ToolResult.fail(f"加载对话失败: {e}")

        if not conv:
            return ToolResult.fail(f"对话不存在: {conv_id}")

        # 调用压缩服务
        try:
            result = await chat_service.compress_conversation(conv_id, conv, adapter)
        except Exception as e:
            logger.error(
                f"[CompressContext] 压缩失败: conv_id={conv_id}, error={e}",
                exc_info=True,
            )
            return ToolResult.fail(f"上下文压缩失败: {e}")

        tokens_before = result.get("tokens_before", 0)
        tokens_after = result.get("tokens_after", 0)
        saved = tokens_before - tokens_after
        ratio = (saved / tokens_before * 100) if tokens_before > 0 else 0

        logger.info(
            f"[CompressContext] 压缩完成: conv_id={conv_id}, "
            f"{tokens_before} → {tokens_after} tokens (节省 {ratio:.1f}%)"
        )

        return ToolResult.ok(
            f"上下文压缩完成：{tokens_before} → {tokens_after} tokens，"
            f"节省 {saved} tokens（{ratio:.1f}%）",
            metadata={
                "conversation_id": conv_id,
                "tokens_before": tokens_before,
                "tokens_after": tokens_after,
                "tokens_saved": saved,
            },
        )
