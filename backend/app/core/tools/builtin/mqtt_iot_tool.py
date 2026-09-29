"""IoT 智能硬件与环境传感器工具 (MQTT IoT Tools).

P0-4 联通改造：IoT 工具此前只认「平台实例里的 mqtt_terminal 适配器」，与内嵌
broker 完全脱节。现统一为两条链路：

- 读取（iot_get_sensor_data）：TelemetryCache（内嵌/外部 broker 的 status 上报
  统一收敛的遥测缓存）优先 → mqtt_terminal 平台实例兜底 → 均无数据时给
  明确可操作的排查建议；
- 下发（iot_send_command）：内嵌 broker 在跑时经 TelemetryCache 直连发布到
  luominest/device/{id}/command → 否则走 mqtt_terminal 平台实例 → 均无通道时
  给明确可操作的排查建议。
"""
from __future__ import annotations

import json
from typing import Any

from loguru import logger

from app.core.tools.registry import ToolBase, ToolResult


def _find_running_mqtt_instances() -> list[Any]:
    """查找运行中的 mqtt_terminal 平台实例（原兜底路径，保持行为不变）。"""
    from app.runtime.platform.registry import list_instances

    return [
        inst for inst in list_instances()
        if getattr(inst.status, "value", str(inst.status)) == "running"
        and "mqtt" in (inst.adapter_type or "").lower()
    ]


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
        self.tier = "domain"
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
        raw_device_id = arguments.get("device_id")
        device_id = str(raw_device_id).strip() if raw_device_id else ""

        # 链路 1：遥测缓存（内嵌/外部 broker 的 status 上报统一收敛于此）
        from app.infrastructure.mqtt.telemetry_cache import get_telemetry_cache

        cache = get_telemetry_cache()
        if device_id:
            entry = cache.get(device_id)
            if entry is not None:
                data = {"device_id": device_id, "source": "telemetry_cache", **entry["payload"], "ts": entry["ts"]}
                return ToolResult.ok(json.dumps(data, ensure_ascii=False))
        else:
            devices = cache.list_devices()
            if devices:
                items = [
                    {"device_id": dev, **e["payload"], "ts": e["ts"]}
                    for dev, e in devices.items()
                ]
                return ToolResult.ok(
                    json.dumps(
                        {"source": "telemetry_cache", "count": len(items), "devices": items},
                        ensure_ascii=False,
                    )
                )

        # 链路 2：mqtt_terminal 平台实例兜底（实例可能指向独立 broker）
        running_mqtt = _find_running_mqtt_instances()
        if running_mqtt:
            adapter = running_mqtt[0].adapter
            if not adapter or not hasattr(adapter, "get_telemetry"):
                return ToolResult.fail("MQTT 适配器未就绪。")
            try:
                data = adapter.get_telemetry(device_id or None)
                if not data:
                    return ToolResult.ok("当前没有已上报传感器数据的设备在线。")
                return ToolResult.ok(json.dumps(data, ensure_ascii=False))
            except Exception as e:
                logger.error(f"[IoTGetSensorDataTool] 获取遥测失败: {e}", exc_info=True)
                return ToolResult.fail(f"获取传感器数据异常: {e}")

        # 两条链路都无数据：给明确可操作的排查建议
        return ToolResult.fail(
            "未获取到任何设备遥测数据。排查建议：\n"
            "1) 设备未上报：确认设备已连接 MQTT broker（内嵌 broker 默认 "
            "127.0.0.1:1883）并发布 JSON 遥测到 luominest/{device_id}/status 或 "
            "luominest/device/{device_id}/status；\n"
            "2) 数据过期：遥测缓存仅保留最近上报（默认 10 分钟），让设备重新上报一次即可；\n"
            "3) 平台实例模式：若使用 MQTT 终端平台实例，请确认实例已配置并处于运行状态。"
        )


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
        self.tier = "domain"
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

        # 链路 1：内嵌 broker 在跑 → 直连发布（外部模式不走此路：实例级 broker
        # 配置可能与全局 settings 指向不同 broker，直发有打错靶子的风险）
        from app.infrastructure.mqtt.telemetry_cache import get_telemetry_cache

        cache = get_telemetry_cache()
        if cache.embedded_mode and cache.is_connected:
            try:
                sent = await cache.publish_command(device_id, command)
            except Exception as e:
                logger.error(f"[IoTSendCommandTool] 内嵌 broker 直发异常: {e}", exc_info=True)
                sent = False
            if sent:
                return ToolResult.ok(f"指令已成功下发至设备 {device_id}（内嵌 MQTT broker 直连）")
            return ToolResult.fail(f"经内嵌 MQTT broker 下发指令至设备 {device_id} 失败，设备可能已离线。")

        # 链路 2：mqtt_terminal 平台实例兜底
        running_mqtt = _find_running_mqtt_instances()
        if running_mqtt:
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

        # 两条链路都不可用：给明确可操作的排查建议
        return ToolResult.fail(
            "当前没有可用的 MQTT 下发通道。排查建议：\n"
            "1) 内嵌 broker 未运行：检查 MQTT_BROKER_EMBEDDED 配置与 1883 端口占用，重启后端启用；\n"
            "2) 平台实例模式：若使用 MQTT 终端平台实例，请确认实例已配置并处于运行状态。"
        )
