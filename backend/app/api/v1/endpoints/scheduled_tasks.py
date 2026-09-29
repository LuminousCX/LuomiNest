"""LuomiNest 定时任务 REST API。

提供定时任务的增删查改接口：
- GET    /scheduled-tasks           列出所有定时任务
- POST   /scheduled-tasks           创建定时任务
- DELETE /scheduled-tasks/{task_id} 删除定时任务

数据源为数据库（ScheduledTaskORM），与 luominest_scheduler 双写。
"""
from fastapi import APIRouter
from loguru import logger
from pydantic import BaseModel, Field

from app.core.exceptions import NotFoundError

from app.services.scheduled_task_persistence import (
    delete_scheduled_task,
    list_scheduled_tasks,
    save_scheduled_task,
)

router = APIRouter(prefix="/scheduled-tasks", tags=["scheduled-tasks"])


class CreateScheduledTaskRequest(BaseModel):
    """创建定时任务请求"""
    name: str = Field(..., description="任务名称")
    schedule_cron: str = Field("", description="cron 表达式（如 '0 9 * * *' 表示每天 9 点）")
    schedule_type: str = Field("cron", description="调度类型：cron/interval/once")
    action: str = Field(..., description="任务触发时执行的指令")
    description: str | None = Field(None, description="任务详细描述")
    context: str | None = Field(None, description="附加上下文信息")
    created_from: str = Field("manual", description="创建来源：manual/workflow/normal_chat")
    run_at: str | None = Field(None, description="once/date 任务的 ISO 执行时间（P0-1）")
    interval_seconds: int | None = Field(None, description="interval 任务的间隔秒数（P0-1）")


# 遗留 schedule_type → 权威 trigger_type 映射（once/date 归一为 date）
_LEGACY_TYPE_MAP = {"cron": "cron", "interval": "interval", "once": "date", "date": "date"}


@router.get("")
async def get_scheduled_tasks():
    """列出所有定时任务"""
    tasks = await list_scheduled_tasks()
    return {"tasks": tasks, "count": len(tasks)}


@router.post("")
async def create_scheduled_task(req: CreateScheduledTaskRequest):
    """创建定时任务（写入数据库 + 注册到调度器）"""
    import uuid

    task_id = f"task_{uuid.uuid4().hex[:12]}"

    # P0-1：按权威 trigger_type 写入触发信息列（REST 端点创建标 api 来源，结果仅留任务记录）
    trigger_type = _LEGACY_TYPE_MAP.get(req.schedule_type.strip().lower(), "cron")
    run_at = req.run_at
    if trigger_type == "date" and not run_at and req.schedule_cron:
        # 兼容旧客户端：once 类型曾把执行时间塞在 schedule_cron 字段
        run_at = req.schedule_cron.strip()

    # 写入数据库
    await save_scheduled_task(
        task_id=task_id,
        name=req.name,
        schedule_cron=req.schedule_cron if trigger_type == "cron" else "",
        schedule_type=req.schedule_type,
        action=req.action,
        description=req.description,
        context=req.context,
        created_from=req.created_from,
        trigger_type=trigger_type,
        run_at=run_at,
        interval_seconds=req.interval_seconds,
        origin_kind="api",
    )

    # 同步注册到调度器（可选，调度器未启动时跳过）；P0-1：按 trigger_type 分支注册，
    # once/date 不再被误当 cron（旧实现把 ISO 串拆 cron 字段会产生每秒执行的幻象任务）
    try:
        from app.core.scheduler.models import LuomiTaskType, ScheduledTaskConfig
        from app.core.scheduler.manager import luominest_scheduler

        if luominest_scheduler.is_running:
            common = dict(
                name=req.name,
                description=req.description or "",
                payload={
                    "instruction": req.action,
                    "context": req.context or "",
                },
                source=req.created_from,
                origin_kind="api",
            )
            if trigger_type == "date":
                if not run_at:
                    raise ValueError("once/date 任务缺少 run_at，无法注册到调度器")
                config = ScheduledTaskConfig(
                    task_type=LuomiTaskType.DATE, run_date=run_at, **common
                )
            elif trigger_type == "interval":
                if not req.interval_seconds or req.interval_seconds <= 0:
                    raise ValueError("interval 任务缺少有效 interval_seconds")
                config = ScheduledTaskConfig(
                    task_type=LuomiTaskType.INTERVAL,
                    interval_seconds=req.interval_seconds,
                    **common,
                )
            else:
                config = ScheduledTaskConfig(
                    task_type=LuomiTaskType.CRON,
                    cron_hour=str(_parse_cron_field(req.schedule_cron, 1)),
                    cron_minute=str(_parse_cron_field(req.schedule_cron, 0)),
                    cron_day_of_week=_parse_cron_field(req.schedule_cron, 4),
                    **common,
                )
            scheduler_task_id = await luominest_scheduler.add_task(config)
            logger.info(
                f"[ScheduledTaskAPI] Task registered to scheduler: "
                f"db_id={task_id}, scheduler_id={scheduler_task_id}"
            )
    except Exception as e:
        logger.warning(f"[ScheduledTaskAPI] Scheduler registration skipped: {e}")

    return {"success": True, "task_id": task_id}


@router.delete("/{task_id}")
async def remove_scheduled_task(task_id: str):
    """删除定时任务"""
    # 从数据库删除
    db_deleted = await delete_scheduled_task(task_id)

    # 从调度器删除（可选）
    try:
        from app.core.scheduler.manager import luominest_scheduler
        if luominest_scheduler.is_running:
            await luominest_scheduler.remove_task(task_id)
    except Exception as e:
        logger.warning(f"[ScheduledTaskAPI] Scheduler removal skipped: {e}")

    if not db_deleted:
        raise NotFoundError(f"任务 {task_id} 不存在", code="SCHEDULER_TASK_NOT_FOUND")

    return {"success": True, "task_id": task_id}


def _parse_cron_field(cron_expr: str, field_index: int) -> str:
    """从 cron 表达式中提取指定字段（0=minute, 1=hour, 4=day_of_week）"""
    parts = cron_expr.strip().split()
    if len(parts) <= field_index:
        return "*"
    return parts[field_index]
