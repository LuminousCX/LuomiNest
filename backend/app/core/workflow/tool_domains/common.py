"""工作流内部工具的共享基础设施。

从原 register_tools.py 拆出（大文件拆分重构），供 tool_domains 各域模块
与 register_tools 入口共用。事件推送器字典 `_active_emitters` 全局唯一，
`set_emitter`/`remove_emitter` 经 register_tools re-export 维持原导入路径。
"""

import functools

from loguru import logger

from app.core.workflow.event_emitter import WorkflowEventEmitter
from app.core.workflow.models import WorkflowTaskResult

# 当前活跃的事件推送器（由 WorkflowEngine 在执行前设置）
# key: session_id, value: WorkflowEventEmitter
_active_emitters: dict[str, WorkflowEventEmitter] = {}


def set_emitter(session_id: str, emitter: WorkflowEventEmitter) -> None:
    """设置当前工作流会话的事件推送器"""
    _active_emitters[session_id] = emitter


def remove_emitter(session_id: str) -> None:
    """移除事件推送器"""
    _active_emitters.pop(session_id, None)


def _get_emitter() -> WorkflowEventEmitter | None:
    """获取当前活跃的事件推送器（取最后一个）"""
    if not _active_emitters:
        return None
    # 返回最后注册的 emitter（当前正在执行的会话）
    return list(_active_emitters.values())[-1]


def _wf_catch(tool_name: str):
    """工作流工具 try/except 装饰器，统一错误日志和返回值。"""
    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            try:
                return await fn(*args, **kwargs)
            except Exception as e:
                logger.error(f"[Workflow:{tool_name}] Failed: {{}}", str(e), exc_info=True)
                return WorkflowTaskResult(success=False, error=str(e))
        return wrapper
    return decorator
