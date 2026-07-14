"""LuomiNest 定时任务调度器 REST API。

提供定时任务的 CRUD 操作：
- GET    /scheduler/tasks        列出所有任务
- GET    /scheduler/tasks/{id}   获取单个任务
- POST   /scheduler/tasks        创建任务
- DELETE /scheduler/tasks/{id}   删除任务
- GET    /scheduler/status       调度器状态
"""
from fastapi import APIRouter, HTTPException
from loguru import logger

from app.core.exceptions import LuomiNestError
from app.core.scheduler import (
    LuomiTaskStatus,
    LuomiTaskType,
    ScheduledTaskConfig,
    luomi_scheduler,
)

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


@router.get("/status")
async def get_scheduler_status():
    """获取调度器运行状态"""
    return {
        "running": luomi_scheduler.is_running,
        "task_count": len(luomi_scheduler.list_tasks()),
    }


@router.get("/tasks")
async def list_tasks():
    """列出所有定时任务"""
    tasks = luomi_scheduler.list_tasks()
    return [t.model_dump() for t in tasks]


@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """获取单个定时任务"""
    task = luomi_scheduler.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")
    return task.model_dump()


@router.post("/tasks")
async def create_task(config: ScheduledTaskConfig):
    """手动创建定时任务"""
    if not luomi_scheduler.is_running:
        raise HTTPException(status_code=503, detail="调度器未启动")
    try:
        task_id = await luomi_scheduler.add_task(config)
        task = luomi_scheduler.get_task(task_id)
        return task.model_dump() if task else {"id": task_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[SchedulerAPI] 创建任务失败: {e}", exc_info=True)
        raise LuomiNestError(
            "定时任务创建失败，请稍后重试",
            code="SCHEDULER_TASK_CREATE_FAILED",
            status_code=500,
        )


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    """删除定时任务"""
    success = await luomi_scheduler.remove_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")
    return {"success": True, "task_id": task_id}
