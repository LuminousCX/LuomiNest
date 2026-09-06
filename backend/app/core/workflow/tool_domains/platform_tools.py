"""平台接入模块的内部工具处理函数（platform.*）。

从原 register_tools.py 拆出（大文件拆分重构），处理函数体保持原样；
注册顺序与 schema 见 register_tools.register_internal_tools。
"""

import json
from typing import Any

from loguru import logger

from app.core.workflow.models import WorkflowTaskResult
from app.core.workflow.tool_domains.common import _get_emitter


async def _platform_list_instances(args: dict[str, Any]) -> WorkflowTaskResult:
    """列出所有平台实例"""
    try:
        from app.runtime.platform.registry import list_instances

        instances = list_instances()
        instance_list = []
        for inst in instances:
            instance_list.append({
                "id": inst.instance_id,
                "adapter_type": inst.adapter_type,
                "name": inst.name,
                "status": inst.status.value if hasattr(inst.status, 'value') else str(inst.status),
                "enable": inst.enable,
            })

        return WorkflowTaskResult(
            success=True,
            output=json.dumps(instance_list, ensure_ascii=False),
            metadata={"count": len(instance_list)},
        )
    except Exception as e:
        logger.error("[Workflow:platform.list_instances] Failed: {}", str(e), exc_info=True)
        return WorkflowTaskResult(success=False, error=str(e))


async def _platform_start_instance(args: dict[str, Any]) -> WorkflowTaskResult:
    """启动平台实例"""
    instance_id = args.get("instance_id", "")
    if not instance_id:
        return WorkflowTaskResult(success=False, error="Missing required parameter: instance_id")

    try:
        from app.runtime.platform.registry import start_instance

        await start_instance(instance_id)

        emitter = _get_emitter()
        if emitter:
            await emitter.emit_module_action(
                module="platform",
                action="started",
                success=True,
                output=f"已启动平台实例: {instance_id}",
                metadata={"instance_id": instance_id},
            )

        return WorkflowTaskResult(
            success=True,
            output=f"已启动平台实例: {instance_id}",
            metadata={"instance_id": instance_id},
        )
    except Exception as e:
        logger.error("[Workflow:platform.start_instance] Failed: {}", str(e), exc_info=True)
        return WorkflowTaskResult(success=False, error=str(e))


async def _platform_stop_instance(args: dict[str, Any]) -> WorkflowTaskResult:
    """停止平台实例"""
    instance_id = args.get("instance_id", "")
    if not instance_id:
        return WorkflowTaskResult(success=False, error="Missing required parameter: instance_id")

    try:
        from app.runtime.platform.registry import stop_instance

        await stop_instance(instance_id)

        emitter = _get_emitter()
        if emitter:
            await emitter.emit_module_action(
                module="platform",
                action="stopped",
                success=True,
                output=f"已停止平台实例: {instance_id}",
                metadata={"instance_id": instance_id},
            )

        return WorkflowTaskResult(
            success=True,
            output=f"已停止平台实例: {instance_id}",
            metadata={"instance_id": instance_id},
        )
    except Exception as e:
        logger.error("[Workflow:platform.stop_instance] Failed: {}", str(e), exc_info=True)
        return WorkflowTaskResult(success=False, error=str(e))


async def _platform_send_message(args: dict[str, Any]) -> WorkflowTaskResult:
    """通过平台实例发送消息"""
    instance_id = args.get("instance_id", "")
    message = args.get("message", "")
    target = args.get("target", "")

    if not instance_id or not message:
        return WorkflowTaskResult(
            success=False,
            error="Missing required parameters: instance_id, message",
        )

    try:
        from app.runtime.platform.registry import get_instance

        instance = get_instance(instance_id)
        if not instance:
            return WorkflowTaskResult(success=False, error=f"平台实例 {instance_id} 不存在")

        payload = json.dumps({
            "type": "send_message",
            "message": message,
            "target": target,
        }, ensure_ascii=False)

        success = await instance.send_message(payload)

        emitter = _get_emitter()
        if emitter:
            await emitter.emit_module_action(
                module="platform",
                action="message_sent",
                success=success,
                output=f"已发送消息到 {instance_id}" if success else "发送失败",
                metadata={"instance_id": instance_id, "target": target},
            )

        if success:
            return WorkflowTaskResult(
                success=True,
                output=f"已通过平台实例 {instance_id} 发送消息",
                metadata={"instance_id": instance_id},
            )
        return WorkflowTaskResult(success=False, error="消息发送失败")
    except Exception as e:
        logger.error("[Workflow:platform.send_message] Failed: {}", str(e), exc_info=True)
        return WorkflowTaskResult(success=False, error=str(e))
