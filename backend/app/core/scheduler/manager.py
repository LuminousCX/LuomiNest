"""LuomiNest 定时任务调度器管理器。

基于 APScheduler AsyncIOScheduler 实现，支持：
1. 一次性定时任务（date）
2. cron 表达式任务
3. 间隔执行任务（interval）

任务执行时通过事件回调通知前端（SSE）和主 Agent。
配置持久化到 scheduled_tasks 数据库表。
"""
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
from app.core.utils import utc_now
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
        self._started = False
        # 任务载荷执行器（SubagentExecutor 兼容对象）：由组合根注入，None 时走端口兜底
        self._task_executor: Any | None = None

    @property
    def is_running(self) -> bool:
        return self._started and self._scheduler is not None and self._scheduler.running

    def register_task_executor(self, executor: Any | None) -> None:
        """注入任务载荷执行器（由组合根在 lifespan 中调用）。

        Args:
            executor: SubagentExecutor 兼容对象（需有 async execute(task=..., context=..., depth=...)）；
                传 None 恢复兜底行为（经 subagent_delegation 端口延迟导入模块单例）。
        """
        self._task_executor = executor

    def add_event_callback(self, callback: TaskEventCallback) -> None:
        """注册任务事件回调（用于 SSE 推送、结果投递等）"""
        self._event_callbacks.append(callback)

    async def _emit_event(self, event: TaskEvent) -> None:
        """安全推送任务事件到所有回调"""
        for cb in self._event_callbacks:
            try:
                await cb(event)
            except Exception as e:
                logger.warning(f"[LuomiScheduler] 事件回调失败: {e}")

    async def emit_task_event(self, event: TaskEvent) -> None:
        """对外发布任务事件（供结果投递器等外部组件广播降级/补充通知）。"""
        await self._emit_event(event)

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

    def add_job(
        self,
        func: Callable[..., Any],
        trigger: Any,
        id: str,
        replace_existing: bool = True,
        **kwargs: Any,
    ) -> bool:
        """添加内部维护任务（非用户 scheduled_task），如周期清理。

        供 app_factory 等外部模块调用，避免直接访问 _scheduler 私有属性。
        返回 True 表示添加成功，False 表示调度器未运行。
        """
        if not self._scheduler or not self._scheduler.running:
            logger.warning(f"[LuomiScheduler] add_job skipped (scheduler not running): id={id}")
            return False
        self._scheduler.add_job(func, trigger=trigger, id=id, replace_existing=replace_existing, **kwargs)
        logger.info(f"[LuomiScheduler] Internal job added: id={id}")
        return True

    async def _load_persisted_tasks(self) -> None:
        """从数据库加载持久化任务，DB 失败或为空时 fallback 到 JSON 文件。"""
        count = 0

        # 优先从 DB 加载
        try:
            from app.services.scheduled_task_persistence import list_scheduled_tasks

            db_tasks = await list_scheduled_tasks()
            if db_tasks:
                for t in db_tasks:
                    if not t.get("is_active", False):
                        continue
                    task_id = t.get("task_id", "")
                    if not task_id:
                        continue
                    try:
                        config = self._db_task_to_config(t)
                        await self._reschedule_task(task_id, config)
                        count += 1
                    except Exception as e:
                        logger.warning(f"[LuomiScheduler] 从 DB 恢复任务 {task_id} 失败: {e}")
                logger.info(f"[LuomiScheduler] 从 DB 恢复 {count} 个持久化任务")
                return
        except Exception as e:
            logger.warning(f"[LuomiScheduler] 从 DB 加载任务失败，尝试 JSON fallback: {e}")

        # Fallback: 从 JSON 文件加载（兼容首次启动或 DB 为空）
        config_file = Path(settings.DATA_DIR) / "scheduled_tasks.json"
        if not config_file.exists():
            return
        try:
            data = json.loads(config_file.read_text(encoding="utf-8"))
            for task_data in data.get("tasks", []):
                task_id = task_data.get("id", "")
                if not task_id:
                    continue
                if task_data.get("status") in (LuomiTaskStatus.COMPLETED.value, LuomiTaskStatus.REMOVED.value):
                    continue
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
                    logger.warning(f"[LuomiScheduler] 从 JSON 恢复任务 {task_id} 失败: {e}")
            logger.info(f"[LuomiScheduler] 从 JSON fallback 恢复 {count} 个持久化任务")
        except Exception as e:
            logger.warning(f"[LuomiScheduler] 加载 JSON 持久化任务失败: {e}")

    @staticmethod
    def _db_task_to_config(t: dict[str, Any]) -> ScheduledTaskConfig:
        """将 DB 记录转换为 ScheduledTaskConfig。

        调度类型以 trigger_type（date/cron/interval）为权威；旧数据（trigger_type 为空）
        按遗留 schedule_type 兜底映射（once/date → date）。恢复失败抛 ValueError，
        由 _load_persisted_tasks 逐任务捕获并告警，保证问题可见。
        """
        trigger_type = (t.get("trigger_type") or "").strip().lower()
        if not trigger_type:
            legacy = (t.get("schedule_type") or "").strip().lower()
            trigger_type = {"date": "date", "once": "date", "cron": "cron", "interval": "interval"}.get(legacy, "")
        schedule_cron = t.get("schedule_cron", "") or ""
        action = t.get("action", "")
        context = t.get("context", "")
        payload: dict[str, Any] = {}
        if action:
            payload["instruction"] = action
        if context:
            payload["context"] = context

        task_type = LuomiTaskType.DATE
        run_date = None
        cron_year = cron_month = cron_day = cron_week = None
        cron_day_of_week = cron_hour = cron_minute = cron_second = None
        interval_seconds = None

        if trigger_type == LuomiTaskType.CRON.value:
            task_type = LuomiTaskType.CRON
            parts = schedule_cron.split()
            if len(parts) >= 5:
                cron_minute, cron_hour, cron_day, cron_month, cron_day_of_week = parts[:5]
            else:
                raise ValueError(f"cron 表达式字段不足: '{schedule_cron}'")
        elif trigger_type == LuomiTaskType.INTERVAL.value:
            task_type = LuomiTaskType.INTERVAL
            interval_seconds = t.get("interval_seconds")
            if not interval_seconds or int(interval_seconds) <= 0:
                # 旧实现未存 interval_seconds；显式告警后降级 3600s，不再静默
                logger.warning(
                    f"[LuomiScheduler] interval 任务 {t.get('task_id', '?')} 缺少 interval_seconds，降级为 3600s"
                )
                interval_seconds = 3600
            else:
                interval_seconds = int(interval_seconds)
        else:
            # date 类型：从 run_at 列恢复 ISO 执行时间；旧实现的幻象 cron "* * * * *"
            # 不再被当作执行时间（无法恢复时显式告警跳过，而非 datetime 解析崩溃）
            run_date = (t.get("run_at") or "").strip() or None
            if not run_date:
                raise ValueError("date 类型任务缺少 run_at，无法从 DB 恢复")

        return ScheduledTaskConfig(
            name=t.get("name", ""),
            description=t.get("description", "") or "",
            task_type=task_type,
            run_date=run_date,
            cron_year=cron_year,
            cron_month=cron_month,
            cron_day=cron_day,
            cron_week=cron_week,
            cron_day_of_week=cron_day_of_week,
            cron_hour=cron_hour,
            cron_minute=cron_minute,
            cron_second=cron_second,
            interval_seconds=interval_seconds,
            payload=payload,
            source=t.get("created_from", "main_agent"),
            origin_kind=t.get("origin_kind") or "",
            origin_ref=t.get("origin_ref") or "",
            origin_target=t.get("origin_target") or "",
        )

    @staticmethod
    def _task_info_to_db_fields(info: dict[str, Any]) -> dict[str, Any]:
        """将内存任务信息映射为持久化行字段（按 task_type 分支，消除幻象 cron）。

        - date：run_at 存 ISO 执行时间，schedule_cron 置空（旧实现误存 "* * * * *"）
        - cron：schedule_cron 存五段 cron 表达式
        - interval：interval_seconds 存间隔秒数，schedule_cron 置空
        """
        task_type = info.get("task_type", LuomiTaskType.DATE.value)
        schedule_cron = ""
        run_at = None
        interval_seconds = None
        if task_type == LuomiTaskType.CRON.value:
            schedule_cron = " ".join([
                info.get("cron_minute") or "*",
                info.get("cron_hour") or "*",
                info.get("cron_day") or "*",
                info.get("cron_month") or "*",
                info.get("cron_day_of_week") or "*",
            ])
        elif task_type == LuomiTaskType.INTERVAL.value:
            interval_seconds = info.get("interval_seconds")
        else:  # date
            run_at = info.get("run_date") or None
        payload = info.get("payload") or {}
        is_active = info.get("status") not in (
            LuomiTaskStatus.COMPLETED.value,
            LuomiTaskStatus.REMOVED.value,
        )
        return {
            "schedule_cron": schedule_cron,
            "schedule_type": task_type,
            "trigger_type": task_type,
            "run_at": run_at,
            "interval_seconds": interval_seconds,
            "action": payload.get("instruction", "") if payload else "",
            "context": payload.get("context", "") if payload else "",
            "is_active": is_active,
            "origin_kind": info.get("origin_kind") or "api",
            "origin_ref": info.get("origin_ref") or None,
            "origin_target": info.get("origin_target") or None,
        }

    async def _persist_tasks(self) -> None:
        """将内存中的任务状态同步到数据库（不再写入 JSON 文件）。"""
        try:
            from app.services.scheduled_task_persistence import save_scheduled_task

            # await 期间 add_task/remove_task 可能增删 _tasks，
            # 先快照再迭代，防 "dictionary changed size during iteration"
            items = list(self._tasks.items())
            for task_id, info in items:
                fields = self._task_info_to_db_fields(info)
                await save_scheduled_task(
                    task_id=task_id,
                    name=info.get("name", ""),
                    description=info.get("description", ""),
                    created_from=info.get("source", "main_agent"),
                    **fields,
                )
        except Exception as e:
            logger.warning(f"[LuomiScheduler] 同步任务到 DB 失败: {e}")

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
            "origin_kind": config.origin_kind,
            "origin_ref": config.origin_ref,
            "origin_target": config.origin_target,
            "created_at": utc_now(),
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
            "origin_kind": config.origin_kind,
            "origin_ref": config.origin_ref,
            "origin_target": config.origin_target,
            "created_at": utc_now(),
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
        info["last_run_time"] = utc_now()

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
        # 执行器优先使用组合根注入的实例；未注入时经 subagent_delegation 端口兜底
        # （端口内部延迟导入 subagent_executor 模块单例），行为保持一致
        try:
            context = payload.get("context", "")
            if self._task_executor is not None:
                result = await self._task_executor.execute(
                    task=instruction,
                    context=context,
                    depth=0,
                )
            else:
                from app.core.ports.subagent_delegation import delegate_task
                result = await delegate_task(instruction, context=context, depth=0)
            return result
        except Exception as e:
            # fail-fast（P0-1）：执行失败上抛，由 _execute_task 记入 FAILED 状态、
            # last_error 与 FAILED 事件（原先吞成结果字符串会让任务假性"完成"）
            logger.error(f"[LuomiScheduler] 子 Agent 执行失败: {e}", exc_info=True)
            raise

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
                # job 可能已执行完毕（一次性任务），属预期情况
                logger.debug(f"[LuomiScheduler] remove_job 未找到已结束的 job: id={task_id}", exc_info=True)

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

        # 同步从数据库删除
        try:
            from app.services.scheduled_task_persistence import delete_scheduled_task
            await delete_scheduled_task(task_id)
        except Exception as e:
            logger.warning(f"[LuomiScheduler] DB 删除任务失败: {e}")

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
                origin_kind=info.get("origin_kind") or "api",
                origin_ref=info.get("origin_ref") or "",
                origin_target=info.get("origin_target") or "",
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
            origin_kind=info.get("origin_kind") or "api",
            origin_ref=info.get("origin_ref") or "",
            origin_target=info.get("origin_target") or "",
            created_at=info.get("created_at", ""),
        )


# 全局单例
luominest_scheduler = LuomiSchedulerManager()
