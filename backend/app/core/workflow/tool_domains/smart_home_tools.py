"""智能家居模块的内部工具处理函数（smart_home.*）。

从原 register_tools.py 拆出（大文件拆分重构），处理函数体保持原样；
注册顺序与 schema 见 register_tools.register_internal_tools。
"""

import json
from typing import Any

from loguru import logger

from app.core.workflow.models import WorkflowTaskResult
from app.core.workflow.tool_domains.common import _get_emitter


async def _smart_home_control(args: dict[str, Any]) -> WorkflowTaskResult:
    """控制智能家居设备

    通过平台实例（MQTT/HomeAssistant/小米IoT）向设备发送控制命令。
    """
    device_id = args.get("device_id", "")
    action = args.get("action", "")
    params = args.get("params", {})

    if not device_id or not action:
        return WorkflowTaskResult(
            success=False,
            error="Missing required parameters: device_id, action",
        )

    try:
        from app.runtime.platform.base import PlatformResponse
        from app.runtime.platform.registry import list_instances

        # 查找包含该设备 ID 的 IoT 平台实例
        instances = list_instances()
        iot_instances = [
            inst for inst in instances
            if inst.adapter_type in ("mqtt_terminal", "home_assistant", "xiaomi_iot")
        ]

        if not iot_instances:
            return WorkflowTaskResult(
                success=False,
                error="未找到已启动的 IoT 平台实例，请先在设置中配置并启动智能家居适配器",
            )

        # 向第一个活跃的 IoT 实例发送命令
        target = iot_instances[0]
        command_payload = {
            "device_id": device_id,
            "action": action,
            "params": params,
        }

        adapter = target.adapter
        if not adapter:
            return WorkflowTaskResult(
                success=False,
                error=f"实例 {target.instance_id} 没有可用的适配器",
            )

        response = PlatformResponse(
            content=json.dumps(command_payload, ensure_ascii=False),
            message_type="text",
        )
        success = await adapter.send_message(response, target=device_id)

        # 推送工作流事件
        emitter = _get_emitter()
        if emitter:
            await emitter.emit_module_action(
                module="smart_home",
                action=action,
                success=success,
                output=f"设备 {device_id} {action} 操作已发送" if success else "",
                error="" if success else "命令发送失败",
                metadata={"device_id": device_id, "action": action, "params": params},
            )

        if success:
            return WorkflowTaskResult(
                success=True,
                output=f"已向设备 {device_id} 发送 {action} 命令",
                metadata={"device_id": device_id, "action": action},
            )
        return WorkflowTaskResult(
            success=False,
            error=f"向设备 {device_id} 发送命令失败",
        )
    except Exception as e:
        logger.error("[Workflow:smart_home.control] Failed: {}", str(e), exc_info=True)
        return WorkflowTaskResult(success=False, error=str(e))


async def _smart_home_list_devices(args: dict[str, Any]) -> WorkflowTaskResult:
    """列出智能家居设备"""
    try:
        from app.runtime.platform.registry import list_instances

        instances = list_instances()
        iot_instances = [
            inst for inst in instances
            if inst.adapter_type in ("mqtt_terminal", "home_assistant", "xiaomi_iot")
        ]

        devices = []
        for inst in iot_instances:
            devices.append({
                "instance_id": inst.instance_id,
                "name": inst.name,
                "adapter_type": inst.adapter_type,
                "status": inst.status.value if hasattr(inst.status, 'value') else str(inst.status),
            })

        return WorkflowTaskResult(
            success=True,
            output=json.dumps(devices, ensure_ascii=False),
            metadata={"count": len(devices)},
        )
    except Exception as e:
        logger.error("[Workflow:smart_home.list_devices] Failed: {}", str(e), exc_info=True)
        return WorkflowTaskResult(success=False, error=str(e))


async def _smart_home_list_scenes(args: dict[str, Any]) -> WorkflowTaskResult:
    """列出智能家居场景"""
    try:
        from app.api.v1.endpoints.smart_home import list_scenes

        result = await list_scenes()
        scenes = result if isinstance(result, list) else []

        return WorkflowTaskResult(
            success=True,
            output=json.dumps(scenes, ensure_ascii=False),
            metadata={"count": len(scenes)},
        )
    except Exception as e:
        logger.error("[Workflow:smart_home.list_scenes] Failed: {}", str(e), exc_info=True)
        return WorkflowTaskResult(success=False, error=str(e))
