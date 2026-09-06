"""单工具域的内部工具处理函数（console.execute / subagent.delegate / context.compress）。

从原 register_tools.py 拆出（大文件拆分重构），处理函数体保持原样；
这三个工具各属独立小域（控制台、子 Agent、上下文压缩），集中在本模块承载；
注册顺序与 schema 见 register_tools.register_internal_tools。
"""

import json
from typing import Any

from loguru import logger

from app.core.workflow.models import WorkflowTaskResult
from app.core.workflow.tool_domains.common import _get_emitter, _wf_catch


@_wf_catch("context.compress")
async def _context_compress(args: dict[str, Any]) -> WorkflowTaskResult:
    """上下文压缩 handler（桥接 CompressContextTool）。

    对齐 tool-opt §4.3 T4：复用 ChatService.compress_conversation()，
    让工作流引擎也能触发上下文压缩。
    """
    from app.core.tools.registry import tool_registry

    tool = tool_registry.get("compress_context")
    if tool is None:
        return WorkflowTaskResult(success=False, error="compress_context 工具未注册")
    result = await tool.execute(args or {})
    return WorkflowTaskResult(
        success=result.success,
        output=result.output,
        error=result.error,
        metadata=result.metadata,
    )


async def _console_execute(args: dict[str, Any]) -> WorkflowTaskResult:
    """执行控制台命令"""
    command = args.get("command", "")
    if not command:
        return WorkflowTaskResult(success=False, error="Missing required parameter: command")

    try:
        from app.api.v1.endpoints.console import (
            _execute_command_via_sandbox,
            _get_console_sandbox,
        )

        # 获取沙盒实例（内置白名单验证）
        sandbox = _get_console_sandbox()

        # 执行命令（沙盒环境：白名单 + 超时 + 输出截断）
        timeout = min(args.get("timeout", 30), 120)
        exit_code, stdout, stderr = await _execute_command_via_sandbox(
            sandbox, command, timeout
        )

        success = exit_code == 0
        output = stdout if success else stderr or stdout

        # 推送工作流事件
        emitter = _get_emitter()
        if emitter:
            await emitter.emit_console_output(
                command=command,
                output=output,
                success=success,
            )

        if success:
            return WorkflowTaskResult(
                success=True,
                output=output,
                metadata={"exit_code": exit_code},
            )
        return WorkflowTaskResult(
            success=False,
            error=stderr or f"命令执行失败 (exit_code={exit_code})",
        )
    except Exception as e:
        logger.error("[Workflow:console.execute] Failed: {}", str(e), exc_info=True)
        return WorkflowTaskResult(success=False, error=str(e))


async def _subagent_delegate(args: dict[str, Any]) -> WorkflowTaskResult:
    """委派任务给子 Agent"""
    task = args.get("task", "")
    context = args.get("context", "")

    if not task:
        return WorkflowTaskResult(success=False, error="Missing required parameter: task")

    try:
        from app.core.agents.subagent_executor import subagent_executor
        from app.core.tools.builtin.subagent_tool import get_subagent_event_callback

        # 读取当前异步上下文的事件回调，与 DelegateToSubagentTool 行为一致
        # 使 workflow 路径触发的子 Agent 委派也能推送 subagent_event 到 SSE 流
        event_callback = get_subagent_event_callback()

        result = await subagent_executor.execute(
            task=task,
            context=context,
            depth=0,
            event_callback=event_callback,
        )
        return WorkflowTaskResult(
            success=True,
            output=result,
            metadata={"task": task},
        )
    except Exception as e:
        logger.error("[Workflow:subagent.delegate] Failed: {}", str(e), exc_info=True)
        return WorkflowTaskResult(success=False, error=str(e))
