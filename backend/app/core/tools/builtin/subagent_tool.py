"""LuomiNest 子 Agent 委派工具。

主 Agent 通过本工具将子任务委派给子 Agent 执行。

核心行为：
1. 接收 task（任务描述）与 context（附加上下文）
2. 经 subagent_delegation 端口委派子 Agent 执行
3. 子 Agent 拥有独立上下文，不继承父对话历史
4. 子 Agent 不读写主 Agent 记忆（避免污染）
5. 深度限制（max_depth=3），防止无限递归
6. 仅返回最终摘要（不返回中间工具调用过程）
7. 通过 contextvars 注入事件回调，将子 Agent 执行过程推送到前端

设计原则（参考 hermes-agent / claude-code 的子 Agent 模式）：
- 子 Agent 只向主 Agent 汇报，不能与其他子 Agent 直接通信
- 嵌套委派通过 depth + 1 控制，接近最大深度时移除委派工具
- 事件回调通过 contextvars 传递，避免破坏 ToolBase 接口
"""
import contextvars
from typing import Any, Awaitable, Callable

from loguru import logger

from app.core.tools.registry import ToolBase, ToolResult


# 子 Agent 事件回调类型：接收事件字典，异步返回 None
SubagentEventCallback = Callable[[dict[str, Any]], Awaitable[None]]

# 上下文变量：在主 Agent 工具调用循环中设置，子 Agent 委派工具读取
# 使用 contextvars 确保异步上下文安全，避免破坏 ToolBase.execute 签名
_subagent_event_callback_var: contextvars.ContextVar[SubagentEventCallback | None] = contextvars.ContextVar(
    "luominest_subagent_event_callback",
    default=None,
)


def set_subagent_event_callback(callback: SubagentEventCallback | None):
    """设置当前异步上下文中的子 Agent 事件回调

    由 ChatService.stream_response 在主 Agent 工具调用循环中调用，
    使 DelegateToSubagentTool 能将子 Agent 执行事件推送到 SSE 流。
    """
    return _subagent_event_callback_var.set(callback)


def reset_subagent_event_callback(token) -> None:
    """重置子 Agent 事件回调到之前的状态"""
    _subagent_event_callback_var.reset(token)


def get_subagent_event_callback() -> SubagentEventCallback | None:
    """读取当前异步上下文中的子 Agent 事件回调

    供 workflow 路径的工具（如 browser.navigate、subagent.delegate）使用，
    使它们能将事件推送到与 DelegateToSubagentTool 相同的 SSE 流。
    """
    return _subagent_event_callback_var.get()


async def emit_luominest_subagent_event(event: dict[str, Any]) -> None:
    """向当前异步上下文的子 Agent 事件回调推送一个事件

    若当前上下文未设置回调（例如不在 chat_service 工具循环中），则静默跳过。
    供 workflow 工具（browser.navigate/open_tab/close_tab 等）使用，
    替代历史上不存在的 `_emit_subagent_event` 符号。
    """
    callback = _subagent_event_callback_var.get()
    if callback is None:
        return
    try:
        await callback(event)
    except Exception as e:
        logger.warning(f"[subagent_tool] 事件回调推送失败: {e}")


class DelegateToSubagentTool(ToolBase):
    """子 Agent 委派工具"""

    @property
    def name(self) -> str:
        return "delegate_to_subagent"

    @property
    def description(self) -> str:
        return (
            "将子任务委派给子 Agent 独立执行。适用于："
            "1. 需要并行处理的独立子任务；"
            "2. 需要独立上下文避免污染的审查任务；"
            "3. 需要专注完成的特定子任务。"
            "子 Agent 拥有独立上下文，不继承当前对话历史，"
            "执行完成后仅返回最终结果摘要。"
            "支持嵌套委派（最大深度 3）。"
            "可选传入 consensus_content 共识规范，确保多子 Agent 协同一致。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "委派给子 Agent 的任务描述（应清晰、具体、可独立完成）",
                },
                "context": {
                    "type": "string",
                    "description": "附加上下文信息（可选）。如相关背景、约束条件、参考资料等。",
                    "default": "",
                },
                "consensus_content": {
                    "type": "string",
                    "description": "共识规范（可选）。注入子 Agent 系统提示词的【Luminous 共识规范】段，确保多子 Agent 协同一致。通常由调度员自动生成。",
                    "default": "",
                },
            },
            "required": ["task"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        task = arguments.get("task", "").strip()
        if not task:
            return ToolResult.fail("缺少 task 参数")

        context = arguments.get("context", "") or ""
        consensus_content = arguments.get("consensus_content", "") or ""

        # 通过子 Agent 委派端口调用（组合根可覆盖实现；端口兜底延迟导入执行器单例）
        try:
            from app.core.ports.subagent_delegation import delegate_task
        except Exception as e:
            logger.error(f"[DelegateToSubagentTool] 导入子 Agent 委派端口失败: {e}")
            return ToolResult.fail(f"子 Agent 委派端口不可用: {e}")

        # 从 contextvars 读取事件回调
        event_callback = _subagent_event_callback_var.get()

        logger.info(
            f"[DelegateToSubagentTool] 委派子 Agent: "
            f"task_len={len(task)}, context_len={len(context)}, "
            f"has_callback={event_callback is not None}, "
            f"has_consensus={bool(consensus_content)}"
        )

        try:
            result = await delegate_task(
                task,
                context=context,
                depth=0,  # 主 Agent 直接委派，深度从 0 开始
                event_callback=event_callback,
                consensus_content=consensus_content or None,
            )
            logger.info(
                f"[DelegateToSubagentTool] 子 Agent 完成: "
                f"result_len={len(result)}"
            )
            return ToolResult.ok(
                result,
                metadata={"task_len": len(task), "result_len": len(result)},
            )
        except Exception as e:
            logger.error(
                f"[DelegateToSubagentTool] 子 Agent 执行异常: {e}",
                exc_info=True,
            )
            return ToolResult.fail(f"子 Agent 执行失败: {e}")
