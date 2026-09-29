"""设备遥测内存缓存（TelemetryCache）— P0-4「IoT 与内嵌 broker 联通」。

背景：内嵌 broker（broker.py，W6-3）与平台实例的 mqtt_terminal 适配器是两条
平行链——内嵌 broker 收到的设备遥测此前无人消费，IoT 工具（iot_get_sensor_data
等）只认平台实例。本服务补上统一的消费端：

1. 持有一条 paho 连接，订阅全部设备 status 上报 topic（复用 topic_manager
   前缀常量，覆盖规范 device 段形式、固件直连简写形式与 luominestai 旧前缀）；
2. 内嵌 broker 在跑时经 loopback（127.0.0.1:broker 端口）连接；否则按
   settings.MQTT_* 外部 broker 配置建连（沿用 LuomiNestMqttClient 的自动重连）；
3. 内存 dict 缓存 device_id → {payload, ts}，读取时按 TTL 过滤过期项（惰性清理）；
4. 内嵌模式下提供 publish_command()：IoT 工具下发命令直连内嵌 broker，
   不再绕道平台实例。

两条 MQTT 链的统一方式：
- 上报侧：无论设备连的是内嵌 broker 还是外部 broker，遥测统一收敛到本缓存
  这一「最近上报」单一事实源，iot_get_sensor_data 只查缓存即可命中；
- 下发侧：内嵌模式直连 broker 发布（settings 的 broker 即内嵌 broker，无歧义）；
  外部模式仍走平台实例路径，尊重实例级 broker 配置（实例可能与全局 settings
  指向不同 broker，直发有打错靶子的风险）。

生命周期：app_factory lifespan 启动时 start()、关闭时 stop()，实例挂 app.state。
全局单例经 get_telemetry_cache() / set_telemetry_cache() 存取（测试可注入）。
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from loguru import logger

from app.core.config import settings
from app.infrastructure.mqtt.client import LuomiNestMqttClient
from app.infrastructure.mqtt.topic_manager import (
    LEGACY_TOPIC_PREFIX,
    TOPIC_PREFIX,
    device_command_topic,
    extract_device_id,
)

# 遥测订阅模式：规范形式 + 固件直连简写形式 + 旧前缀兼容（两类前缀 × 两种形态）
_STATUS_SUBSCRIPTION_PATTERNS: tuple[str, ...] = (
    f"{TOPIC_PREFIX}/device/+/status",
    f"{TOPIC_PREFIX}/+/status",
    f"{LEGACY_TOPIC_PREFIX}/device/+/status",
    f"{LEGACY_TOPIC_PREFIX}/+/status",
)


class TelemetryCache:
    """设备遥测内存缓存（单一 paho 连接 + TTL 字典）。

    Usage:
        cache = TelemetryCache()
        await cache.start(embedded_broker=broker)   # 内嵌 broker 在跑则 loopback 直连
        entry = cache.get("p4")                     # {"payload": {...}, "ts": ...}
        devices = cache.list_devices()              # 全部未过期设备
        await cache.publish_command("p4", "...")    # 内嵌模式下直发命令
        await cache.stop()
    """

    def __init__(
        self,
        ttl: float | None = None,
        host: str | None = None,
        port: int | None = None,
        username: str = "",
        password: str = "",
        client_id: str = "luominest-telemetry-cache",
    ) -> None:
        self._ttl = float(ttl) if ttl is not None else float(settings.TELEMETRY_CACHE_TTL)
        # 显式 host/port 优先（测试注入专用）；缺省按内嵌/外部模式自动解析
        self._host_override = host
        self._port_override = port
        self._username = username
        self._password = password
        self._client_id = client_id

        self._client: LuomiNestMqttClient | None = None
        self._connect_task: asyncio.Task | None = None
        self._mode = "external"  # embedded | external
        # device_id -> {"payload": dict, "ts": float}
        self._entries: dict[str, dict[str, Any]] = {}

    # ── 属性 ────────────────────────────────────────────────────────────────

    @property
    def ttl(self) -> float:
        return self._ttl

    @property
    def mode(self) -> str:
        """当前连接模式：embedded（内嵌 broker loopback）/ external（settings 配置）。"""
        return self._mode

    @property
    def embedded_mode(self) -> bool:
        return self._mode == "embedded"

    @property
    def is_connected(self) -> bool:
        return self._client is not None and self._client.is_connected

    @property
    def subscription_patterns(self) -> list[str]:
        return list(_STATUS_SUBSCRIPTION_PATTERNS)

    # ── 生命周期 ────────────────────────────────────────────────────────────

    async def start(self, embedded_broker: Any = None) -> bool:
        """启动缓存并后台建连订阅。

        Args:
            embedded_broker: 内嵌 broker 实例（EmbeddedMqttBroker）；在跑时经
                loopback 连接，否则按 settings.MQTT_* 外部 broker 配置连接。

        建连放后台任务：外部 broker 暂不可达时不阻塞主服务启动
        （paho 线程内持续重试，订阅已缓存、连接成功后自动补订）。
        """
        if self._client is not None:
            return True

        use_embedded = (
            self._host_override is None
            and embedded_broker is not None
            and getattr(embedded_broker, "is_running", False)
        )
        host, port = self._resolve_broker(embedded_broker)
        self._mode = "embedded" if use_embedded else "external"

        self._client = LuomiNestMqttClient(
            host=host,
            port=port,
            username=self._username or settings.MQTT_USERNAME,
            password=self._password or settings.MQTT_PASSWORD,
            client_id=self._client_id,
        )
        self._client.on_message = self.handle_message
        self._connect_task = asyncio.create_task(self._client.connect())
        # subscribe 在未连接时会缓存，连接成功后由客户端自动补订（含重连场景）
        for pattern in _STATUS_SUBSCRIPTION_PATTERNS:
            await self._client.subscribe(pattern, qos=1)
        logger.info(
            f"[TelemetryCache] 已启动（mode={self._mode}, broker={host}:{port}, "
            f"ttl={self._ttl}s, patterns={len(_STATUS_SUBSCRIPTION_PATTERNS)}）"
        )
        return True

    async def stop(self) -> None:
        """停止缓存：取消建连任务、断开客户端、清空缓存。"""
        if self._connect_task is not None:
            self._connect_task.cancel()
            self._connect_task = None
        if self._client is not None:
            await self._client.disconnect()
            self._client = None
        self._entries.clear()
        self._mode = "external"
        logger.info("[TelemetryCache] 已停止")

    # ── 读取 ────────────────────────────────────────────────────────────────

    def get(self, device_id: str) -> dict[str, Any] | None:
        """获取指定设备的最新遥测（过期返回 None 并惰性清理）。

        Returns:
            {"payload": dict, "ts": float} 的浅拷贝；无数据或已过期返回 None。
        """
        entry = self._entries.get(device_id)
        if entry is None:
            return None
        if time.time() - entry["ts"] > self._ttl:
            del self._entries[device_id]
            return None
        return {"payload": dict(entry["payload"]), "ts": entry["ts"]}

    def list_devices(self) -> dict[str, dict[str, Any]]:
        """列出全部未过期设备：{device_id: {"payload": dict, "ts": float}}。"""
        now = time.time()
        return {
            device_id: {"payload": dict(entry["payload"]), "ts": entry["ts"]}
            for device_id, entry in self._entries.items()
            if now - entry["ts"] <= self._ttl
        }

    # ── 写入（paho 回调） ───────────────────────────────────────────────────

    async def handle_message(self, topic: str, payload: bytes, qos: int = 0) -> None:
        """MQTT status 消息回调（LuomiNestMqttClient.on_message 签名）。

        JSON 解析失败也保留原始文本（对齐 mqtt_terminal 适配器的宽容策略）。
        """
        device_id = extract_device_id(topic)
        if not device_id or device_id == "unknown":
            logger.debug(f"[TelemetryCache] 无法从 topic 解析 device_id，忽略: {topic}")
            return
        try:
            payload_dict = json.loads(payload.decode("utf-8", errors="replace"))
            if not isinstance(payload_dict, dict):
                payload_dict = {"raw": str(payload_dict)}
        except (ValueError, UnicodeDecodeError):
            payload_dict = {"raw": payload.decode("utf-8", errors="replace")[:200]}
        self._entries[device_id] = {"payload": payload_dict, "ts": time.time()}
        logger.debug(f"[TelemetryCache] 设备 {device_id} 遥测已缓存: {topic}")

    # ── 下发（内嵌模式直连） ────────────────────────────────────────────────

    async def publish_command(self, device_id: str, command: str) -> bool:
        """向设备 command topic 直发控制命令（luominest/device/{id}/command）。

        仅在客户端已连接时可用；payload 形态对齐 mqtt_terminal 适配器
        （{"type": "command", "content": ...}），固件侧解析无需区分来源。
        """
        if self._client is None or not self._client.is_connected:
            logger.warning(f"[TelemetryCache] 未连接 broker，丢弃命令下发: {device_id}")
            return False
        payload = json.dumps({"type": "command", "content": command}, ensure_ascii=False)
        return await self._client.publish(device_command_topic(device_id), payload, qos=1)

    # ── 内部 ────────────────────────────────────────────────────────────────

    def _resolve_broker(self, embedded_broker: Any) -> tuple[str, int]:
        """解析连接参数：显式覆盖 > 内嵌 broker loopback > settings 外部配置。"""
        if self._host_override is not None:
            return self._host_override, int(self._port_override or settings.MQTT_BROKER_PORT)
        if embedded_broker is not None and getattr(embedded_broker, "is_running", False):
            # 内嵌 broker：强制 loopback（broker 可能配置监听非回环地址，本机连接走回环最快）
            return "127.0.0.1", int(embedded_broker.port)
        return settings.MQTT_BROKER_HOST, settings.MQTT_BROKER_PORT


# ── 全局单例 ────────────────────────────────────────────────────────────────

_telemetry_cache: TelemetryCache | None = None


def get_telemetry_cache() -> TelemetryCache:
    """获取全局遥测缓存单例（懒初始化，未 start 状态仅查询返回空）。"""
    global _telemetry_cache
    if _telemetry_cache is None:
        _telemetry_cache = TelemetryCache()
    return _telemetry_cache


def set_telemetry_cache(cache: TelemetryCache | None) -> None:
    """替换全局单例（测试注入 / 生命周期重建）。"""
    global _telemetry_cache
    _telemetry_cache = cache
