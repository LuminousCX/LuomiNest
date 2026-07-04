"""工作流数据模型

定义工作流引擎的核心数据结构：状态枚举、任务模型、会话模型。

参考：
- deer-flow: RunStatus 状态机 + SubTask 数据类
- hermes-agent: CollaborationPhase 协作阶段
- claude-code: Task 任务类型体系
"""
import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class WorkflowStatus(str, Enum):
    """工作流任务执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class WorkflowPhase(str, Enum):
    """工作流执行阶段

    状态流转：analyzing → planning → waiting_confirmation → executing → synthesizing → completed
    任何阶段都可能转为 failed
    waiting_confirmation: 计划生成后暂停，等待用户确认（借鉴 deer-flow ClarificationMiddleware）
    """
    ANALYZING = "analyzing"
    PLANNING = "planning"
    WAITING_CONFIRMATION = "waiting_confirmation"
    EXECUTING = "executing"
    SYNTHESIZING = "synthesizing"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkflowPriority(str, Enum):
    """任务优先级"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class WorkflowMode(str, Enum):
    """工作流执行模式（仅工作流模式，普通模式见 ChatMode）

    不同模式调整迭代次数、并发度、温度等参数，适配不同复杂度的任务：
    - standard: 标准模式，平衡速度与深度（默认），排除细粒度浏览器自动化工具
    - ultra: 超长模式，最大能力，适合复杂长任务，全部工具可用
    """
    STANDARD = "standard"
    ULTRA = "ultra"


# 各模式的参数配置
MODE_CONFIGS: dict[WorkflowMode, dict[str, Any]] = {
    WorkflowMode.STANDARD: {
        "max_iterations": 20,
        "max_concurrent": 3,
        "planning_temperature": 0.3,
        "synthesis_temperature": 0.4,
        "planning_max_tokens": 2000,
        "skip_confirmation": False,
    },
    WorkflowMode.ULTRA: {
        "max_iterations": 100,
        "max_concurrent": 8,
        "planning_temperature": 0.5,
        "synthesis_temperature": 0.6,
        "planning_max_tokens": 4000,
        "skip_confirmation": False,
    },
}


class WorkflowTaskType(str, Enum):
    """子任务类型，对应内部模块接口分类"""
    BROWSER = "browser"
    SCHEDULE = "schedule"
    MEMORY = "memory"
    CONSOLE = "console"
    MARKET = "market"
    SMART_HOME = "smart_home"
    DEVICE = "device"
    PLATFORM = "platform"
    SUBAGENT = "subagent"
    CUSTOM = "custom"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class WorkflowTask:
    """工作流子任务

    代表长任务分解后的一个执行单元，由内部模块接口执行。
    """
    task_id: str = field(default_factory=lambda: f"wf_task_{uuid.uuid4().hex[:8]}")
    title: str = ""
    description: str = ""
    task_type: WorkflowTaskType = WorkflowTaskType.CUSTOM
    tool_name: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    priority: WorkflowPriority = WorkflowPriority.NORMAL
    node_type: str = "tool"
    status: WorkflowStatus = WorkflowStatus.PENDING
    result: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    started_at: str | None = None
    completed_at: str | None = None

    def mark_running(self) -> None:
        self.status = WorkflowStatus.RUNNING
        self.started_at = _utc_now()

    def mark_completed(self, result: str) -> None:
        self.status = WorkflowStatus.COMPLETED
        self.result = result
        self.completed_at = _utc_now()

    def mark_failed(self, error: str) -> None:
        self.status = WorkflowStatus.FAILED
        self.error = error
        self.completed_at = _utc_now()

    def mark_cancelled(self) -> None:
        self.status = WorkflowStatus.CANCELLED
        self.completed_at = _utc_now()

    def is_terminal(self) -> bool:
        return self.status in (
            WorkflowStatus.COMPLETED,
            WorkflowStatus.FAILED,
            WorkflowStatus.CANCELLED,
            WorkflowStatus.SKIPPED,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "description": self.description,
            "task_type": self.task_type.value,
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "depends_on": self.depends_on,
            "priority": self.priority.value,
            "node_type": self.node_type,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


@dataclass
class WorkflowTaskResult:
    """子任务执行结果"""
    success: bool
    output: str = ""
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "metadata": self.metadata,
        }


@dataclass
class WorkflowSession:
    """工作流会话

    一次长任务执行的完整上下文，包含原始请求、执行计划、所有子任务和最终结果。
    """
    session_id: str = field(default_factory=lambda: f"wf_session_{uuid.uuid4().hex[:12]}")
    user_message: str = ""
    phase: WorkflowPhase = WorkflowPhase.ANALYZING
    plan: str | None = None
    tasks: list[WorkflowTask] = field(default_factory=list)
    final_result: str | None = None
    error: str | None = None
    created_at: str = field(default_factory=_utc_now)
    completed_at: str | None = None
    max_iterations: int = 20
    max_concurrent: int = 3
    abort_requested: bool = False
    # 执行模式（P2：长任务执行模式）
    mode: WorkflowMode = WorkflowMode.STANDARD
    # 模式专属配置（由 MODE_CONFIGS 注入，避免运行时反复查表）
    planning_temperature: float = 0.3
    synthesis_temperature: float = 0.4
    planning_max_tokens: int = 2000
    skip_confirmation: bool = False
    # 关联对话 ID（用于持久化和前端跳转）
    conversation_id: str | None = None
    # 计划确认机制（借鉴 deer-flow ClarificationMiddleware）
    confirmation_event: asyncio.Event = field(default_factory=asyncio.Event, repr=False)
    confirmation_result: bool = False
    confirmation_feedback: str = ""

    @property
    def is_terminal(self) -> bool:
        return self.phase in (WorkflowPhase.COMPLETED, WorkflowPhase.FAILED)

    @property
    def completed_task_count(self) -> int:
        return sum(1 for t in self.tasks if t.status == WorkflowStatus.COMPLETED)

    @property
    def failed_task_count(self) -> int:
        return sum(1 for t in self.tasks if t.status == WorkflowStatus.FAILED)

    def get_task(self, task_id: str) -> WorkflowTask | None:
        for task in self.tasks:
            if task.task_id == task_id:
                return task
        return None

    def get_ready_tasks(self) -> list[WorkflowTask]:
        """获取所有依赖已满足且未执行的子任务"""
        completed_ids = {
            t.task_id for t in self.tasks
            if t.status == WorkflowStatus.COMPLETED
        }
        failed_ids = {
            t.task_id for t in self.tasks
            if t.status == WorkflowStatus.FAILED
        }
        ready = []
        for task in self.tasks:
            if task.status != WorkflowStatus.PENDING:
                continue
            if task.abort_requested:
                continue
            deps_ok = all(
                dep in completed_ids or dep in failed_ids
                for dep in task.depends_on
            )
            if deps_ok:
                ready.append(task)
        ready.sort(key=lambda t: {
            WorkflowPriority.URGENT: 0,
            WorkflowPriority.HIGH: 1,
            WorkflowPriority.NORMAL: 2,
            WorkflowPriority.LOW: 3,
        }[t.priority])
        return ready

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_message": self.user_message,
            "phase": self.phase.value,
            "plan": self.plan,
            "tasks": [t.to_dict() for t in self.tasks],
            "final_result": self.final_result,
            "error": self.error,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "conversation_id": self.conversation_id,
            "stats": {
                "total": len(self.tasks),
                "completed": self.completed_task_count,
                "failed": self.failed_task_count,
            },
        }
