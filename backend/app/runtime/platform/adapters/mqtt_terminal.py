"""MQTT 终端适配器 — 通过 MQTT 协议连接 IoT 设备终端（ESP32-P4 等）。

基于 infrastructure/mqtt 的 LuomiNestMqttClient 实现：
- start()：连接 Broker 并订阅 topic_manager.inbound_subscription_patterns()
- 入站消息分类处理：
  - status  → 维护内存设备注册表（供 smart_home /devices 聚合）
  - chat    → PlatformMessage 路由到主 Agent（_emit_message）
  - audio   → 记录分片信息（语音链路由 Avatar 音频通道处理）
  - location→ 记录位置信息
- send_message()：向设备 command topic 下发控制命令
"""
from __future__ import annotations

import json
import time
from typing import Any

from loguru import logger

from app.core.config import settings
from app.infrastructure.mqtt import (
    LuomiNestMqttClient,
    classify_topic,
    device_command_topic,
    extract_device_id,
    inbound_subscription_patterns,
)
from app.runtime.platform.base import (
    AdapterStatus,
    BasePlatformAdapter,
    PlatformMessage,
    PlatformResponse,
)

# 设备注册表条目的最长保留时间（秒）：超时未上报 status 视为离线
_DEVICE_STALE_SECONDS = 300.0


class MQTTTerminalAdapter(BasePlatformAdapter):
    """MQTT IoT 终端适配器。

    每个平台实例持有独立的 MQTT 连接（broker 配置来自实例 config，
    缺省回退 settings.MQTT_*），收到的 chat 文本经 _emit_message
    路由到主 Agent，status 维护设备注册表。
    """

    platform_name = "mqtt_terminal"

    def __init__(self) -> None:
        super().__init__()
        self._client: LuomiNestMqttClient | None = None
        # 内存设备注册表：device_id -> {"status": dict, "last_seen": float, "online": bool}
        self._devices: dict[str, dict[str, Any]] = {}

    # ── 生命周期 ────────────────────────────────────────────────────────────

    def initialize(self, config: dict[str, Any]) -> None:
        super().initialize(config)

    def _build_client(self) -> LuomiNestMqttClient:
        """按实例配置构造客户端（config 优先，回退全局 settings）。"""
        cfg = self._config or {}
        host = str(cfg.get("broker_host") or settings.MQTT_BROKER_HOST)
        port = int(cfg.get("broker_port") or settings.MQTT_BROKER_PORT)
        username = str(cfg.get("username") or settings.MQTT_USERNAME)
        password = str(cfg.get("password") or settings.MQTT_PASSWORD)
        return LuomiNestMqttClient(
            host=host,
            port=port,
            username=username,
            password=password,
            client_id=f"luominest-terminal-{self._instance_id or 'default'}",
        )

    async def start(self) -> None:
        self.update_status(AdapterStatus.STARTING)
        self._client = self._build_client()
        self._client.on_message = self._on_mqtt_message

        connected = await self._client.connect()
        if not connected:
            # 连接失败不抛异常：后台线程会持续重连，适配器标记重连中
            self.update_status(AdapterStatus.RECONNECTING)
            self._log(
                "warning", "connection_pending",
                f"MQTT Broker 连接中（将自动重连）: {self._client.host}:{self._client.port}",
            )
        else:
            self.update_status(AdapterStatus.RUNNING)

        for pattern in inbound_subscription_patterns():
            await self._client.subscribe(pattern, qos=1)

        self._log(
            "info", "adapter_started",
            f"MQTT 终端适配器已启动: {self._client.host}:{self._client.port}",
            details={"subscriptions": inbound_subscription_patterns()},
        )
        logger.info(f"[{self.platform_name}] MQTT Terminal adapter started")

    async def stop(self) -> None:
        self.update_status(AdapterStatus.STOPPING)
        if self._client is not None:
            await self._client.disconnect()
            self._client = None
        self.update_status(AdapterStatus.STOPPED)
        self._log("info", "adapter_stopped", "MQTT 终端适配器已停止")
        logger.info(f"[{self.platform_name}] MQTT Terminal adapter stopped")

    # ── 出站 ────────────────────────────────────────────────────────────────

    async def send_message(self, response: PlatformResponse, target: str) -> bool:
        """向设备下发命令（target = device_id）。"""
        if self._client is None or not self._client.is_connected:
            logger.warning(f"[{self.platform_name}] MQTT 未连接，无法下发命令: target={target}")
            self._log("warning", "message_failed", f"MQTT 未连接，命令下发失败: {target}")
            return False

        payload = {
            "type": response.message_type,
            "content": response.content,
            **(response.extra or {}),
        }
        topic = device_command_topic(target)
        sent = await self._client.publish(topic, json.dumps(payload, ensure_ascii=False), qos=1)
        if sent:
            self._message_count += 1
            self._log("info", "message_sent", f"命令已下发至设备 {target}", details={"topic": topic})
        else:
            self._log("warning", "message_failed", f"命令下发失败: {target}", details={"topic": topic})
        return sent

    # ── 入站 ────────────────────────────────────────────────────────────────

    async def _on_mqtt_message(self, topic: str, payload: bytes, qos: int) -> None:
        """全局 MQTT 消息回调（事件循环线程上执行）。"""
        category = classify_topic(topic)
        device_id = extract_device_id(topic)

        if category == "status":
            await self._handle_status(device_id, payload)
        elif category == "chat":
            await self._handle_chat(device_id, payload)
        elif category == "audio":
            self._log(
                "info", "audio_chunk",
                f"设备 {device_id} 音频分片: {len(payload)} bytes",
                details={"topic": topic},
            )
        elif category == "location":
            await self._handle_location(device_id, payload)
        else:
            logger.debug(f"[{self.platform_name}] 未分类 topic 忽略: {topic}")

    async def _handle_status(self, device_id: str, payload: bytes) -> None:
        """处理设备状态上报：更新注册表（JSON 解析失败也保留原始文本）。"""
        try:
            status = json.loads(payload.decode("utf-8", errors="replace"))
            if not isinstance(status, dict):
                status = {"raw": str(status)}
        except (ValueError, UnicodeDecodeError):
            status = {"raw": payload.decode("utf-8", errors="replace")[:200]}

        entry = self._devices.setdefault(device_id, {})
        prev_state = entry.get("status", {}).get("state")
        entry["status"] = status
        entry["last_seen"] = time.time()
        entry["online"] = True

        new_state = status.get("state")
        # 状态变化才记平台日志（每秒一次的心跳不刷屏）
        if new_state != prev_state:
            self._log(
                "info", "device_status",
                f"设备 {device_id} 状态: {new_state or 'unknown'}",
                details={"device_id": device_id, "state": new_state},
            )
        else:
            logger.debug(f"[{self.platform_name}] device {device_id} heartbeat: {new_state}")

    async def _handle_chat(self, device_id: str, payload: bytes) -> None:
        """处理终端聊天文本：路由到主 Agent。"""
        try:
            data = json.loads(payload.decode("utf-8", errors="replace"))
            content = str(data.get("content", "")).strip() if isinstance(data, dict) else ""
        except (ValueError, UnicodeDecodeError):
            content = payload.decode("utf-8", errors="replace").strip()

        if not content:
            return

        # 更新设备注册表活跃时间
        entry = self._devices.setdefault(device_id, {})
        entry["last_seen"] = time.time()
        entry["online"] = True

        message = PlatformMessage(
            platform=self.platform_name,
            user_id=device_id,
            content=content,
            session_id=f"mqtt_{device_id}",
            sender_name=f"device:{device_id}",
            raw={"topic_kind": "chat"},
        )
        self._log(
            "info", "message_received",
            f"设备 {device_id} 聊天消息: {content[:80]}",
            details={"device_id": device_id},
        )
        response = await self._emit_message(message)
        # 主 Agent 的回复直接回到该设备的 chat topic
        if response is not None and response.content:
            from app.infrastructure.mqtt.topic_manager import chat_message_topic

            await self._client.publish(
                chat_message_topic(device_id),
                json.dumps({"type": "chat", "content": response.content}, ensure_ascii=False),
                qos=1,
            )

    async def _handle_location(self, device_id: str, payload: bytes) -> None:
        """处理位置上报：记录到设备注册表。"""
        try:
            location = json.loads(payload.decode("utf-8", errors="replace"))
            if not isinstance(location, dict):
                location = {"raw": str(location)}
        except (ValueError, UnicodeDecodeError):
            location = {"raw": payload.decode("utf-8", errors="replace")[:200]}

        entry = self._devices.setdefault(device_id, {})
        entry["location"] = location
        entry["last_seen"] = time.time()
        entry["online"] = True
        logger.debug(f"[{self.platform_name}] device {device_id} location: {location}")

    # ── 设备注册表（供 smart_home 聚合） ────────────────────────────────────

    async def list_devices(self) -> list[dict[str, Any]]:
        """返回注册表中的设备快照（超过 _DEVICE_STALE_SECONDS 未上报视为离线）。"""
        now = time.time()
        devices: list[dict[str, Any]] = []
        for device_id, entry in self._devices.items():
            last_seen = entry.get("last_seen", 0.0)
            online = entry.get("online", False) and (now - last_seen) < _DEVICE_STALE_SECONDS
            devices.append({
                "device_id": device_id,
                "name": entry.get("status", {}).get("name", device_id),
                "state": entry.get("status", {}).get("state", "unknown"),
                "online": online,
                "last_seen": last_seen,
                "status": entry.get("status", {}),
                "location": entry.get("location"),
                "source": self.platform_name,
                "instance_id": self._instance_id,
            })
        return devices

    async def health_check(self) -> dict:
        base = await super().health_check()
        base["broker"] = (
            {"host": self._client.host, "port": self._client.port, "connected": self._client.is_connected}
            if self._client
            else None
        )
        base["device_count"] = len(self._devices)
        return base
