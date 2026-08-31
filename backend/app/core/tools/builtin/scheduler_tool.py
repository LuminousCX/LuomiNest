"""LuomiNest 定时任务创建工具。

主 Agent 通过本工具创建定时任务，实现"明天8点总结报告"等场景。

支持三种任务类型：
1. date - 一次性定时任务（如"明天上午8点执行"）
2. cron - cron 表达式任务（如"每天0点执行"）
3. interval - 间隔执行任务（如"每30分钟执行一次"）

任务触发时，后端通过子 Agent 执行载荷中的指令，并通过 SSE 推送 task_event 到前端。
"""
from typing import Any

from loguru import logger

from app.core.scheduler.models import LuomiTaskType, ScheduledTaskConfig
from app.core.tools.registry import ToolBase, ToolResult


class CreateScheduledTaskTool(ToolBase):
    """定时任务创建工具"""

    @property
    def name(self) -> str:
        return "create_scheduled_task"

    @property
    def description(self) -> str:
        return (
            "创建定时任务，在指定时间自动执行指令。支持三种类型：\n"
            "1. date（一次性）：在指定时间执行一次，需提供 run_date（ISO 格式，如 '2026-06-21T08:00:00'）\n"
            "2. cron（周期性）：按 cron 表达式周期执行，需提供 cron 字段（cron_hour/cron_minute 等）\n"
            "3. interval（间隔）：按固定间隔重复执行，需提供 interval_seconds\n"
            "任务触发时，后端会通过子 Agent 执行 instruction 中的指令。"
            "适用于：定时总结报告、定时提醒、周期性数据采集等场景。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "任务名称（简短描述，如'每日新闻总结'）",
                },
                "instruction": {
                    "type": "string",
                    "description": "任务触发时要执行的指令（将交给子 Agent 执行）",
                },
                "task_type": {
                    "type": "string",
                    "enum": ["date", "cron", "interval"],
                    "description": "任务类型：date=一次性定时，cron=cron表达式，interval=间隔执行",
                },
                "run_date": {
                    "type": "string",
                    "description": "date 类型必填。ISO 格式时间字符串，如 '2026-06-21T08:00:00'",
                },
                "cron_hour": {
                    "type": "string",
                    "description": "cron 类型：小时（0-23 或 *）。如 '8' 表示每小时8点",
                },
                "cron_minute": {
                    "type": "string",
                    "description": "cron 类型：分钟（0-59 或 *）。如 '0' 表示整点",
                },
                "cron_day_of_week": {
                    "type": "string",
                    "description": "cron 类型：星期（0-6 或 mon-sun 或 *）。如 'mon-fri' 表示工作日",
                },
                "interval_seconds": {
                    "type": "integer",
                    "description": "interval 类型必填。间隔秒数，如 1800 表示30分钟",
                },
                "description": {
                    "type": "string",
                    "description": "任务详细描述（可选）",
                },
                "context": {
                    "type": "string",
                    "description": "附加上下文信息（可选），传递给子 Agent",
                },
            },
            "required": ["name", "instruction", "task_type"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        name = arguments.get("name", "").strip()
        instruction = arguments.get("instruction", "").strip()
        task_type_str = arguments.get("task_type", "").strip()

        if not name:
            return ToolResult.fail("缺少 name 参数")
        if not instruction:
            return ToolResult.fail("缺少 instruction 参数")
        if not task_type_str:
            return ToolResult.fail("缺少 task_type 参数")

        try:
            task_type = LuomiTaskType(task_type_str)
        except ValueError:
            return ToolResult.fail(f"不支持的 task_type: {task_type_str}，可选: date/cron/interval")

        # 构建配置
        config = ScheduledTaskConfig(
            name=name,
            description=arguments.get("description", ""),
            task_type=task_type,
            run_date=arguments.get("run_date"),
            cron_year=arguments.get("cron_year"),
            cron_month=arguments.get("cron_month"),
            cron_day=arguments.get("cron_day"),
            cron_week=arguments.get("cron_week"),
            cron_day_of_week=arguments.get("cron_day_of_week"),
            cron_hour=arguments.get("cron_hour"),
            cron_minute=arguments.get("cron_minute"),
            cron_second=arguments.get("cron_second"),
            interval_seconds=arguments.get("interval_seconds"),
            payload={
                "instruction": instruction,
                "context": arguments.get("context", ""),
            },
            source="main_agent",
        )

        # 通过任务调度端口调用（组合根可覆盖实现；端口兜底延迟导入调度器单例）
        try:
            from app.core.ports.task_scheduling import get_scheduler
        except Exception as e:
            logger.error(f"[CreateScheduledTaskTool] 导入调度端口失败: {e}")
            return ToolResult.fail(f"调度器不可用: {e}")

        scheduler = get_scheduler()
        if not scheduler.is_running:
            return ToolResult.fail("调度器未启动，无法创建任务")

        try:
            task_id = await scheduler.add_task(config)
            task_info = scheduler.get_task(task_id)

            next_run = task_info.next_run_time if task_info else "未知"
            logger.info(
                f"[CreateScheduledTaskTool] 任务已创建: id={task_id}, name={name}, "
                f"type={task_type.value}, next_run={next_run}"
            )

            # 通过 contextvars 回调推送 task_event 到 SSE 流
            from app.core.tools.builtin.subagent_tool import _subagent_event_callback_var

            callback = _subagent_event_callback_var.get()
            if callback is not None:
                try:
                    await callback({
                        "task_id": task_id,
                        "task_name": name,
                        "status": "pending",
                        "task_type": task_type.value,
                        "message": f"定时任务已创建，下次执行: {next_run}",
                        "payload": config.payload,
                    })
                except Exception as e:
                    logger.warning(f"[CreateScheduledTaskTool] 事件回调失败: {e}")

            return ToolResult.ok(
                f"定时任务已创建\n"
                f"任务ID: {task_id}\n"
                f"任务名称: {name}\n"
                f"任务类型: {task_type.value}\n"
                f"下次执行: {next_run}\n"
                f"执行指令: {instruction}",
                metadata={"task_id": task_id, "next_run_time": next_run},
            )
        except ValueError as e:
            return ToolResult.fail(f"任务参数错误: {e}")
        except Exception as e:
            logger.error(f"[CreateScheduledTaskTool] 创建任务异常: {e}", exc_info=True)
            return ToolResult.fail(f"创建定时任务失败: {e}")


class ListScheduledTasksTool(ToolBase):
    """列出所有定时任务"""

    @property
    def name(self) -> str:
        return "list_scheduled_tasks"

    @property
    def description(self) -> str:
        return "列出所有已创建的定时任务，返回任务 ID、名称、类型、下次执行时间等信息。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        try:
            from app.core.ports.task_scheduling import get_scheduler
        except Exception as e:
            return ToolResult.fail(f"调度器不可用: {e}")

        scheduler = get_scheduler()
        if not scheduler.is_running:
            return ToolResult.fail("调度器未启动")

        tasks = scheduler.list_tasks()
        task_list = [t.model_dump() for t in tasks]
        return ToolResult.ok(
            f"共 {len(task_list)} 个定时任务",
            metadata={"count": len(task_list), "tasks": task_list},
        )


class GetScheduledTaskTool(ToolBase):
    """获取单个定时任务详情"""

    @property
    def name(self) -> str:
        return "get_scheduled_task"

    @property
    def description(self) -> str:
        return "根据任务 ID 获取单个定时任务的详细信息。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "任务 ID",
                },
            },
            "required": ["task_id"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        task_id = arguments.get("task_id", "").strip()
        if not task_id:
            return ToolResult.fail("缺少 task_id 参数")

        try:
            from app.core.ports.task_scheduling import get_scheduler
        except Exception as e:
            return ToolResult.fail(f"调度器不可用: {e}")

        task = get_scheduler().get_task(task_id)
        if not task:
            return ToolResult.fail(f"任务 {task_id} 不存在")

        return ToolResult.ok(
            f"任务详情: {task.name}",
            metadata={"task": task.model_dump()},
        )


class DeleteScheduledTaskTool(ToolBase):
    """删除定时任务"""

    @property
    def name(self) -> str:
        return "delete_scheduled_task"

    @property
    def description(self) -> str:
        return "根据任务 ID 删除指定的定时任务。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "要删除的任务 ID",
                },
            },
            "required": ["task_id"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        task_id = arguments.get("task_id", "").strip()
        if not task_id:
            return ToolResult.fail("缺少 task_id 参数")

        try:
            from app.core.ports.task_scheduling import get_scheduler
        except Exception as e:
            return ToolResult.fail(f"调度器不可用: {e}")

        success = await get_scheduler().remove_task(task_id)
        if not success:
            return ToolResult.fail(f"任务 {task_id} 不存在或删除失败")

        return ToolResult.ok(
            f"已删除定时任务: {task_id}",
            metadata={"task_id": task_id},
        )
