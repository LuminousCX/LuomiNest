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

    # 写入数据库
    await save_scheduled_task(
        task_id=task_id,
        name=req.name,
        schedule_cron=req.schedule_cron,
        schedule_type=req.schedule_type,
        action=req.action,
        description=req.description,
        context=req.context,
        created_from=req.created_from,
    )

    # 同步注册到调度器（可选，调度器未启动时跳过）
    try:
        from app.core.scheduler.models import LuomiTaskType, ScheduledTaskConfig
        from app.core.scheduler.manager import luominest_scheduler

        if luominest_scheduler.is_running and req.schedule_cron:
            config = ScheduledTaskConfig(
                name=req.name,
                description=req.description or "",
                task_type=LuomiTaskType.CRON,
                cron_hour=str(_parse_cron_field(req.schedule_cron, 1)),
                cron_minute=str(_parse_cron_field(req.schedule_cron, 0)),
                cron_day_of_week=_parse_cron_field(req.schedule_cron, 4),
                payload={
                    "instruction": req.action,
                    "context": req.context or "",
                },
                source=req.created_from,
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
