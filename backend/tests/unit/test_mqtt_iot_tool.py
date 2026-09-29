"""mqtt_iot_tool 路由（P0-4 联通改造）单元测试。

验证 iot_get_sensor_data / iot_send_command 的三级路由：
1. 读取：TelemetryCache 命中（不触碰平台注册表）→ mqtt_terminal 平台实例兜底
   → 均无数据时返回明确可操作的失败文案；
2. 下发：内嵌 broker 模式直连发布（不经平台实例）→ 平台实例兜底
   → 均无通道时返回明确可操作的失败文案；
3. tier 修正：registry 只定义 core/domain/meta，工具不再声明 standard。

平台注册表与全局遥测缓存单例均 monkeypatch 替身，无真实网络。
"""
from __future__ import annotations

import json
from typing import Any

import pytest

import app.infrastructure.mqtt.telemetry_cache as telemetry_cache_module
import app.runtime.platform.registry as platform_registry_module
from app.core.tools.builtin.mqtt_iot_tool import IoTGetSensorDataTool, IoTSendCommandTool
from app.infrastructure.mqtt.telemetry_cache import TelemetryCache
from app.runtime.platform.registry import PlatformInstance, PlatformStatus

# ── 替身 ────────────────────────────────────────────────────────────────────

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


class _FakeAdapter:
    """MQTTTerminalAdapter 最小替身（get_telemetry/send_message）。"""

    def __init__(self, telemetry: dict[str, Any] | None = None, send_ok: bool = True) -> None:
        self._telemetry = telemetry if telemetry is not None else {}
        self._send_ok = send_ok
        self.sent: list[tuple[str, str]] = []

    def get_telemetry(self, device_id: str | None = None) -> dict[str, Any]:
        if device_id:
            return {"device_id": device_id, "telemetry": self._telemetry}
        if not self._telemetry:
            return {}  # 无任何已注册设备（对齐真实适配器返回空表的行为）
        return {"dev-x": {"telemetry": self._telemetry}}

    async def send_message(self, response: Any, target: str) -> bool:
        self.sent.append((response.content, target))
        return self._send_ok


def _make_instance(adapter: _FakeAdapter) -> PlatformInstance:
    return PlatformInstance(
        instance_id="inst-mqtt",
        adapter_type="mqtt_terminal",
        name="MQTT 终端",
        config={},
        status=PlatformStatus.RUNNING,
        adapter=adapter,  # type: ignore[arg-type]
    )


@pytest.fixture
def cache_factory(monkeypatch: pytest.MonkeyPatch):
    """注入全新 TelemetryCache 单例，用例结束后恢复默认单例。"""

    def _install(cache: TelemetryCache) -> TelemetryCache:
        monkeypatch.setattr(telemetry_cache_module, "_telemetry_cache", cache)
        return cache

    yield _install
    telemetry_cache_module._telemetry_cache = None


async def _feed(cache: TelemetryCache, device_id: str, payload: dict[str, Any]) -> None:
    topic = f"luominest/device/{device_id}/status"
    await cache.handle_message(topic, json.dumps(payload).encode("utf-8"), qos=1)


# ── tier 修正 ───────────────────────────────────────────────────────────────

def test_tools_tier_is_domain():
    """registry 只定义 core/domain/meta，tier 不再是无效的 standard。"""
    assert IoTGetSensorDataTool().tier == "domain"
    assert IoTSendCommandTool().tier == "domain"


# ── 读取路由 ────────────────────────────────────────────────────────────────

async def test_get_sensor_cache_hit_single_device(cache_factory, monkeypatch):
    """指定 device_id 且缓存命中：直接返回遥测，不触碰平台注册表。"""
    cache = cache_factory(TelemetryCache(ttl=60))
    await _feed(cache, "esp32", {"temperature": 26.4, "humidity": 58})

    def _boom():
        raise AssertionError("缓存命中时不应查询平台注册表")

    monkeypatch.setattr(platform_registry_module, "list_instances", _boom)

    result = await IoTGetSensorDataTool().execute({"device_id": "esp32"})
    assert result.success is True
    data = json.loads(result.output)
    assert data["device_id"] == "esp32"
    assert data["temperature"] == 26.4
    assert data["source"] == "telemetry_cache"


async def test_get_sensor_cache_hit_list_all(cache_factory, monkeypatch):
    """不指定 device_id 且缓存非空：返回全部设备遥测。"""
    cache = cache_factory(TelemetryCache(ttl=60))
    await _feed(cache, "esp32", {"temperature": 26.4})
    await _feed(cache, "p4", {"battery": 88})
    monkeypatch.setattr(
        platform_registry_module, "list_instances",
        lambda: (_ for _ in ()).throw(AssertionError("不应查询平台注册表")),
    )

    result = await IoTGetSensorDataTool().execute({})
    assert result.success is True
    data = json.loads(result.output)
    assert data["count"] == 2
    assert {d["device_id"] for d in data["devices"]} == {"esp32", "p4"}


async def test_get_sensor_cache_miss_platform_fallback(cache_factory, monkeypatch):
    """缓存未命中 → mqtt_terminal 平台实例兜底路径返回适配器数据。"""
    cache_factory(TelemetryCache(ttl=60))  # 空缓存
    adapter = _FakeAdapter(telemetry={"temperature": 22.5})
    monkeypatch.setattr(platform_registry_module, "list_instances", lambda: [_make_instance(adapter)])

    # 指定设备
    result = await IoTGetSensorDataTool().execute({"device_id": "dev-x"})
    assert result.success is True
    data = json.loads(result.output)
    assert data["device_id"] == "dev-x"
    assert data["telemetry"]["temperature"] == 22.5

    # 不指定设备
    result_all = await IoTGetSensorDataTool().execute({})
    assert result_all.success is True
    assert "dev-x" in result_all.output


async def test_get_sensor_no_source_actionable_error(cache_factory, monkeypatch):
    """缓存为空且无运行中的平台实例：失败并给出可操作的排查建议。"""
    cache_factory(TelemetryCache(ttl=60))
    monkeypatch.setattr(platform_registry_module, "list_instances", lambda: [])

    result = await IoTGetSensorDataTool().execute({"device_id": "ghost"})
    assert result.success is False
    # 可操作性：指出上报 topic 与实例路径
    assert "luominest/" in result.error and "/status" in result.error
    assert "平台" in result.error or "实例" in result.error


async def test_get_sensor_platform_instance_without_data(cache_factory, monkeypatch):
    """平台实例存在但无数据：保持原有「无设备在线」提示。"""
    cache_factory(TelemetryCache(ttl=60))
    monkeypatch.setattr(
        platform_registry_module, "list_instances",
        lambda: [_make_instance(_FakeAdapter(telemetry={}))],
    )
    result = await IoTGetSensorDataTool().execute({})
    assert result.success is True
    assert "没有已上报传感器数据的设备在线" in result.output


# ── 下发路由 ────────────────────────────────────────────────────────────────

async def test_send_command_embedded_direct_publish(cache_factory, monkeypatch):
    """内嵌 broker 在跑且已连接：直连发布到 luominest/device/{id}/command。"""
    cache = cache_factory(TelemetryCache(ttl=60))
    cache._mode = "embedded"  # 模拟 start(embedded_broker) 后的内嵌模式
    fake_client = _FakeMqttClient()
    cache._client = fake_client  # type: ignore[assignment]

    def _boom():
        raise AssertionError("内嵌直发时不应查询平台注册表")

    monkeypatch.setattr(platform_registry_module, "list_instances", _boom)

    result = await IoTSendCommandTool().execute(
        {"device_id": "esp32", "command": '{"action":"switch","state":"on"}'}
    )
    assert result.success is True
    assert "esp32" in result.output
    topic, payload, qos = fake_client.published[0]
    assert topic == "luominest/device/esp32/command"
    assert json.loads(payload)["content"] == '{"action":"switch","state":"on"}'
    assert qos == 1


async def test_send_command_embedded_not_connected_falls_to_platform(cache_factory, monkeypatch):
    """内嵌模式但客户端未连接 → 降级走平台实例路径。"""
    cache = cache_factory(TelemetryCache(ttl=60))
    cache._mode = "embedded"
    cache._client = _FakeMqttClient(connected=False)  # type: ignore[assignment]

    adapter = _FakeAdapter()
    monkeypatch.setattr(platform_registry_module, "list_instances", lambda: [_make_instance(adapter)])

    result = await IoTSendCommandTool().execute({"device_id": "dev-x", "command": "on"})
    assert result.success is True
    assert adapter.sent == [("on", "dev-x")]


async def test_send_command_platform_fallback(cache_factory, monkeypatch):
    """非内嵌模式（外部 broker）：走 mqtt_terminal 平台实例下发。"""
    cache_factory(TelemetryCache(ttl=60))  # external 模式且未连接
    adapter = _FakeAdapter()
    monkeypatch.setattr(platform_registry_module, "list_instances", lambda: [_make_instance(adapter)])

    result = await IoTSendCommandTool().execute({"device_id": "dev-x", "command": "on"})
    assert result.success is True
    assert "dev-x" in result.output
    assert adapter.sent == [("on", "dev-x")]


async def test_send_command_no_channel_actionable_error(cache_factory, monkeypatch):
    """无内嵌直发通道且无平台实例：失败并给出可操作的排查建议。"""
    cache_factory(TelemetryCache(ttl=60))
    monkeypatch.setattr(platform_registry_module, "list_instances", lambda: [])

    result = await IoTSendCommandTool().execute({"device_id": "esp32", "command": "on"})
    assert result.success is False
    assert "内嵌" in result.error and "实例" in result.error


async def test_send_command_missing_arguments():
    """缺参直接失败（不触达任何链路）。"""
    result = await IoTSendCommandTool().execute({"device_id": "", "command": ""})
    assert result.success is False
    assert "device_id" in result.error and "command" in result.error
