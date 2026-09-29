"""定时任务结果投递器（P0-1 定时任务闭环）。

任务触发执行完毕后，把执行结果投递回任务创建时记录的来源：
- web_conversation：结果作为一条带 ``[定时任务]《任务名》`` 前缀的 assistant 消息
  追加进该网页会话（受配置开关 SCHEDULER_RESULT_INTO_CHAT 控制）；
- platform：经 platform_router 的发送链路投递到 ``group:{id}`` / ``private:{id}``，
  实例离线时沿用适配器内置发送队列重试，最终失败降级为任务事件通知（结果仍保留在
  任务记录 last_result，前端任务面板轮询可见，不丢结果）；
- api / 未知来源：无会话目标，结果仅保留在任务记录。

接入方式：组合根（app_factory）把本模块单例注册为调度器的事件回调，
仅消费 COMPLETED / FAILED 事件；任务创建、开始执行等状态由前端任务面板轮询覆盖。
"""
import uuid

from loguru import logger

from app.core.config import settings
from app.core.scheduler.models import (
    ORIGIN_API,
    ORIGIN_PLATFORM,
    ORIGIN_WEB_CONVERSATION,
    LuomiTaskStatus,
    ScheduledTaskInfo,
    TaskEvent,
)

# config_items 中平台会话映射的键前缀（与 runtime/platform/session.py 一致）
_PLATFORM_SESSIONS_KEY_PREFIX = "platform.sessions."


class TaskResultDispatcher:
    """任务执行结果投递器：按任务来源把结果送回网页会话或平台目标。"""

    async def handle_task_event(self, event: TaskEvent) -> None:
        """调度器事件回调入口：仅消费任务完成/失败事件并投递结果。"""
        if event.status not in (LuomiTaskStatus.COMPLETED, LuomiTaskStatus.FAILED):
            return

        origin = self._resolve_origin(event.task_id)
        if origin is None:
            logger.debug(
                f"[TaskResultDispatcher] 任务 {event.task_id} 无来源信息，结果保留在任务记录"
            )
            return

        content = self._build_message_content(event)
        origin_kind = origin.get("origin_kind") or ORIGIN_API

        try:
            if origin_kind == ORIGIN_WEB_CONVERSATION:
                await self._deliver_to_conversation(origin, content, event)
            elif origin_kind == ORIGIN_PLATFORM:
                await self._deliver_to_platform(origin, content, event)
            else:
                # api / 未知来源：无会话可回投，结果保留在任务记录（前端任务面板可见）
                logger.debug(
                    f"[TaskResultDispatcher] 任务 {event.task_id} 来源为 {origin_kind}，不回投会话"
                )
        except Exception as e:
            # 投递失败不允许中断调度器事件链；结果仍在任务记录中可查
            logger.warning(
                f"[TaskResultDispatcher] 任务 {event.task_id} 结果投递异常: {e}",
                exc_info=True,
            )

    # ── 来源解析 ──

    def _resolve_origin(self, task_id: str) -> dict | None:
        """从调度器内存任务读取投递来源；任务不存在返回 None。

        来源随任务持久化（scheduled_tasks.origin_* 三列），重启恢复后仍可投递。
        """
        try:
            from app.core.scheduler.manager import luominest_scheduler

            task: ScheduledTaskInfo | None = luominest_scheduler.get_task(task_id)
        except Exception as e:
            logger.warning(f"[TaskResultDispatcher] 读取任务 {task_id} 来源失败: {e}")
            return None
        if task is None:
            return None
        return {
            "origin_kind": task.origin_kind,
            "origin_ref": task.origin_ref or "",
            "origin_target": task.origin_target or "",
        }

    @staticmethod
    def _build_message_content(event: TaskEvent) -> str:
        """构建投递消息文本（统一带 ``[定时任务]《任务名》`` 前缀）。"""
        if event.status == LuomiTaskStatus.FAILED:
            return f"[定时任务]《{event.task_name}》执行失败：{event.error or '未知错误'}"
        body = (event.result or "").strip() or "（任务无返回内容）"
        return f"[定时任务]《{event.task_name}》执行完成：\n{body}"

    # ── 网页会话投递 ──

    async def _deliver_to_conversation(self, origin: dict, content: str, event: TaskEvent) -> None:
        """web 来源：结果作为 assistant 消息追加进原会话（开关可关）。"""
        if not settings.SCHEDULER_RESULT_INTO_CHAT:
            logger.debug(
                f"[TaskResultDispatcher] SCHEDULER_RESULT_INTO_CHAT 已关闭，"
                f"任务 {event.task_id} 结果不写入会话"
            )
            return

        conv_id = origin.get("origin_ref") or ""
        if not conv_id:
            logger.warning(
                f"[TaskResultDispatcher] 任务 {event.task_id} 缺少会话 ID，结果保留在任务记录"
            )
            return

        from app.infrastructure.database.conversation_store import conversation_store

        message = {
            "role": "assistant",
            "content": content,
            "id": str(uuid.uuid4()),
            "model": "scheduled-task",
            "scheduled_task": {
                "task_id": event.task_id,
                "status": event.status.value,
            },
        }
        appended = await conversation_store.append_message_async(conv_id, message)
        if appended:
            logger.info(
                f"[TaskResultDispatcher] 任务 {event.task_id} 结果已写入会话 {conv_id}"
            )
        else:
            # 会话可能已删除：结果仍保留在任务记录，前端任务面板可见
            logger.warning(
                f"[TaskResultDispatcher] 会话 {conv_id} 不存在，"
                f"任务 {event.task_id} 结果保留在任务记录"
            )

    # ── 平台投递 ──

    async def _deliver_to_platform(self, origin: dict, content: str, event: TaskEvent) -> None:
        """platform 来源：经 platform_router 发送链路投递，失败降级为任务事件通知。"""
        origin_ref = origin.get("origin_ref") or ""
        if ":" not in origin_ref:
            logger.warning(
                f"[TaskResultDispatcher] 任务 {event.task_id} 平台来源引用非法: "
                f"'{origin_ref}'（应为 instance_id:session_id），结果保留在任务记录"
            )
            return
        instance_id, session_id = origin_ref.split(":", 1)

        target = self._resolve_platform_target(
            instance_id, session_id, origin.get("origin_target") or ""
        )

        sent = await self._send_via_platform(instance_id, target, content)
        if sent:
            logger.info(
                f"[TaskResultDispatcher] 任务 {event.task_id} 结果已投递到 "
                f"实例 {instance_id} 目标 {target}"
            )
            return

        # 发送失败（实例离线且队列不可用等）：降级为任务事件通知，结果保留在任务记录
        logger.warning(
            f"[TaskResultDispatcher] 任务 {event.task_id} 投递到实例 {instance_id} "
            f"目标 {target} 失败，降级为任务事件通知"
        )
        await self._emit_delivery_failure_event(event, instance_id, target)

    @staticmethod
    async def _send_via_platform(instance_id: str, target: str, content: str) -> bool:
        """经 platform_router 发送链路投递（独立小方法，便于测试替身替换）。

        实例离线时由适配器内部 _enqueue_message 走现有重试队列，此处返回 False
        仅表示"当前未送达"。
        """
        from app.runtime.platform.base import PlatformResponse
        from app.services.platform_router import send_platform_response

        return await send_platform_response(
            instance_id,
            target,
            PlatformResponse(content=content, message_type="text"),
        )

    @staticmethod
    def _resolve_platform_target(instance_id: str, session_id: str, explicit_target: str) -> str:
        """解析平台投递目标：显式指定优先（D5），否则按会话映射推断群聊/私聊。"""
        if explicit_target:
            return explicit_target
        is_group = False
        try:
            from app.infrastructure.database.config_store import luominest_config_store

            mapping = luominest_config_store.get(
                f"{_PLATFORM_SESSIONS_KEY_PREFIX}{instance_id}:{session_id}", {}
            )
            if isinstance(mapping, dict):
                is_group = bool(mapping.get("is_group", False))
        except Exception as e:
            logger.warning(f"[TaskResultDispatcher] 读取平台会话映射失败，按私聊处理: {e}")
        return f"group:{session_id}" if is_group else f"private:{session_id}"

    async def _emit_delivery_failure_event(
        self, event: TaskEvent, instance_id: str, target: str
    ) -> None:
        """投递失败时补发一条任务事件，保证降级路径在事件侧可见。"""
        from app.core.scheduler.manager import luominest_scheduler

        await luominest_scheduler.emit_task_event(TaskEvent(
            task_id=event.task_id,
            task_name=event.task_name,
            status=event.status,
            task_type=event.task_type,
            message=(
                f"结果投递到实例 {instance_id} 目标 {target} 失败，"
                f"结果已保留在任务记录（任务面板可查）"
            ),
            result=event.result,
            error=event.error,
            payload=event.payload,
        ))


# 全局单例（组合根注册为调度器事件回调）
task_result_dispatcher = TaskResultDispatcher()
