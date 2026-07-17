"""MQTT 终端适配器 - 通过 MQTT 协议连接 IoT 设备终端。"""

import json
from typing import Any

from loguru import logger

from app.infrastructure.mqtt import mqtt_client
from app.runtime.platform.base import BasePlatformAdapter, PlatformMessage, PlatformResponse


class MQTTTerminalAdapter(BasePlatformAdapter):
    platform_name = "mqtt_terminal"

    TOPIC_STATUS = "luominestai/device/{device_id}/status"
    TOPIC_COMMAND = "luominestai/device/{device_id}/command"
    TOPIC_AUDIO = "luominestai/device/{device_id}/audio"
    TOPIC_LOCATION = "luominestai/device/{device_id}/location"

    def __init__(self) -> None:
        super().__init__()
        self._subscribed_devices: set[str] = set()

    async def start(self) -> None:
        if mqtt_client:
            await mqtt_client.subscribe("luominestai/device/+/status")
            await mqtt_client.subscribe("luominestai/device/+/audio")
            await mqtt_client.subscribe("luominestai/device/+/location")
        logger.info(f"[{self.platform_name}] MQTT Terminal adapter started")

    async def send_message(self, response: PlatformResponse, target: str) -> bool:
        if not mqtt_client:
            return False
        topic = self.TOPIC_COMMAND.format(device_id=target)
        payload = {
            "type": response.message_type,
            "content": response.content,
            **(response.extra or {}),
        }
        await mqtt_client.publish(topic, json.dumps(payload), qos=1)
        return True

    async def handle_event(self, event: dict[str, Any]) -> PlatformMessage | None:
        topic = event.get("topic", "")
        payload = event.get("payload", {})

        if "/status" in topic:
            device_id = self._extract_device_id(topic)
            return PlatformMessage(
                platform=self.platform_name,
                user_id=device_id,
                content=json.dumps(payload),
                raw=payload,
            )
        elif "/audio" in topic:
            device_id = self._extract_device_id(topic)
            return PlatformMessage(
                platform=self.platform_name,
                user_id=device_id,
                content=f"[AUDIO] {len(payload.get('data', b''))} bytes",
                raw=payload,
            )
        return None

    def _extract_device_id(self, topic: str) -> str:
        parts = topic.split("/")
        for i, part in enumerate(parts):
            if part == "device" and i + 1 < len(parts):
                return parts[i + 1]
        return "unknown"
