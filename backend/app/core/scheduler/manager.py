"""LuomiNest 定时任务调度器管理器。

基于 APScheduler AsyncIOScheduler 实现，支持：
1. 一次性定时任务（date）
2. cron 表达式任务
3. 间隔执行任务（interval）

任务执行时通过事件回调通知前端（SSE）和主 Agent。
配置持久化到 {DATA_DIR}/scheduled_tasks.json。
"""
import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from app.core.config import settings
from app.core.scheduler.models import (
    LuomiTaskStatus,
    LuomiTaskType,
    ScheduledTaskConfig,
    ScheduledTaskInfo,
    TaskEvent,
)


# 任务事件回调类型：接收 TaskEvent，异步返回 None
TaskEventCallback = Callable[[TaskEvent], Awaitable[None]]


class LuomiSchedulerManager:
    """LuomiNest 定时任务调度器管理器（单例）"""

    def __init__(self) -> None:
        self._scheduler: AsyncIOScheduler | None = None
        self._tasks: dict[str, dict[str, Any]] = {}  # task_id -> task info dict
        self._event_callbacks: list[TaskEventCallback] = []
        self._config_file: Path = Path(settings.DATA_DIR) / "scheduled_tasks.json"
        self._started = False

    @property
    def is_running(self) -> bool:
        return self._started and self._scheduler is not None and self._scheduler.running

    def add_event_callback(self, callback: TaskEventCallback) -> None:
        """注册任务事件回调（用于 SSE 推送）"""
        self._event_callbacks.append(callback)

    async def _emit_event(self, event: TaskEvent) -> None:
        """安全推送任务事件到所有回调"""
        for cb in self._event_callbacks:
            try:
                await cb(event)
            except Exception as e:
                logger.warning(f"[LuomiScheduler] 事件回调失败: {e}")

    async def init(self) -> None:
        """初始化调度器并加载持久化配置"""
        if self._started:
            return

        self._scheduler = AsyncIOScheduler(
            timezone="Asia/Shanghai",
            job_defaults={"coalesce": True, "max_instances": 1},
        )
        self._scheduler.start()
        self._started = True
        logger.info("[LuomiScheduler] 调度器已启动")

        # 加载持久化任务
        await self._load_persisted_tasks()

    async def shutdown(self) -> None:
        """关闭调度器"""
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("[LuomiScheduler] 调度器已关闭")
        self._started = False

    async def _load_persisted_tasks(self) -> None:
        """从配置文件加载持久化任务"""
        if not self._config_file.exists():
            return

        try:
            data = json.loads(self._config_file.read_text(encoding="utf-8"))
            count = 0
            for task_data in data.get("tasks", []):
                task_id = task_data.get("id", "")
                if not task_id:
                    continue
                # 跳过已完成的 date 类型任务
                if task_data.get("status") in (LuomiTaskStatus.COMPLETED.value, LuomiTaskStatus.REMOVED.value):
                    continue
                # 重新调度
                config = ScheduledTaskConfig(
                    name=task_data.get("name", ""),
                    description=task_data.get("description", ""),
                    task_type=LuomiTaskType(task_data.get("task_type", LuomiTaskType.DATE.value)),
                    run_date=task_data.get("run_date"),
                    cron_year=task_data.get("cron_year"),
                    cron_month=task_data.get("cron_month"),
                    cron_day=task_data.get("cron_day"),
                    cron_week=task_data.get("cron_week"),
                    cron_day_of_week=task_data.get("cron_day_of_week"),
                    cron_hour=task_data.get("cron_hour"),
                    cron_minute=task_data.get("cron_minute"),
                    cron_second=task_data.get("cron_second"),
                    interval_seconds=task_data.get("interval_seconds"),
                    payload=task_data.get("payload", {}),
                    source=task_data.get("source", "main_agent"),
                )
                try:
                    await self._reschedule_task(task_id, config)
                    count += 1
                except Exception as e:
                    logger.warning(f"[LuomiScheduler] 恢复任务 {task_id} 失败: {e}")
            logger.info(f"[LuomiScheduler] 恢复 {count} 个持久化任务")
        except Exception as e:
            logger.warning(f"[LuomiScheduler] 加载持久化任务失败: {e}")

    async def _persist_tasks(self) -> None:
        """持久化任务配置到文件"""
        try:
            self._config_file.parent.mkdir(parents=True, exist_ok=True)
            tasks_data = []
            for task_id, info in self._tasks.items():
                tasks_data.append({
                    "id": task_id,
                    "name": info.get("name", ""),
                    "description": info.get("description", ""),
                    "task_type": info.get("task_type", LuomiTaskType.DATE.value),
                    "status": info.get("status", LuomiTaskStatus.PENDING.value),
                    "run_date": info.get("run_date"),
                    "cron_year": info.get("cron_year"),
                    "cron_month": info.get("cron_month"),
                    "cron_day": info.get("cron_day"),
                    "cron_week": info.get("cron_week"),
                    "cron_day_of_week": info.get("cron_day_of_week"),
                    "cron_hour": info.get("cron_hour"),
                    "cron_minute": info.get("cron_minute"),
                    "cron_second": info.get("cron_second"),
                    "interval_seconds": info.get("interval_seconds"),
                    "payload": info.get("payload", {}),
                    "source": info.get("source", "main_agent"),
                })
            self._config_file.write_text(
                json.dumps({"tasks": tasks_data}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"[LuomiScheduler] 持久化任务失败: {e}")

    def _build_trigger(self, config: ScheduledTaskConfig):
        """根据配置构建 APScheduler trigger"""
        if config.task_type == LuomiTaskType.DATE:
            if not config.run_date:
                raise ValueError("date 类型任务需要 run_date 参数")
            run_dt = datetime.fromisoformat(config.run_date)
            return DateTrigger(run_date=run_dt)

        if config.task_type == LuomiTaskType.CRON:
            return CronTrigger(
                year=config.cron_year,
                month=config.cron_month,
                day=config.cron_day,
                week=config.cron_week,
                day_of_week=config.cron_day_of_week,
                hour=config.cron_hour,
                minute=config.cron_minute,
                second=config.cron_second,
            )

        if config.task_type == LuomiTaskType.INTERVAL:
            if not config.interval_seconds or config.interval_seconds <= 0:
                raise ValueError("interval 类型任务需要正数 interval_seconds")
            return IntervalTrigger(seconds=config.interval_seconds)

        raise ValueError(f"不支持的任务类型: {config.task_type}")

    async def add_task(self, config: ScheduledTaskConfig) -> str:
        """添加定时任务"""
        if not self.is_running:
            raise RuntimeError("调度器未启动")

        task_id = f"lumi_task_{uuid.uuid4().hex[:12]}"
        trigger = self._build_trigger(config)

        # 存储任务信息
        self._tasks[task_id] = {
            "id": task_id,
            "name": config.name,
            "description": config.description,
            "task_type": config.task_type.value,
            "status": LuomiTaskStatus.PENDING.value,
            "run_date": config.run_date,
            "cron_year": config.cron_year,
            "cron_month": config.cron_month,
            "cron_day": config.cron_day,
            "cron_week": config.cron_week,
            "cron_day_of_week": config.cron_day_of_week,
            "cron_hour": config.cron_hour,
            "cron_minute": config.cron_minute,
            "cron_second": config.cron_second,
            "interval_seconds": config.interval_seconds,
            "payload": config.payload,
            "source": config.source,
            "created_at": datetime.now().isoformat(),
            "last_run_time": None,
            "last_result": None,
            "last_error": None,
        }

        # 添加到调度器
        self._scheduler.add_job(
            self._execute_task,
            trigger=trigger,
            args=[task_id],
            id=task_id,
            replace_existing=True,
        )

        # 获取下次执行时间
        job = self._scheduler.get_job(task_id)
        if job and job.next_run_time:
            self._tasks[task_id]["next_run_time"] = job.next_run_time.isoformat()
        else:
            self._tasks[task_id]["next_run_time"] = None

        await self._persist_tasks()

        logger.info(
            f"[LuomiScheduler] 添加任务: id={task_id}, name={config.name}, "
            f"type={config.task_type.value}, next_run={self._tasks[task_id].get('next_run_time')}"
        )

        # 推送创建事件
        await self._emit_event(TaskEvent(
            task_id=task_id,
            task_name=config.name,
            status=LuomiTaskStatus.PENDING,
            task_type=config.task_type,
            message=f"任务已创建，下次执行: {self._tasks[task_id].get('next_run_time', '未知')}",
            payload=config.payload,
        ))

        return task_id

    async def _reschedule_task(self, task_id: str, config: ScheduledTaskConfig) -> None:
        """恢复持久化任务（不推送事件）"""
        trigger = self._build_trigger(config)
        self._tasks[task_id] = {
            "id": task_id,
            "name": config.name,
            "description": config.description,
            "task_type": config.task_type.value,
            "status": LuomiTaskStatus.PENDING.value,
            "run_date": config.run_date,
            "cron_year": config.cron_year,
            "cron_month": config.cron_month,
            "cron_day": config.cron_day,
            "cron_week": config.cron_week,
            "cron_day_of_week": config.cron_day_of_week,
            "cron_hour": config.cron_hour,
            "cron_minute": config.cron_minute,
            "cron_second": config.cron_second,
            "interval_seconds": config.interval_seconds,
            "payload": config.payload,
            "source": config.source,
            "created_at": datetime.now().isoformat(),
            "last_run_time": None,
            "last_result": None,
            "last_error": None,
        }
        self._scheduler.add_job(
            self._execute_task,
            trigger=trigger,
            args=[task_id],
            id=task_id,
            replace_existing=True,
        )
        job = self._scheduler.get_job(task_id)
        if job and job.next_run_time:
            self._tasks[task_id]["next_run_time"] = job.next_run_time.isoformat()

    async def _execute_task(self, task_id: str) -> None:
        """任务触发时的执行回调"""
        info = self._tasks.get(task_id)
        if not info:
            logger.warning(f"[LuomiScheduler] 任务 {task_id} 不存在，跳过执行")
            return

        info["status"] = LuomiTaskStatus.RUNNING.value
        info["last_run_time"] = datetime.now().isoformat()

        logger.info(f"[LuomiScheduler] 任务触发: id={task_id}, name={info.get('name')}")

        # 推送执行开始事件
        await self._emit_event(TaskEvent(
            task_id=task_id,
            task_name=info.get("name", ""),
            status=LuomiTaskStatus.RUNNING,
            task_type=LuomiTaskType(info.get("task_type", LuomiTaskType.DATE.value)),
            message="任务开始执行",
            payload=info.get("payload", {}),
        ))

        try:
            # 执行任务载荷中的指令
            payload = info.get("payload", {})
            result = await self._run_payload(task_id, payload)

            info["status"] = LuomiTaskStatus.COMPLETED.value
            info["last_result"] = result
            info["last_error"] = None

            logger.info(f"[LuomiScheduler] 任务完成: id={task_id}, result_len={len(result)}")

            await self._emit_event(TaskEvent(
                task_id=task_id,
                task_name=info.get("name", ""),
                status=LuomiTaskStatus.COMPLETED,
                task_type=LuomiTaskType(info.get("task_type", LuomiTaskType.DATE.value)),
                message="任务执行完成",
                result=result,
                payload=info.get("payload", {}),
            ))

        except Exception as e:
            info["status"] = LuomiTaskStatus.FAILED.value
            info["last_error"] = str(e)
            info["last_result"] = None

            logger.error(f"[LuomiScheduler] 任务失败: id={task_id}, error={e}", exc_info=True)

            await self._emit_event(TaskEvent(
                task_id=task_id,
                task_name=info.get("name", ""),
                status=LuomiTaskStatus.FAILED,
                task_type=LuomiTaskType(info.get("task_type", LuomiTaskType.DATE.value)),
                message="任务执行失败",
                error=str(e),
                payload=info.get("payload", {}),
            ))

        # date 类型任务执行后标记完成，不再重复
        if info.get("task_type") == LuomiTaskType.DATE.value:
            info["next_run_time"] = None

        await self._persist_tasks()

    async def _run_payload(self, task_id: str, payload: dict[str, Any]) -> str:
        """执行任务载荷

        当前实现：将载荷中的 instruction 通过子 Agent 执行。
        载荷格式：{"instruction": "执行xxx", "context": "附加上下文"}
        """
        instruction = payload.get("instruction", "").strip()
        if not instruction:
            return "任务载荷无 instruction 字段，跳过执行"

        # 通过子 Agent 执行指令（独立上下文，不污染主 Agent）
        try:
            from app.core.agents.subagent_executor import subagent_executor
            context = payload.get("context", "")
            result = await subagent_executor.execute(
                task=instruction,
                context=context,
                depth=0,
            )
            return result
        except Exception as e:
            logger.error(f"[LuomiScheduler] 子 Agent 执行失败: {e}", exc_info=True)
            return f"子 Agent 执行失败: {e}"

    async def remove_task(self, task_id: str) -> bool:
        """移除任务"""
        if task_id not in self._tasks:
            return False

        info = self._tasks[task_id]
        info["status"] = LuomiTaskStatus.REMOVED.value

        if self._scheduler:
            try:
                self._scheduler.remove_job(task_id)
            except Exception:
                pass

        logger.info(f"[LuomiScheduler] 移除任务: id={task_id}, name={info.get('name')}")

        await self._emit_event(TaskEvent(
            task_id=task_id,
            task_name=info.get("name", ""),
            status=LuomiTaskStatus.REMOVED,
            task_type=LuomiTaskType(info.get("task_type", LuomiTaskType.DATE.value)),
            message="任务已移除",
        ))

        del self._tasks[task_id]
        await self._persist_tasks()
        return True

    def list_tasks(self) -> list[ScheduledTaskInfo]:
        """列出所有任务"""
        result = []
        for task_id, info in self._tasks.items():
            result.append(ScheduledTaskInfo(
                id=task_id,
                name=info.get("name", ""),
                description=info.get("description", ""),
                task_type=LuomiTaskType(info.get("task_type", LuomiTaskType.DATE.value)),
                status=LuomiTaskStatus(info.get("status", LuomiTaskStatus.PENDING.value)),
                next_run_time=info.get("next_run_time"),
                last_run_time=info.get("last_run_time"),
                last_result=info.get("last_result"),
                last_error=info.get("last_error"),
                payload=info.get("payload", {}),
                source=info.get("source", "main_agent"),
                created_at=info.get("created_at", ""),
            ))
        return result

    def get_task(self, task_id: str) -> ScheduledTaskInfo | None:
        """获取单个任务信息"""
        info = self._tasks.get(task_id)
        if not info:
            return None
        return ScheduledTaskInfo(
            id=task_id,
            name=info.get("name", ""),
            description=info.get("description", ""),
            task_type=LuomiTaskType(info.get("task_type", LuomiTaskType.DATE.value)),
            status=LuomiTaskStatus(info.get("status", LuomiTaskStatus.PENDING.value)),
            next_run_time=info.get("next_run_time"),
            last_run_time=info.get("last_run_time"),
            last_result=info.get("last_result"),
            last_error=info.get("last_error"),
            payload=info.get("payload", {}),
            source=info.get("source", "main_agent"),
            created_at=info.get("created_at", ""),
        )


# 全局单例
luomi_scheduler = LuomiSchedulerManager()
