"""LuomiNest 内嵌 MQTT broker — 基于 amqtt（纯 Python asyncio 实现）。

W6-3「内置 MQTT broker」：默认随主服务在 MQTT_BROKER_HOST:MQTT_BROKER_PORT
起一个内存型 broker，ESP32 等硬件设备直连 LuomiNest 即可上报遥测，
开箱即用，无需外装 mosquitto。

设计取舍（精简优先）：
- 匿名认证（本地单机场景，默认仅监听 127.0.0.1）；
- 不落盘持久化，全部内存态，随进程退出即清空；
- 只加载匿名认证插件（去掉每包调试日志与 $SYS 定时采集，降低开销）；
- 启动失败（端口被占用=用户已装外部 broker，或其他异常）仅告警降级，
  绝不抛出，主服务与外部 broker 模式均不受影响。
"""
from __future__ import annotations

import socket
from typing import Any

from loguru import logger

from app.core.config import settings

# plugins 配置一旦给出，amqtt 仅加载其中列出的插件（不再走 entrypoint 默认集）
_BROKER_PLUGINS: dict[str, dict[str, Any]] = {
    "amqtt.plugins.authentication.AnonymousAuthPlugin": {"allow_anonymous": True},
}


class EmbeddedMqttBroker:
    """内嵌 MQTT broker（amqtt MQTTBroker 的精简封装）。

    Usage:
        broker = EmbeddedMqttBroker()
        await broker.start()   # 失败仅告警并返回 False，不抛异常
        ...
        await broker.stop()
    """

    def __init__(self, host: str | None = None, port: int | None = None) -> None:
        self._host = host or settings.MQTT_BROKER_HOST
        self._port = port or settings.MQTT_BROKER_PORT
        self._broker: Any = None  # amqtt.broker.MQTTBroker（启动成功后持有）

    # ── 属性 ────────────────────────────────────────────────────────────────

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    @property
    def is_running(self) -> bool:
        return self._broker is not None

    # ── 生命周期 ────────────────────────────────────────────────────────────

    async def start(self) -> bool:
        """启动内嵌 broker。成功返回 True；任何失败仅告警并返回 False。"""
        if self.is_running:
            return True
        # amqtt 监听带 reuse_address=True，Windows 上会静默绑定已被占用的端口，
        # 故先探测端口，确保「mosquitto 已在跑」时走降级而非抢绑。
        if not self._port_available():
            logger.warning(
                "内嵌 MQTT broker 启动失败（端口可能被占用），跳过内嵌 broker，外部 broker 模式不受影响: "
                f"{self._host}:{self._port}: 端口已被占用"
            )
            return False
        try:
            from amqtt.broker import Broker  # amqtt 0.12 的类名（曾名 MQTTBroker）

            broker = Broker(self._build_config())
            await broker.start()
        except Exception as e:
            logger.warning(
                "内嵌 MQTT broker 启动失败（端口可能被占用），跳过内嵌 broker，外部 broker 模式不受影响: "
                f"{self._host}:{self._port}: {e}"
            )
            self._broker = None
            return False
        self._broker = broker
        logger.success(f"[MqttBroker] 内嵌 MQTT broker 已启动: {self._host}:{self._port}（匿名，内存态）")
        return True

    async def stop(self) -> None:
        """停止内嵌 broker（未启动则静默返回）。"""
        if not self.is_running:
            return
        try:
            await self._broker.shutdown()
        except Exception:
            logger.warning("[MqttBroker] 内嵌 MQTT broker 停止异常（忽略）", exc_info=True)
        self._broker = None
        logger.info(f"[MqttBroker] 内嵌 MQTT broker 已停止: {self._host}:{self._port}")

    # ── 内部 ────────────────────────────────────────────────────────────────

    def _port_available(self) -> bool:
        """探测监听端口是否空闲（不设 SO_REUSEADDR 的裸 bind）。"""
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            probe.bind((self._host, self._port))
            return True
        except OSError:
            return False
        finally:
            probe.close()

    def _build_config(self) -> dict[str, Any]:
        """精简配置：仅 TCP 监听 + 匿名认证，内存态。"""
        return {
            "listeners": {"default": {"type": "tcp", "bind": f"{self._host}:{self._port}"}},
            "plugins": dict(_BROKER_PLUGINS),
        }
