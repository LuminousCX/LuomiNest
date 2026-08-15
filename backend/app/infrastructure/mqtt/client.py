"""LuomiNest MQTT 客户端 — 基于 paho-mqtt 2.x 的异步封装。

paho 自带后台网络线程（loop_start）与自动重连（connect_async +
reconnect_delay_set），本封装负责：

1. 把 paho 线程回调桥接到 asyncio 事件循环（call_soon_threadsafe）；
2. 提供可 await 的 publish / subscribe 接口；
3. 连接状态跟踪与优雅关闭。

参考：SRS FR-CONNECT-005 指数退避（初始 1s → 上限 30s，
与固件 app_mqtt.c 的 INITIAL/MAX_BACKOFF_MS 保持一致）。
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Any, Awaitable, Callable

from loguru import logger

# 消息回调：(topic, payload_bytes, qos) -> None（在事件循环线程上执行）
MqttMessageHandler = Callable[[str, bytes, int], Awaitable[None]]

# 重连退避（秒）
_INITIAL_RECONNECT_DELAY = 1.0
_MAX_RECONNECT_DELAY = 30.0
# 连接建立等待上限（秒）
_CONNECT_TIMEOUT = 10.0


class LuomiNestMqttClient:
    """paho-mqtt 异步封装（每实例一条后台网络线程）。

    Usage:
        client = LuomiNestMqttClient(host, port, username=..., password=...)
        await client.connect()
        await client.subscribe("luominest/device/+/status")
        client.on_message = handler          # async def handler(topic, payload, qos)
        await client.publish("luominest/device/p4/command", b"{...}", qos=1)
        await client.disconnect()
    """

    def __init__(
        self,
        host: str,
        port: int = 1883,
        username: str = "",
        password: str = "",
        client_id: str = "",
        keepalive: int = 30,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._client_id = client_id or f"luominest-backend-{uuid.uuid4().hex[:8]}"
        self._keepalive = keepalive

        self._client: Any = None  # paho.Client（延迟创建，便于测试替换）
        self._loop: asyncio.AbstractEventLoop | None = None
        self._connected: bool = False
        self._subscriptions: list[tuple[str, int]] = []
        self.on_message: MqttMessageHandler | None = None
        self.on_connect: Callable[[], None] | None = None
        self._connect_event: asyncio.Event | None = None

    # ── 属性 ────────────────────────────────────────────────────────────────

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ── 连接管理 ────────────────────────────────────────────────────────────

    def _build_paho_client(self) -> Any:
        """创建 paho 客户端（独立方法便于测试时 mock）。"""
        import paho.mqtt.client as mqtt

        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=self._client_id,
            protocol=mqtt.MQTTv311,
        )
        if self._username:
            client.username_pw_set(self._username, self._password)
        # 指数退避自动重连（对齐固件 1s→30s）
        client.reconnect_delay_set(
            delay_min=int(_INITIAL_RECONNECT_DELAY),
            delay_max=int(_MAX_RECONNECT_DELAY),
        )
        return client

    async def connect(self) -> bool:
        """建立连接（后台线程自动重连，失败不抛异常仅返回 False）。"""
        if self._connected:
            return True

        self._loop = asyncio.get_running_loop()
        self._connect_event = asyncio.Event()

        if self._client is None:
            self._client = self._build_paho_client()
            self._client.on_connect = self._on_paho_connect
            self._client.on_disconnect = self._on_paho_disconnect
            self._client.on_message = self._on_paho_message

        try:
            # connect_async：网络线程内持续重试直至成功（paho 自动重连语义）
            self._client.connect_async(self._host, self._port, keepalive=self._keepalive)
            self._client.loop_start()
        except Exception as e:
            logger.error(f"[MqttClient] 连接启动失败 {self._host}:{self._port}: {e}")
            return False

        try:
            await asyncio.wait_for(self._connect_event.wait(), timeout=_CONNECT_TIMEOUT)
        except asyncio.TimeoutError:
            logger.warning(
                f"[MqttClient] 连接超时（{_CONNECT_TIMEOUT}s），后台将继续重试: "
                f"{self._host}:{self._port}"
            )
            return False
        return True

    async def disconnect(self) -> None:
        """断开连接并停止后台线程。"""
        if self._client is None:
            return
        try:
            self._client.disconnect()
        except Exception:
            logger.debug("[MqttClient] 断开时异常（忽略）", exc_info=True)
        try:
            self._client.loop_stop()
        except Exception:
            logger.debug("[MqttClient] 停止网络线程异常（忽略）", exc_info=True)
        self._connected = False
        logger.info(f"[MqttClient] 已断开: {self._host}:{self._port}")

    # ── 订阅 / 发布 ─────────────────────────────────────────────────────────

    async def subscribe(self, topic: str, qos: int = 1) -> bool:
        """订阅 topic（连接建立前调用会先缓存，连接后自动补订）。"""
        self._subscriptions.append((topic, qos))
        if not self._connected or self._client is None:
            logger.debug(f"[MqttClient] 未连接，订阅已缓存: {topic}")
            return False
        try:
            result, _mid = self._client.subscribe(topic, qos=qos)
            if result == 0:
                logger.debug(f"[MqttClient] 已订阅: {topic} (qos={qos})")
                return True
            logger.warning(f"[MqttClient] 订阅被 Broker 拒绝: {topic} (result={result})")
            return False
        except Exception as e:
            logger.warning(f"[MqttClient] 订阅异常: {topic}: {e}")
            return False

    async def publish(self, topic: str, payload: str | bytes, qos: int = 1) -> bool:
        """发布消息（等待 Broker 确认，最多 5 秒）。"""
        if not self._connected or self._client is None:
            logger.warning(f"[MqttClient] 未连接，丢弃发布: {topic}")
            return False
        try:
            info = self._client.publish(topic, payload, qos=qos)
            if info.rc != 0:
                logger.warning(f"[MqttClient] 发布失败: {topic} (rc={info.rc})")
                return False
            # wait_for_publish 阻塞至 Broker 确认（qos>=1），放线程池避免卡事件循环
            await asyncio.to_thread(info.wait_for_publish, 5.0)
            return True
        except Exception as e:
            logger.warning(f"[MqttClient] 发布异常: {topic}: {e}")
            return False

    # ── paho 回调（网络线程 → 事件循环桥接） ────────────────────────────────

    def _on_paho_connect(self, client, userdata, flags, reason_code, properties=None):
        """paho 线程回调：连接建立。"""
        if self._loop is None or self._loop.is_closed():
            return
        self._loop.call_soon_threadsafe(self._handle_connected, int(reason_code))

    def _handle_connected(self, reason_code: int):
        connected = reason_code == 0
        self._connected = connected
        if self._connect_event is not None:
            self._connect_event.set()
        if connected:
            logger.success(f"[MqttClient] 已连接: {self._host}:{self._port}")
            # 重连后补订（paho 不保留订阅，除非 clean_session=False）
            for topic, qos in self._subscriptions:
                try:
                    self._client.subscribe(topic, qos=qos)
                except Exception:
                    logger.warning(f"[MqttClient] 重连补订失败: {topic}", exc_info=True)
            if self.on_connect:
                try:
                    self.on_connect()
                except Exception:
                    logger.warning("[MqttClient] on_connect 回调异常", exc_info=True)
        else:
            logger.warning(f"[MqttClient] 连接被拒绝 (reason_code={reason_code})")

    def _on_paho_disconnect(self, client, userdata, flags, reason_code, properties=None):
        """paho 线程回调：连接断开。"""
        if self._loop is None or self._loop.is_closed():
            return
        self._loop.call_soon_threadsafe(self._handle_disconnected, int(reason_code))

    def _handle_disconnected(self, reason_code: int):
        if self._connected:  # 主动 disconnect 不告警
            self._connected = False
            logger.warning(
                f"[MqttClient] 连接断开 (rc={reason_code})，后台线程将自动重连"
            )

    def _on_paho_message(self, client, userdata, message):
        """paho 线程回调：收到消息 → 调度到事件循环执行 async handler。"""
        if self._loop is None or self._loop.is_closed():
            return
        topic = message.topic
        payload = bytes(message.payload)
        qos = message.qos
        self._loop.call_soon_threadsafe(self._schedule_message_handler, topic, payload, qos)

    def _schedule_message_handler(self, topic: str, payload: bytes, qos: int):
        if self.on_message is None:
            return
        task = self._loop.create_task(self._safe_invoke_handler(topic, payload, qos))
        # 避免任务引用滞留
        task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)

    async def _safe_invoke_handler(self, topic: str, payload: bytes, qos: int):
        try:
            await self.on_message(topic, payload, qos)
        except Exception:
            logger.warning(f"[MqttClient] 消息处理异常: topic={topic}", exc_info=True)
