"""子 Agent 委派端口（六边形架构）。

内层消费方（core.scheduler / core.tools.builtin.subagent_tool 等）只依赖本端口的
delegate_task 契约，不再直接 import app.core.agents.subagent_executor；
具体执行器可在组合根通过 register_subagent_delegate() 显式注入；
未注入时回退到内置兜底实现（对 subagent_executor 单例采用延迟导入，
避免核心模块之间形成顶层导入环）。

依赖方向纪律：
- 本端口不得顶层 import 任何具体执行器模块（app.core.agents.*）；
- 兜底实现内部延迟导入，保持"外层 → 端口 → （延迟）实现"的单向依赖。
"""
from typing import Any, Awaitable, Callable

from loguru import logger

# 委派执行器契约：与 SubagentExecutor.execute 关键字兼容
# (task=..., context=..., depth=..., **kwargs) -> 子 Agent 最终结果文本
SubagentDelegate = Callable[..., Awaitable[str]]

_executor: SubagentDelegate | None = None


def register_subagent_delegate(delegate: SubagentDelegate | None) -> None:
    """注册子 Agent 委派执行器（由组合根/测试调用）。

    Args:
        delegate: 异步可调用对象，签名兼容 SubagentExecutor.execute
            （task/context/depth 及可选 kwargs）；传 None 清除注册，回退兜底实现。
    """
    global _executor
    _executor = delegate


async def _default_delegate(task: str, context: str = "", depth: int = 0, **kwargs: Any) -> str:
    """默认兜底实现：委派给全局 subagent_executor 单例。

    延迟导入 —— 避免本端口顶层依赖 app.core.agents（依赖方向纪律）。
    """
    from app.core.agents.subagent_executor import subagent_executor

    return await subagent_executor.execute(task=task, context=context, depth=depth, **kwargs)


async def delegate_task(task: str, context: str = "", depth: int = 0, **kwargs: Any) -> str:
    """通过已注册的执行器委派子 Agent 任务（未注册时回退兜底实现）。

    Args:
        task: 委派给子 Agent 的任务描述
        context: 附加上下文信息（可选）
        depth: 当前委派深度（0=主 Agent 直接委派）
        **kwargs: 透传给执行器的其余参数（event_callback/consensus_content/
            timeout_seconds/cancel_event/task_id/provider/model 等）

    Returns:
        子 Agent 的最终结果文本
    """
    delegate = _executor or _default_delegate
    logger.debug(f"[SubagentDelegationPort] delegate_task depth={depth} task_len={len(task)}")
    return await delegate(task=task, context=context, depth=depth, **kwargs)
