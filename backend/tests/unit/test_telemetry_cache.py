"""TelemetryCache（P0-4 遥测缓存）单元测试。

验证：
1. 三类 status topic（规范 device 段 / 固件直连简写 / 旧前缀 luominestai）均能
   落缓存并按 device_id 读取、列举；
2. TTL 过期过滤（get 返回 None 并惰性清理，list_devices 不含过期项）；
3. publish_command 的 topic/payload 形态与未连接时的拒绝；
4. broker 参数解析优先级（显式覆盖 > 内嵌 broker loopback > settings 外部配置）；
5. 端到端：真实内嵌 broker + paho 订阅 + amqtt 模拟设备发布 → 缓存可查；
   publish_command 经内嵌 broker 直达订阅方（「联通」的核心证明）。

端到端端口动态探测（避开开发机可能占用 1883 的 mosquitto），全部 loopback。
"""
from __future__ import annotations

import asyncio
import json
import socket
import time
from types import SimpleNamespace

import app.infrastructure.mqtt.telemetry_cache as telemetry_cache_module
from app.core.config import settings
from app.infrastructure.mqtt.broker import EmbeddedMqttBroker
from app.infrastructure.mqtt.telemetry_cache import (
    TelemetryCache,
    get_telemetry_cache,
    set_telemetry_cache,
)

_HOST = "127.0.0.1"


def _free_port() -> int:
    """探测一个当前空闲的 TCP 端口（绑定后立即释放）。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((_HOST, 0))
        return probe.getsockname()[1]


async def _feed(cache: TelemetryCache, topic: str, payload: dict) -> None:
    await cache.handle_message(topic, json.dumps(payload).encode("utf-8"), qos=1)


# ── 写入 / 读取 / 列举 ──────────────────────────────────────────────────────

async def test_handle_message_three_topic_forms():
    """规范形式 / 固件直连简写 / 旧前缀兼容三种 topic 均正确落缓存。"""
    cache = TelemetryCache(ttl=60)
    await _feed(cache, "luominest/device/esp32/status", {"temperature": 25.1})
    await _feed(cache, "luominest/p4/status", {"temperature": 26.2})  # 固件直连简写
    await _feed(cache, "luominestai/device/legacy1/status", {"battery": 88})

    assert cache.get("esp32")["payload"] == {"temperature": 25.1}
    assert cache.get("p4")["payload"] == {"temperature": 26.2}
    assert cache.get("legacy1")["payload"] == {"battery": 88}

    devices = cache.list_devices()
    assert set(devices) == {"esp32", "p4", "legacy1"}
    for entry in devices.values():
        assert isinstance(entry["payload"], dict)
        assert entry["ts"] > 0


async def test_get_missing_and_malformed_payload():
    """未知设备返回 None；非 JSON payload 宽容保留原始文本。"""
    cache = TelemetryCache(ttl=60)
    assert cache.get("no-such-device") is None

    await cache.handle_message("luominest/device/raw1/status", b"not-json", qos=0)
    entry = cache.get("raw1")
    assert entry is not None
    assert "not-json" in entry["payload"]["raw"]


async def test_get_unknown_device_id_topic_ignored():
    """解析不出 device_id 的 topic 不入缓存。"""
    cache = TelemetryCache(ttl=60)
    await cache.handle_message("unrelated/topic", b"{}", qos=0)
    assert cache.list_devices() == {}


# ── TTL 过期 ────────────────────────────────────────────────────────────────

async def test_ttl_expiry_filters_read_and_list():
    """超过 TTL 的条目 get 返回 None（惰性清理），list_devices 同步过滤。"""
    cache = TelemetryCache(ttl=30)
    await _feed(cache, "luominest/device/fresh/status", {"ok": 1})
    await _feed(cache, "luominest/device/stale/status", {"ok": 0})

    # 人为把 stale 的时间戳拨回 TTL 之前（确定性，不依赖 sleep 精度）
    cache._entries["stale"]["ts"] = time.time() - 31

    assert cache.get("fresh") is not None
    assert cache.get("stale") is None          # 过期 → None
    assert "stale" not in cache._entries       # 惰性清理已删除
    assert set(cache.list_devices()) == {"fresh"}


async def test_ttl_boundary_and_custom_ttl():
    """TTL 边界（等于 TTL 未过期）与自定义 ttl 生效。"""
    cache = TelemetryCache(ttl=10)
    assert cache.ttl == 10
    await _feed(cache, "luominest/device/d1/status", {"v": 1})
    cache._entries["d1"]["ts"] = time.time() - 10  # 恰好等于 TTL（> 判定，未过期）
    assert cache.get("d1") is not None
    cache._entries["d1"]["ts"] = time.time() - 10.5
    assert cache.get("d1") is None


# ── 命令下发 ────────────────────────────────────────────────────────────────

class _FakeMqttClient:
    """LuomiNestMqttClient 最小替身（is_connected/publish）。"""

    def __init__(self, connected: bool = True) -> None:
        self._connected = connected
        self.published: list[tuple[str, str, int]] = []

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def publish(self, topic: str, payload: str | bytes, qos: int = 1) -> bool:
        self.published.append((topic, str(payload), qos))
        return True


async def test_publish_command_topic_and_payload():
    """publish_command 发布到 luominest/device/{id}/command，payload 形态对齐适配器。"""
    cache = TelemetryCache()
    fake = _FakeMqttClient()
    cache._client = fake  # type: ignore[assignment]

    assert await cache.publish_command("esp32", '{"action":"switch","state":"on"}') is True
    topic, payload, qos = fake.published[0]
    assert topic == "luominest/device/esp32/command"
    assert json.loads(payload) == {"type": "command", "content": '{"action":"switch","state":"on"}'}
    assert qos == 1


async def test_publish_command_without_client_rejected():
    """未连接 broker（无客户端）时拒绝下发。"""
    cache = TelemetryCache()
    assert cache.is_connected is False
    assert await cache.publish_command("esp32", "on") is False


# ── broker 解析与生命周期 ───────────────────────────────────────────────────

def test_resolve_broker_priority():
    """显式覆盖 > 内嵌 broker loopback > settings 外部配置。"""
    cache = TelemetryCache(host="10.0.0.8", port=34567)

    class _FakeBroker:
        is_running = True
        port = 34568

    # 1) 显式覆盖最优先
    assert cache._resolve_broker(_FakeBroker()) == ("10.0.0.8", 34567)
    # 2) 内嵌 broker 在跑 → loopback + broker 端口
    cache2 = TelemetryCache()
    assert cache2._resolve_broker(_FakeBroker()) == ("127.0.0.1", 34568)
    # 3) 无内嵌 broker → settings 外部配置
    assert cache2._resolve_broker(None) == (settings.MQTT_BROKER_HOST, settings.MQTT_BROKER_PORT)


async def test_start_stop_lifecycle():
    """start 后处于对应模式且订阅模式齐全；stop 幂等并清空状态。"""
    cache = TelemetryCache(host=_HOST, port=_free_port())  # 指向空闲端口：不依赖真实 broker
    try:
        assert await cache.start() is True
        assert cache.embedded_mode is False  # 未传内嵌 broker → external 模式
        assert cache.subscription_patterns == [
            "luominest/device/+/status",
            "luominest/+/status",
            "luominestai/device/+/status",
            "luominestai/+/status",
        ]
        assert await cache.start() is True  # 幂等
    finally:
        await cache.stop()
    await cache.stop()  # 幂等
    assert cache._client is None
    assert cache.list_devices() == {}


# ── 端到端（真实内嵌 broker + paho + amqtt 模拟设备） ────────────────────────

async def test_end_to_end_with_embedded_broker():
    """内嵌 broker 在跑：设备发布 status → 缓存可查；publish_command 直达订阅方。"""
    broker = EmbeddedMqttBroker(host=_HOST, port=_free_port())
    assert await broker.start() is True
    cache = TelemetryCache(ttl=60)
    pub = sub = None
    try:
        assert await cache.start(embedded_broker=broker) is True
        assert cache.embedded_mode is True

        # 等待 paho 订阅就绪（订阅在连接建立后由客户端自动补订）
        for _ in range(50):
            if cache.is_connected:
                break
            await asyncio.sleep(0.1)
        assert cache.is_connected is True

        # 模拟 ESP32 经内嵌 broker 上报遥测
        from amqtt.client import MQTTClient

        pub = MQTTClient(client_id="ut-telemetry-pub")
        await pub.connect(f"mqtt://{_HOST}:{broker.port}/")
        await pub.publish(
            "luominest/device/esp32/status",
            json.dumps({"temperature": 26.4, "humidity": 58}).encode("utf-8"),
            qos=1,
        )

        # paho 订阅回调异步落缓存，轮询等待（最长 5 秒）
        entry = None
        for _ in range(50):
            entry = cache.get("esp32")
            if entry is not None:
                break
            await asyncio.sleep(0.1)
        assert entry is not None, "设备遥测未在 5 秒内进入缓存"
        assert entry["payload"] == {"temperature": 26.4, "humidity": 58}
        assert cache.list_devices()["esp32"]["payload"]["humidity"] == 58

        # 命令下发直通：订阅方经内嵌 broker 收到 publish_command 的消息
        sub = MQTTClient(client_id="ut-telemetry-sub")
        await sub.connect(f"mqtt://{_HOST}:{broker.port}/")
        await sub.subscribe([("luominest/device/esp32/command", 1)])
        assert await cache.publish_command("esp32", '{"action":"switch","state":"on"}') is True
        message = await sub.deliver_message(timeout_duration=5)
        assert message.topic == "luominest/device/esp32/command"
        command = json.loads(bytes(message.data))
        assert command["type"] == "command"
        assert json.loads(command["content"]) == {"action": "switch", "state": "on"}
    finally:
        for client in (pub, sub):
            if client is not None:
                await client.disconnect()
        await cache.stop()
        await broker.stop()


# ── 主题解析与 payload 容错（补强） ─────────────────────────────────────────

async def test_handle_message_legacy_shorthand_topic():
    """旧前缀下的固件直连简写（luominestai/{id}/status）同样落缓存。"""
    cache = TelemetryCache(ttl=60)
    await _feed(cache, "luominestai/p4legacy/status", {"rssi": -60})
    assert cache.get("p4legacy")["payload"] == {"rssi": -60}
    assert set(cache.list_devices()) == {"p4legacy"}


async def test_handle_message_non_dict_json_payload_wrapped_as_raw():
    """合法 JSON 但顶层非 dict（数组/数字/字符串）→ 统一包装为 {"raw": ...}。"""
    cache = TelemetryCache(ttl=60)
    await cache.handle_message("luominest/device/arr/status", json.dumps([1, 2, 3]).encode(), qos=1)
    await cache.handle_message("luominest/device/num/status", b"42", qos=0)
    await cache.handle_message("luominest/device/str/status", json.dumps("hello").encode(), qos=0)

    assert cache.get("arr")["payload"] == {"raw": "[1, 2, 3]"}
    assert cache.get("num")["payload"] == {"raw": "42"}
    assert cache.get("str")["payload"] == {"raw": "hello"}


async def test_handle_message_invalid_utf8_payload_replaced_not_raised():
    """非法 UTF-8 字节不炸回调：errors=replace 解码后按非 JSON 原文保留。"""
    cache = TelemetryCache(ttl=60)
    await cache.handle_message("luominest/device/bin1/status", b"\xff\xfe\xb0 not-json", qos=0)
    entry = cache.get("bin1")
    assert entry is not None
    assert "not-json" in entry["payload"]["raw"]
    assert "\ufffd" in entry["payload"]["raw"]  # 替换字符证明走了 replace 解码


async def test_same_device_latest_report_wins():
    """同一设备重复上报：仅保留最新 payload，条目不累积。"""
    cache = TelemetryCache(ttl=60)
    await _feed(cache, "luominest/device/esp32/status", {"temperature": 20.0})
    first_ts = cache.get("esp32")["ts"]
    await _feed(cache, "luominest/device/esp32/status", {"temperature": 21.5})

    entry = cache.get("esp32")
    assert entry["payload"] == {"temperature": 21.5}
    assert entry["ts"] >= first_ts
    assert len(cache._entries) == 1


async def test_get_and_list_devices_return_payload_copies():
    """get / list_devices 返回浅拷贝：外部改写返回值不污染缓存内部状态。"""
    cache = TelemetryCache(ttl=60)
    await _feed(cache, "luominest/device/esp32/status", {"temperature": 20.0})

    entry = cache.get("esp32")
    entry["payload"]["temperature"] = 999
    assert cache.get("esp32")["payload"]["temperature"] == 20.0

    devices = cache.list_devices()
    devices["esp32"]["payload"]["temperature"] = 888
    assert cache.get("esp32")["payload"]["temperature"] == 20.0


# ── 命令下发（补强：有客户端但未连接） ──────────────────────────────────────

async def test_publish_command_disconnected_client_rejected():
    """客户端存在但未连接：拒绝下发且不产生任何 publish。"""
    cache = TelemetryCache()
    fake = _FakeMqttClient(connected=False)
    cache._client = fake  # type: ignore[assignment]

    assert cache.is_connected is False
    assert await cache.publish_command("esp32", "on") is False
    assert fake.published == []


# ── start 模式判定与订阅（替身客户端，零网络） ──────────────────────────────

class _FakeLuomiNestClient:
    """LuomiNestMqttClient 最小替身：记录构造参数与订阅，不发起任何网络。"""

    def __init__(
        self,
        *,
        host: str,
        port: int = 1883,
        username: str = "",
        password: str = "",
        client_id: str = "",
        keepalive: int = 30,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.client_id = client_id
        self.on_message = None
        self.on_connect = None
        self.subscribed: list[tuple[str, int]] = []
        self.disconnected = False
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> bool:
        self._connected = True
        return True

    async def subscribe(self, topic: str, qos: int = 1) -> bool:
        self.subscribed.append((topic, qos))
        return True

    async def disconnect(self) -> None:
        self._connected = False
        self.disconnected = True


async def test_start_embedded_mode_loopback_and_full_subscription(monkeypatch):
    """内嵌 broker 在跑：loopback 直连 + 4 条订阅模式全量订阅 + 回调挂接。"""
    created: list[_FakeLuomiNestClient] = []

    def _factory(**kwargs):
        client = _FakeLuomiNestClient(**kwargs)
        created.append(client)
        return client

    monkeypatch.setattr(telemetry_cache_module, "LuomiNestMqttClient", _factory)
    cache = TelemetryCache(username="ut-user", password="ut-pass", client_id="ut-cache")
    try:
        assert await cache.start(
            embedded_broker=SimpleNamespace(is_running=True, port=34577)
        ) is True
        await asyncio.sleep(0)  # 让后台 connect 任务跑完，stop 时无挂起任务
        assert cache.mode == "embedded"
        assert cache.embedded_mode is True
        assert cache.is_connected is True

        client = created[0]
        assert (client.host, client.port) == ("127.0.0.1", 34577)  # 强制 loopback
        assert (client.username, client.password) == ("ut-user", "ut-pass")  # 显式凭证优先
        assert client.client_id == "ut-cache"
        assert client.on_message == cache.handle_message
        assert [t for t, _ in client.subscribed] == cache.subscription_patterns
        assert len(client.subscribed) == 4
        assert {q for _, q in client.subscribed} == {1}
    finally:
        await cache.stop()

    assert created[0].disconnected is True
    assert cache._client is None


async def test_start_stopped_embedded_broker_falls_to_external(monkeypatch):
    """内嵌 broker 未在跑：回退 external 模式，连接参数与凭证回落 settings。"""
    created: list[_FakeLuomiNestClient] = []

    def _factory(**kwargs):
        client = _FakeLuomiNestClient(**kwargs)
        created.append(client)
        return client

    monkeypatch.setattr(telemetry_cache_module, "LuomiNestMqttClient", _factory)
    cache = TelemetryCache()
    try:
        assert await cache.start(
            embedded_broker=SimpleNamespace(is_running=False, port=34578)
        ) is True
        await asyncio.sleep(0)
        assert cache.mode == "external"
        assert cache.embedded_mode is False

        client = created[0]
        assert (client.host, client.port) == (settings.MQTT_BROKER_HOST, settings.MQTT_BROKER_PORT)
        assert client.username == settings.MQTT_USERNAME
        assert client.password == settings.MQTT_PASSWORD
    finally:
        await cache.stop()


# ── 全局单例 ────────────────────────────────────────────────────────────────

def test_global_singleton_get_set_reset(monkeypatch):
    """get_telemetry_cache 懒初始化并复用；set_telemetry_cache 可替换/重置。"""
    monkeypatch.setattr(telemetry_cache_module, "_telemetry_cache", None)
    first = get_telemetry_cache()
    assert isinstance(first, TelemetryCache)
    assert get_telemetry_cache() is first  # 懒初始化后复用同一实例

    replacement = TelemetryCache(ttl=5)
    set_telemetry_cache(replacement)
    assert get_telemetry_cache() is replacement

    set_telemetry_cache(None)
    fresh = get_telemetry_cache()
    assert fresh is not replacement
    assert fresh.ttl == float(settings.TELEMETRY_CACHE_TTL)  # 缺省 TTL 来自 settings
