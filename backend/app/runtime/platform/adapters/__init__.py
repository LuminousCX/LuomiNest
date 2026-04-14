import json
import asyncio
from typing import Any
from app.runtime.platform.base import BasePlatformAdapter, PlatformMessage, PlatformResponse
from app.infrastructure.mqtt import get_mqtt_client
from app.core.config import settings
from loguru import logger


class MQTTTerminalAdapter(BasePlatformAdapter):
    platform_name = "mqtt_terminal"

    TOPIC_STATUS = "luominestai/device/{device_id}/status"
    TOPIC_COMMAND = "luominestai/device/{device_id}/command"
    TOPIC_AUDIO = "luominestai/device/{device_id}/audio"
    TOPIC_LOCATION = "luominestai/device/{device_id}/location"

    def __init__(self):
        self._subscribed_devices: set[str] = set()

    async def start(self) -> None:
        client = get_mqtt_client()
        if not client:
            logger.warning(f"[{self.platform_name}] MQTT client not available, adapter will not function")
            return
        await client.subscribe("luominestai/device/+/status")
        await client.subscribe("luominestai/device/+/audio")
        await client.subscribe("luominestai/device/+/location")
        logger.info(f"[{self.platform_name}] MQTT Terminal adapter started")

    async def send_message(self, response: PlatformResponse, target: str) -> bool:
        client = get_mqtt_client()
        if not client:
            logger.warning(f"[{self.platform_name}] MQTT client not available")
            return False
        topic = self.TOPIC_COMMAND.format(device_id=target)
        payload = {
            "type": response.message_type,
            "content": response.content,
            **(response.extra or {}),
        }
        await client.publish(topic, json.dumps(payload), qos=1)
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


class WebSocketPlatformAdapter(BasePlatformAdapter):
    platform_name = "websocket"

    def __init__(self):
        self._connections: dict[str, Any] = {}

    async def send_message(self, response: PlatformResponse, target: str) -> bool:
        conn = self._connections.get(target)
        if conn and hasattr(conn, 'send_json'):
            await conn.send_json({"type": "message", "data": {"content": response.content}})
            return True
        return False

    async def handle_event(self, event: dict[str, Any]) -> PlatformMessage | None:
        ws = event.get("ws")
        data = event.get("data", {})
        conn_id = event.get("conn_id", "")
        if ws:
            self._connections[conn_id] = ws
        return PlatformMessage(
            platform=self.platform_name,
            user_id=conn_id,
            content=data.get("content", ""),
            raw=data,
        ) if data.get("content") else None


class RESTPlatformAdapter(BasePlatformAdapter):
    platform_name = "rest_api"

    async def send_message(self, response: PlatformResponse, target: str) -> bool:
        return True

    async def handle_event(self, event: dict[str, Any]) -> PlatformMessage | None:
        return PlatformMessage(
            platform=self.platform_name,
            user_id=event.get("user_id", "anonymous"),
            content=event.get("content", ""),
            raw=event,
        )


def register_platform_adapters() -> dict[str, BasePlatformAdapter]:
    return {
        "mqtt_terminal": MQTTTerminalAdapter(),
        "websocket": WebSocketPlatformAdapter(),
        "rest_api": RESTPlatformAdapter(),
    }