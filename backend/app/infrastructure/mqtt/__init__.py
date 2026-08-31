"""MQTT 基础设施 — 客户端、发布助手与 Topic 规范。

模块结构：
- ``client.py``       LuomiNestMqttClient（paho-mqtt 异步封装，自动重连）
- ``publisher.py``    mqtt_publish / publish_device_command 等业务发布入口
- ``topic_manager.py``  统一 topic 前缀（luominest/）与构造/解析

全局共享客户端通过 ``get_mqtt_client()`` 懒初始化（读取 settings
的 MQTT_* 配置），``set_mqtt_client()`` 供测试注入。
"""
from __future__ import annotations

from app.core.config import settings
from app.infrastructure.mqtt.client import LuomiNestMqttClient
from app.infrastructure.mqtt.topic_manager import (
    TOPIC_PREFIX,
    chat_message_topic,
    classify_topic,
    device_audio_topic,
    device_command_topic,
    device_location_topic,
    device_status_topic,
    extract_device_id,
    firmware_status_topic,
    inbound_subscription_patterns,
)

_shared_client: LuomiNestMqttClient | None = None


def get_mqtt_client() -> LuomiNestMqttClient | None:
    """获取全局共享 MQTT 客户端（懒初始化，未连接状态）。"""
    global _shared_client
    if _shared_client is None:
        try:
            _shared_client = LuomiNestMqttClient(
                host=settings.MQTT_BROKER_HOST,
                port=settings.MQTT_BROKER_PORT,
                username=settings.MQTT_USERNAME,
                password=settings.MQTT_PASSWORD,
            )
        except Exception:
            from loguru import logger

            logger.warning("[Mqtt] 全局客户端初始化失败", exc_info=True)
            return None
    return _shared_client


def set_mqtt_client(client: LuomiNestMqttClient | None) -> None:
    """替换全局共享客户端（测试注入 / 自定义连接参数）。"""
    global _shared_client
    _shared_client = client


__all__ = [
    "LuomiNestMqttClient",
    "get_mqtt_client",
    "set_mqtt_client",
    "TOPIC_PREFIX",
    "chat_message_topic",
    "classify_topic",
    "device_audio_topic",
    "device_command_topic",
    "device_location_topic",
    "device_status_topic",
    "extract_device_id",
    "firmware_status_topic",
    "inbound_subscription_patterns",
]
