"""MQTT 发布助手 — 面向业务的极简发布入口。

业务代码不需要自己管理客户端生命周期，
直接 ``await mqtt_publish(topic, payload)`` 即可（使用全局共享客户端）。
"""
from __future__ import annotations

from loguru import logger

from app.infrastructure.mqtt.client import LuomiNestMqttClient
from app.infrastructure.mqtt.topic_manager import (
    TOPIC_PREFIX,
    chat_message_topic,
    device_command_topic,
)


async def mqtt_publish(topic: str, payload: str | bytes, qos: int = 1) -> bool:
    """通过全局共享客户端发布消息。"""
    from app.infrastructure.mqtt import get_mqtt_client

    client = get_mqtt_client()
    if client is None:
        logger.warning(f"[MqttPublisher] 全局客户端未初始化，丢弃发布: {topic}")
        return False
    return await client.publish(topic, payload, qos=qos)


async def publish_device_command(device_id: str, command: dict, qos: int = 1) -> bool:
    """向设备下发控制命令（luominest/device/{id}/command）。"""
    import json

    return await mqtt_publish(
        device_command_topic(device_id),
        json.dumps(command, ensure_ascii=False),
        qos=qos,
    )


async def publish_chat_message(device_id: str, text: str, qos: int = 1) -> bool:
    """向终端下发聊天文本（luominest/chat/{id}/message）。"""
    import json

    return await mqtt_publish(
        chat_message_topic(device_id),
        json.dumps({"type": "chat", "content": text, "prefix": TOPIC_PREFIX}, ensure_ascii=False),
        qos=qos,
    )


__all__ = [
    "LuomiNestMqttClient",
    "mqtt_publish",
    "publish_device_command",
    "publish_chat_message",
]
