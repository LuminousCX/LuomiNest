"""工作流事件推送器

统一管理工作流引擎执行过程中的事件推送。
所有内部工具执行后，通过此模块推送结构化事件到前端。

事件类型：
- module_action: 内部模块操作事件（浏览器导航、计划创建、记忆存储等）
  前端根据 module 字段路由到对应页面

参考：
- deer-flow: StreamBridge 流式解耦
- claude-code: 邮箱系统结构化事件
"""
import asyncio
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from app.core.utils import utc_now


class WorkflowEventEmitter:
    """工作流事件推送器

    收集工作流执行过程中的所有事件，供 SSE 端点推送到前端。
    每个 WorkflowSession 创建一个 emitter 实例。
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self._queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

    async def emit(self, event_type: str, data: dict[str, Any]) -> None:
        """推送事件到队列"""
        event = {
            "type": event_type,
            "data": data,
            "session_id": self.session_id,
            "timestamp": utc_now(),
        }
        await self._queue.put(event)
        logger.debug(f"[WorkflowEmitter] {event_type}: {data.get('module', '')}")

    async def emit_module_action(
        self,
        module: str,
        action: str,
        success: bool,
        output: str = "",
        error: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """推送内部模块操作事件

        Args:
            module: 模块名（browser, schedule, memory, console, smart_home 等）
            action: 操作名（navigate, create, store, recall 等）
            success: 是否成功
            output: 输出信息
            error: 错误信息
            metadata: 附加元数据（如 tab_id, task_id, memory_id 等）
        """
        await self.emit("module_action", {
            "module": module,
            "action": action,
            "success": success,
            "output": output,
            "error": error,
            "metadata": metadata or {},
        })

    async def emit_browser_action(
        self,
        action: str,
        url: str = "",
        title: str = "",
        tab_id: str = "",
        purpose: str = "",
    ) -> None:
        """推送浏览器操作事件（兼容现有 subagent_event 通道格式）"""
        await self.emit("module_action", {
            "module": "browser",
            "action": action,
            "success": True,
            "url": url,
            "title": title,
            "tab_id": tab_id,
            "purpose": purpose,
            "metadata": {"tab_id": tab_id, "url": url},
        })

    async def emit_schedule_created(
        self,
        task_id: str,
        name: str,
        schedule: str,
        action: str,
    ) -> None:
        """推送计划任务创建事件"""
        await self.emit("module_action", {
            "module": "schedule",
            "action": "created",
            "success": True,
            "task_id": task_id,
            "name": name,
            "schedule": schedule,
            "task_action": action,
            "metadata": {"task_id": task_id},
        })

    async def emit_memory_stored(
        self,
        memory_id: str,
        content: str,
        category: str,
    ) -> None:
        """推送记忆存储事件"""
        await self.emit("module_action", {
            "module": "memory",
            "action": "stored",
            "success": True,
            "memory_id": memory_id,
            "content_preview": content[:200] if content else "",
            "category": category,
            "metadata": {"memory_id": memory_id, "category": category},
        })

    async def emit_memory_recalled(
        self,
        query: str,
        results_count: int,
        results: Any = None,
    ) -> None:
        """推送记忆检索事件"""
        await self.emit("module_action", {
            "module": "memory",
            "action": "recalled",
            "success": True,
            "query": query,
            "results_count": results_count,
            "metadata": {"query": query, "count": results_count},
        })

    async def emit_console_output(
        self,
        command: str,
        output: str,
        success: bool,
    ) -> None:
        """推送控制台命令输出事件"""
        await self.emit("module_action", {
            "module": "console",
            "action": "executed",
            "success": success,
            "command": command,
            "output": output[:500] if output else "",
            "metadata": {"command": command},
        })

    async def finish(self) -> None:
        """标记事件流结束"""
        await self._queue.put(None)

    async def stream(self):
        """异步迭代器：逐个 yield 事件"""
        while True:
            event = await self._queue.get()
            if event is None:
                break
            yield event
