"""EmbeddedMqttBroker（W6-3 内嵌 MQTT broker）单元测试。

验证：
1. start() 后 amqtt MQTTClient 可连接 → 订阅 → 收到另一客户端 publish 的 JSON；
2. 端口被占用（如用户已装 mosquitto）时优雅降级：start() 不抛异常、
   is_running=False、进程不崩，先启动的 broker 不受影响；
3. stop() 幂等，start() 幂等。

端口选择：不用固定 1883（开发机可能装有 mosquitto 占用端口），
每次测试动态探测空闲端口，保证测试确定性；端口占用场景由「两个
broker 实例绑同一端口」构造，效果与外部 mosquitto 占用等价。

事件循环说明：amqtt 为纯 asyncio 实现，pytest-asyncio（asyncio_mode=auto）
的函数级事件循环即可直接承载 broker 与客户端，无需额外线程。
"""
from __future__ import annotations

import json
import socket

from app.infrastructure.mqtt.broker import EmbeddedMqttBroker

_HOST = "127.0.0.1"


def _free_port() -> int:
    """探测一个当前空闲的 TCP 端口（绑定后立即释放）。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((_HOST, 0))
        return probe.getsockname()[1]


async def _connect(client_id: str, port: int):
    """创建并连接一个 amqtt MQTTClient。"""
    from amqtt.client import MQTTClient

    client = MQTTClient(client_id=client_id)
    await client.connect(f"mqtt://{_HOST}:{port}/")
    return client


async def test_broker_roundtrip_pubsub():
    """启动 broker → 订阅 → 另一客户端 publish JSON → 断言收到 → stop。"""
    broker = EmbeddedMqttBroker(host=_HOST, port=_free_port())
    assert await broker.start() is True
    assert broker.is_running is True

    subscriber = await _connect("ut-mqtt-sub", broker.port)
    await subscriber.subscribe([("luominest/device/test/status", 1)])

    publisher = await _connect("ut-mqtt-pub", broker.port)
    payload = {"temperature": 26.4, "humidity": 58, "state": "online"}
    await publisher.publish(
        "luominest/device/test/status", json.dumps(payload).encode("utf-8"), qos=1
    )

    message = await subscriber.deliver_message(timeout_duration=5)
    assert message is not None
    assert message.topic == "luominest/device/test/status"
    assert json.loads(bytes(message.data)) == payload

    await publisher.disconnect()
    await subscriber.disconnect()
    await broker.stop()
    assert broker.is_running is False


async def test_broker_port_conflict_graceful_degradation():
    """同端口再启一个实例：不抛异常、is_running=False，进程不崩。"""
    first = EmbeddedMqttBroker(host=_HOST, port=_free_port())
    assert await first.start() is True
    try:
        second = EmbeddedMqttBroker(host=_HOST, port=first.port)
        assert await second.start() is False
        assert second.is_running is False
        # 降级不影响先启动的实例
        assert first.is_running is True
    finally:
        await first.stop()
    assert first.is_running is False


async def test_broker_lifecycle_idempotent():
    """未启动时 stop() 静默返回；start() 两次不重复起实例。"""
    broker = EmbeddedMqttBroker(host=_HOST, port=_free_port())
    assert broker.is_running is False
    await broker.stop()  # 未启动 stop 不抛
    assert await broker.start() is True
    assert await broker.start() is True  # 幂等
    assert broker.is_running is True
    await broker.stop()
    assert broker.is_running is False
