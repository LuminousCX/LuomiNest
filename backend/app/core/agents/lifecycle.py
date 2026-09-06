"""LuomiNest 子 Agent 任务生命周期管理。

参考 deer-flow 的 SubagentStatus 状态机（Demo/deer-flow/backend/packages/harness/deerflow/subagents/executor.py），
为 LuomiNest 子 Agent 系统提供显式生命周期跟踪与协作式取消能力。

状态转换：
    PENDING → RUNNING → COMPLETED
                       → FAILED
                       → CANCELLED
                       → TIMED_OUT

设计要点：
1. 终结状态（COMPLETED/FAILED/CANCELLED/TIMED_OUT）不可逆
2. cancel_event 为协作式取消，子 Agent 在迭代边界检查
3. Registry 仅管理活跃任务，终结任务可通过 cleanup_terminal 清理
"""
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from loguru import logger

from app.core.utils import utc_now_dt


class LuomiNestTaskStatus(str, Enum):
    """子 Agent 任务状态枚举"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"

    @property
    def is_terminal(self) -> bool:
        """是否为终结状态（不可逆）"""
        return self in (
            LuomiNestTaskStatus.COMPLETED,
            LuomiNestTaskStatus.FAILED,
            LuomiNestTaskStatus.CANCELLED,
            LuomiNestTaskStatus.TIMED_OUT,
        )


@dataclass
class LuomiNestTaskRecord:
    """子 Agent 任务记录

    跟踪单个子 Agent 任务的完整生命周期信息。
    """

    task_id: str
    status: LuomiNestTaskStatus = LuomiNestTaskStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: str = ""
    error: str = ""
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    metadata: dict[str, Any] = field(default_factory=dict)

    def mark_running(self) -> None:
        """标记为运行中"""
        self.status = LuomiNestTaskStatus.RUNNING
        self.started_at = utc_now_dt()

    def mark_completed(self, result: str) -> None:
        """标记为已完成"""
        self.status = LuomiNestTaskStatus.COMPLETED
        self.result = result
        self.completed_at = utc_now_dt()

    def mark_failed(self, error: str) -> None:
        """标记为失败"""
        self.status = LuomiNestTaskStatus.FAILED
        self.error = error
        self.completed_at = utc_now_dt()

    def mark_cancelled(self) -> None:
        """标记为已取消"""
        self.status = LuomiNestTaskStatus.CANCELLED
        self.completed_at = utc_now_dt()

    def mark_timed_out(self) -> None:
        """标记为超时"""
        self.status = LuomiNestTaskStatus.TIMED_OUT
        self.completed_at = utc_now_dt()

    def request_cancel(self) -> None:
        """请求取消（协作式，子 Agent 在迭代边界检查 cancel_event）"""
        self.cancel_event.set()


class LuomiNestTaskRegistry:
    """子 Agent 任务注册表（全局单例）

    管理所有活跃子 Agent 任务的记录，支持查询、取消、清理。
    线程安全（异步锁保护内部字典）。
    """

    def __init__(self) -> None:
        self._tasks: dict[str, LuomiNestTaskRecord] = {}
        self._lock = asyncio.Lock()

    async def register(self, task_id: str, record: LuomiNestTaskRecord) -> None:
        """注册新任务记录"""
        async with self._lock:
            self._tasks[task_id] = record

    async def get(self, task_id: str) -> LuomiNestTaskRecord | None:
        """获取任务记录"""
        async with self._lock:
            return self._tasks.get(task_id)

    async def cancel(self, task_id: str) -> bool:
        """请求取消任务

        Returns:
            True 如果找到任务并设置了取消信号；False 如果任务不存在或已终结
        """
        async with self._lock:
            record = self._tasks.get(task_id)
            if record is None or record.status.is_terminal:
                return False
            record.request_cancel()
            logger.info(f"[TaskRegistry] 任务 {task_id} 已请求取消")
            return True

    async def remove(self, task_id: str) -> None:
        """移除任务记录"""
        async with self._lock:
            self._tasks.pop(task_id, None)

    async def cleanup_terminal(self) -> int:
        """清理所有已终结的任务记录

        Returns:
            清理的任务数量
        """
        async with self._lock:
            terminal_ids = [
                tid
                for tid, rec in self._tasks.items()
                if rec.status.is_terminal
            ]
            for tid in terminal_ids:
                self._tasks.pop(tid, None)
            if terminal_ids:
                logger.info(f"[TaskRegistry] 清理 {len(terminal_ids)} 个终结任务")
            return len(terminal_ids)

    async def list_active(self) -> list[LuomiNestTaskRecord]:
        """列出所有活跃（非终结）任务"""
        async with self._lock:
            return [
                rec
                for rec in self._tasks.values()
                if not rec.status.is_terminal
            ]


# 全局单例
luominest_task_registry = LuomiNestTaskRegistry()
