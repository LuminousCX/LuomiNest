"""任务调度执行端口（六边形架构）。

内层工具（core.tools.builtin.scheduler_tool 等）只依赖本端口的
get_scheduler / 便捷函数契约，不再直接 import app.core.scheduler.manager；
具体调度器实例可在组合根通过 register_task_scheduler() 显式注入；
未注入时回退到内置兜底实现（对 luomi_scheduler 单例采用延迟导入，
避免核心模块之间形成顶层导入环）。

依赖方向纪律：
- 本端口不得顶层 import app.core.scheduler.*；
- 兜底实现内部延迟导入，保持"外层 → 端口 → （延迟）实现"的单向依赖。
"""
from typing import Any

from loguru import logger

# 调度器实例持有槽（对象端口：暴露调度器实例本身，
# 而非单一 callable —— 消费方需要 is_running/list_tasks/get_task 等多个方法）
_scheduler: Any | None = None


def register_task_scheduler(scheduler: Any | None) -> None:
    """注册任务调度器实例（由组合根/测试调用）。

    Args:
        scheduler: LuomiSchedulerManager 兼容实例（is_running/add_task/
            get_task/list_tasks/remove_task）；传 None 清除注册，回退兜底实现。
    """
    global _scheduler
    _scheduler = scheduler


def _default_scheduler() -> Any:
    """默认兜底实现：返回全局 luomi_scheduler 单例。

    延迟导入 —— 避免本端口顶层依赖 app.core.scheduler（依赖方向纪律）。
    """
    from app.core.scheduler.manager import luomi_scheduler

    return luomi_scheduler


def get_scheduler() -> Any:
    """获取已注册的调度器实例（未注册时回退兜底实现）。"""
    scheduler = _scheduler or _default_scheduler()
    logger.debug("[TaskSchedulingPort] get_scheduler")
    return scheduler


# ── 便捷入口（消费方可直接调用，无需持有调度器实例）──

def scheduler_is_running() -> bool:
    """调度器是否已启动。"""
    return bool(get_scheduler().is_running)


def list_scheduled() -> list:
    """列出所有定时任务（ScheduledTaskInfo 列表）。"""
    return get_scheduler().list_tasks()


def get_scheduled(task_id: str):
    """获取单个定时任务详情，不存在时返回 None。"""
    return get_scheduler().get_task(task_id)


async def remove_scheduled(task_id: str) -> bool:
    """删除定时任务，返回是否成功。"""
    return await get_scheduler().remove_task(task_id)


async def add_scheduled(config: Any) -> str:
    """添加定时任务（ScheduledTaskConfig），返回 task_id。"""
    return await get_scheduler().add_task(config)
