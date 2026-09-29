"""LuomiNest 定时任务数据模型。

定义定时任务的配置、状态与事件结构。
任务类型支持：一次性定时、cron 表达式、间隔执行。
"""
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.core.utils import utc_now


class LuomiTaskType(str, Enum):
    """定时任务类型"""
    DATE = "date"          # 一次性任务，在指定时间执行
    CRON = "cron"          # cron 表达式任务
    INTERVAL = "interval"  # 间隔执行任务


class LuomiTaskStatus(str, Enum):
    """定时任务状态"""
    PENDING = "pending"      # 已创建，等待触发
    RUNNING = "running"      # 正在执行
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"        # 执行失败
    REMOVED = "removed"      # 已移除


# 结果投递来源类型（origin_kind，P0-1 定时任务闭环）。
# 核心定义处：调度器持久化、创建工具、结果投递器共用同一组取值。
ORIGIN_WEB_CONVERSATION = "web_conversation"  # 网页会话（origin_ref=会话 ID）
ORIGIN_PLATFORM = "platform"                  # 平台会话（origin_ref=instance_id:session_id）
ORIGIN_API = "api"                            # REST 等无会话路径（结果仅留在任务记录）


class ScheduledTaskConfig(BaseModel):
    """定时任务配置（创建时传入）"""
    name: str = Field(..., description="任务名称")
    description: str = Field("", description="任务描述")
    task_type: LuomiTaskType = Field(..., description="任务类型")
    # date 类型：ISO 格式时间字符串，如 "2026-06-21T08:00:00"
    run_date: str | None = Field(None, description="一次性任务执行时间（ISO 格式）")
    # cron 类型：cron 表达式字段
    cron_year: str | None = Field(None, description="cron 年")
    cron_month: str | None = Field(None, description="cron 月")
    cron_day: str | None = Field(None, description="cron 日")
    cron_week: str | None = Field(None, description="cron 周")
    cron_day_of_week: str | None = Field(None, description="cron 星期")
    cron_hour: str | None = Field(None, description="cron 时")
    cron_minute: str | None = Field(None, description="cron 分")
    cron_second: str | None = Field(None, description="cron 秒")
    # interval 类型：间隔秒数
    interval_seconds: int | None = Field(None, description="间隔执行秒数")
    # 任务载荷：主 Agent 委派的指令
    payload: dict[str, Any] = Field(default_factory=dict, description="任务载荷")
    # 来源标识
    source: str = Field("main_agent", description="任务来源（main_agent/manual/api）")
    # 结果投递来源（P0-1 闭环）：决定任务触发后执行结果投递到哪里
    origin_kind: str = Field(
        "api",
        description="创建来源渠道：web_conversation（网页会话）/ platform（平台会话）/ api（REST 等无会话路径）",
    )
    origin_ref: str = Field(
        "",
        description="投递目标引用：web_conversation 存会话 ID；platform 存 'instance_id:session_id'",
    )
    origin_target: str = Field(
        "",
        description="显式指定投递目标（D5，可选）：如 'group:123' / 'private:456'，优先于 origin_ref 推导",
    )


class ScheduledTaskInfo(BaseModel):
    """定时任务信息（查询/列表返回）"""
    id: str
    name: str
    description: str
    task_type: LuomiTaskType
    status: LuomiTaskStatus
    next_run_time: str | None = None
    last_run_time: str | None = None
    last_result: str | None = None
    last_error: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    source: str = "main_agent"
    origin_kind: str = "api"
    origin_ref: str = ""
    origin_target: str = ""
    created_at: str = ""


class TaskEvent(BaseModel):
    """任务执行事件（推送到前端）"""
    task_id: str
    task_name: str
    status: LuomiTaskStatus
    task_type: LuomiTaskType
    message: str = ""
    result: str | None = None
    error: str | None = None
    timestamp: str = Field(default_factory=utc_now)
    payload: dict[str, Any] = Field(default_factory=dict)
