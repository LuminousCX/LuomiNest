"""LuomiNest 定时任务持久化服务。

将定时任务持久化到数据库，替代 scheduler 的 JSON 文件存储。
与 luomi_scheduler 双写：数据库为主（历史回溯），JSON/内存为辅（运行时调度）。
"""
import json
from datetime import datetime, timezone
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.infrastructure.database.models.scheduled_task import ScheduledTaskORM
from app.infrastructure.database.session import get_async_session


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def save_scheduled_task(
    task_id: str,
    name: str,
    schedule_cron: str,
    schedule_type: str,
    action: str,
    description: str | None = None,
    context: str | None = None,
    created_from: str = "manual",
    is_active: bool = True,
) -> None:
    """保存或更新定时任务（upsert）"""
    async with get_async_session() as db:
        stmt = sqlite_insert(ScheduledTaskORM).values(
            task_id=task_id,
            name=name,
            schedule_cron=schedule_cron,
            schedule_type=schedule_type,
            action=action,
            description=description,
            context=context,
            created_from=created_from,
            is_active=is_active,
            created_at=_utc_now(),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["task_id"],
            set_={
                "name": name,
                "schedule_cron": schedule_cron,
                "schedule_type": schedule_type,
                "action": action,
                "description": description,
                "context": context,
                "is_active": is_active,
            },
        )
        await db.execute(stmt)
        await db.commit()
        logger.debug(f"[ScheduledTaskPersistence] Task {task_id} saved (name={name})")


async def list_scheduled_tasks() -> list[dict[str, Any]]:
    """列出所有定时任务"""
    async with get_async_session() as db:
        result = await db.execute(
            select(ScheduledTaskORM)
            .order_by(ScheduledTaskORM.created_at.desc())
        )
        tasks = result.scalars().all()
        return [
            {
                "task_id": t.task_id,
                "name": t.name,
                "schedule_cron": t.schedule_cron,
                "schedule_type": t.schedule_type,
                "action": t.action,
                "description": t.description,
                "context": t.context,
                "created_from": t.created_from,
                "is_active": t.is_active,
                "created_at": t.created_at,
                "last_run_at": t.last_run_at,
            }
            for t in tasks
        ]


async def delete_scheduled_task(task_id: str) -> bool:
    """删除定时任务"""
    from sqlalchemy import delete as sql_delete

    async with get_async_session() as db:
        result = await db.execute(
            sql_delete(ScheduledTaskORM).where(ScheduledTaskORM.task_id == task_id)
        )
        await db.commit()
        deleted = result.rowcount > 0
        if deleted:
            logger.debug(f"[ScheduledTaskPersistence] Task {task_id} deleted")
        return deleted


async def update_last_run(task_id: str) -> None:
    """更新任务最后执行时间"""
    async with get_async_session() as db:
        stmt = sqlite_insert(ScheduledTaskORM).values(
            task_id=task_id,
            name="",
            schedule_cron="",
            schedule_type="cron",
            action="",
            created_at=_utc_now(),
            last_run_at=_utc_now(),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["task_id"],
            set_={"last_run_at": _utc_now()},
        )
        await db.execute(stmt)
        await db.commit()
