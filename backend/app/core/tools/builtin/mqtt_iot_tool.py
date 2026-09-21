"""IoT 智能硬件与环境传感器工具 (MQTT IoT Tools).

提供主 Agent 获取真实世界环境遥测信息（室内温湿度、空气质量、电量）
以及向 MQTT 智能设备下发控制指令的能力。
"""
from __future__ import annotations

import json
from typing import Any

from loguru import logger

from app.core.tools.registry import ToolBase, ToolResult


class IoTGetSensorDataTool(ToolBase):
    """获取 IoT 传感器遥测数据工具。"""

    def __init__(self) -> None:
        self._name = "iot_get_sensor_data"
        self._description = (
            "获取家中或已连接环境中的 IoT 传感器遥测数据（如室内温湿度、光照、电量、空气质量等）。"
            "可以指定设备 ID，或查询所有在线传感器。"
        )
        self._parameters = {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "目标硬件设备 ID（可选，若不传则获取全部在线设备的最新传感器遥测）",
                },
            },
        }
        self.tier = "standard"
        self.category = "iot"

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters(self) -> dict[str, Any]:
        return self._parameters

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        device_id = arguments.get("device_id")
        from app.runtime.platform.registry import list_instances

        # 查找运行中的 mqtt_terminal 实例
        running_mqtt = [
            inst for inst in list_instances()
            if getattr(inst.status, "value", str(inst.status)) == "running"
            and "mqtt" in (inst.adapter_type or "").lower()
        ]

        if not running_mqtt:
            return ToolResult.fail(
                "未检测到运行中的 MQTT 终端服务。若需读取真实温湿度或硬件传感器，"
                "请先在平台设置中配置并启动 MQTT 终端实例。"
            )

        adapter = running_mqtt[0].adapter
        if not adapter or not hasattr(adapter, "get_telemetry"):
            return ToolResult.fail("MQTT 适配器未就绪。")

        try:
            data = adapter.get_telemetry(device_id)
            if not data:
                return ToolResult.ok("当前没有已上报传感器数据的设备在线。")
            return ToolResult.ok(json.dumps(data, ensure_ascii=False))
        except Exception as e:
            logger.error(f"[IoTGetSensorDataTool] 获取遥测失败: {e}", exc_info=True)
            return ToolResult.fail(f"获取传感器数据异常: {e}")


class IoTSendCommandTool(ToolBase):
    """向 IoT 设备发送控制指令工具。"""

    def __init__(self) -> None:
        self._name = "iot_send_command"
        self._description = (
            "向已连接的 IoT 智能硬件或终端设备下发控制指令（例如控制智能插座、开关灯、调整模式等）。"
        )
        self._parameters = {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "目标硬件设备 ID",
                },
                "command": {
                    "type": "string",
                    "description": "下发的控制指令或 JSON 数据（如 {'action': 'switch', 'state': 'on'}）",
                },
            },
            "required": ["device_id", "command"],
        }
        self.tier = "standard"
        self.category = "iot"

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters(self) -> dict[str, Any]:
        return self._parameters

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        device_id = str(arguments.get("device_id", "")).strip()
        command = str(arguments.get("command", "")).strip()
        if not device_id or not command:
            return ToolResult.fail("必须提供 device_id 和 command")

        from app.runtime.platform.registry import list_instances

        running_mqtt = [
            inst for inst in list_instances()
            if getattr(inst.status, "value", str(inst.status)) == "running"
            and "mqtt" in (inst.adapter_type or "").lower()
        ]

        if not running_mqtt:
            return ToolResult.fail("未检测到运行中的 MQTT 终端服务，无法下发硬件指令。")

        adapter = running_mqtt[0].adapter
        if not adapter:
            return ToolResult.fail("MQTT 适配器未就绪。")

        try:
            from app.runtime.platform.base import PlatformResponse
            resp = PlatformResponse(content=command, message_type="command")
            sent = await adapter.send_message(resp, device_id)
            if sent:
                return ToolResult.ok(f"指令已成功下发至设备 {device_id}")
            else:
                return ToolResult.fail(f"下发指令至设备 {device_id} 失败，设备可能已离线。")
        except Exception as e:
            logger.error(f"[IoTSendCommandTool] 指令下发异常: {e}", exc_info=True)
            return ToolResult.fail(f"下发指令异常: {e}")
