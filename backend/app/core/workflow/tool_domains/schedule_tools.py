"""定时任务模块的内部工具处理函数（schedule.*）。

从原 register_tools.py 拆出（大文件拆分重构），处理函数体保持原样；
注册顺序与 schema 见 register_tools.register_internal_tools。
"""

import json
from typing import Any

from loguru import logger

from app.core.workflow.models import WorkflowTaskResult
from app.core.workflow.tool_domains.common import _get_emitter


async def _schedule_create(args: dict[str, Any]) -> WorkflowTaskResult:
    """创建定时任务"""
    name = args.get("name", "")
    schedule = args.get("schedule", "")
    action = args.get("action", "")
    description = args.get("description", "")
    context = args.get("context", "")

    if not name or not schedule or not action:
        return WorkflowTaskResult(
            success=False,
            error="Missing required parameters: name, schedule, action",
        )

    try:
        from app.core.tools.builtin.scheduler_tool import CreateScheduledTaskTool

        tool = CreateScheduledTaskTool()
        result = await tool.execute(
            name=name,
            schedule=schedule,
            action=action,
            description=description,
            context=context,
        )

        if result.success:
            # 推送工作流事件
            emitter = _get_emitter()
            if emitter:
                task_id = result.metadata.get("task_id", "")
                await emitter.emit_schedule_created(
                    task_id=task_id,
                    name=name,
                    schedule=schedule,
                    action=action,
                )

            return WorkflowTaskResult(
                success=True,
                output=result.output,
                metadata=result.metadata,
            )
        return WorkflowTaskResult(success=False, error=result.error)
    except Exception as e:
        logger.error("[Workflow:schedule.create] Failed: {}", str(e), exc_info=True)
        return WorkflowTaskResult(success=False, error=str(e))


async def _schedule_list(args: dict[str, Any]) -> WorkflowTaskResult:
    """列出所有定时任务"""
    try:
        from app.core.scheduler import luominest_scheduler

        tasks = luominest_scheduler.list_tasks()
        task_list = [t.model_dump() for t in tasks]

        emitter = _get_emitter()
        if emitter:
            await emitter.emit_module_action(
                module="schedule",
                action="list",
                success=True,
                output=f"共 {len(task_list)} 个定时任务",
                metadata={"count": len(task_list)},
            )

        return WorkflowTaskResult(
            success=True,
            output=json.dumps(task_list, ensure_ascii=False),
            metadata={"count": len(task_list)},
        )
    except Exception as e:
        logger.error("[Workflow:schedule.list] Failed: {}", str(e), exc_info=True)
        return WorkflowTaskResult(success=False, error=str(e))


async def _schedule_get(args: dict[str, Any]) -> WorkflowTaskResult:
    """获取单个定时任务详情"""
    task_id = args.get("task_id", "")
    if not task_id:
        return WorkflowTaskResult(success=False, error="Missing required parameter: task_id")

    try:
        from app.core.scheduler import luominest_scheduler

        task = luominest_scheduler.get_task(task_id)
        if not task:
            return WorkflowTaskResult(success=False, error=f"任务 {task_id} 不存在")

        return WorkflowTaskResult(
            success=True,
            output=json.dumps(task.model_dump(), ensure_ascii=False),
            metadata={"task_id": task_id},
        )
    except Exception as e:
        logger.error("[Workflow:schedule.get] Failed: {}", str(e), exc_info=True)
        return WorkflowTaskResult(success=False, error=str(e))


async def _schedule_delete(args: dict[str, Any]) -> WorkflowTaskResult:
    """删除定时任务"""
    task_id = args.get("task_id", "")
    if not task_id:
        return WorkflowTaskResult(success=False, error="Missing required parameter: task_id")

    try:
        from app.core.scheduler import luominest_scheduler

        success = await luominest_scheduler.remove_task(task_id)
        if not success:
            return WorkflowTaskResult(success=False, error=f"任务 {task_id} 不存在")

        emitter = _get_emitter()
        if emitter:
            await emitter.emit_module_action(
                module="schedule",
                action="deleted",
                success=True,
                output=f"已删除任务 {task_id}",
                metadata={"task_id": task_id},
            )

        return WorkflowTaskResult(
            success=True,
            output=f"已删除定时任务: {task_id}",
            metadata={"task_id": task_id},
        )
    except Exception as e:
        logger.error("[Workflow:schedule.delete] Failed: {}", str(e), exc_info=True)
        return WorkflowTaskResult(success=False, error=str(e))
