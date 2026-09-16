"""智能家居设备列表单元测试（零网络）。

覆盖两块：
- HomeAssistantAdapter.list_devices：HA REST /api/states → 统一设备模型的映射
  （域过滤 / friendly_name / unavailable 判离线 / 属性透传 / 支持动作标注）、
  HTTP 客户端未初始化 / 请求失败 / 响应格式异常时的空列表降级（不抛错）；
- smart_home 聚合逻辑 _aggregate_capability：单实例异常跳过并计入 skipped、
  未实现能力计入 unsupported、来源 instance_id / adapter_type 标注。

全部请求用 httpx.MockTransport 模拟，不发真请求。
"""
from __future__ import annotations

import httpx
import pytest

from app.api.v1.endpoints import smart_home
from app.runtime.platform.adapters.home_assistant import HomeAssistantAdapter


# ── 测试替身 ───────────────────────────────────────────────────────────────────


class _FakeInstance:
    """平台实例替身（鸭子类型，字段与 PlatformInstance 对齐）。"""

    def __init__(self, instance_id: str, adapter_type: str, adapter) -> None:
        self.instance_id = instance_id
        self.adapter_type = adapter_type
        self.adapter = adapter
        self.name = instance_id
        self.enabled = True


class _ExplodingAdapter:
    """list_devices 必抛异常的假适配器（模拟实例离线 / 网络故障）。"""

    async def list_devices(self):
        raise RuntimeError("connection refused")


class _GoodAdapter:
    """返回一条标准化设备的假适配器（模拟 mqtt_terminal）。"""

    async def list_devices(self):
        return [{"device_id": "esp32-1", "name": "客厅终端", "online": True}]


class _NoMethodAdapter:
    """没有 list_devices 能力的假适配器（模拟不支持该能力的平台）。"""


def _ha_states_payload() -> list[dict]:
    """模拟 HA GET /api/states 返回：覆盖可控域 / 传感域 / 非设备域 / 离线实体。"""
    return [
        {
            "entity_id": "light.living_room",
            "state": "on",
            "attributes": {"friendly_name": "客厅灯", "brightness": 180, "room": "客厅"},
        },
        {
            "entity_id": "switch.plug",
            "state": "off",
            "attributes": {"friendly_name": "智能插座"},
        },
        {
            "entity_id": "climate.ac",
            "state": "cool",
            "attributes": {"friendly_name": "空调", "temperature": 26.0, "area_id": "bedroom"},
        },
        {
            "entity_id": "cover.garage",
            "state": "closed",
            "attributes": {},
        },
        {
            "entity_id": "sensor.temperature",
            "state": "23.5",
            "attributes": {"friendly_name": "温度", "unit_of_measurement": "°C"},
        },
        {
            "entity_id": "binary_sensor.door",
            "state": "unavailable",
            "attributes": {"friendly_name": "门磁"},
        },
        {
            "entity_id": "fan.bedroom_fan",
            "state": "on",
            "attributes": {"friendly_name": "卧室风扇"},
        },
        {
            "entity_id": "media_player.tv",
            "state": "playing",
            "attributes": {"friendly_name": "电视"},
        },
        # 非设备域：应被过滤
        {"entity_id": "automation.morning", "state": "on", "attributes": {}},
        {"entity_id": "script.cleanup", "state": "off", "attributes": {}},
        {"entity_id": "sun.sun", "state": "above_horizon", "attributes": {}},
        {"entity_id": "zone.home", "state": "0", "attributes": {}},
    ]


def _make_ha_adapter(handler) -> HomeAssistantAdapter:
    """构造带 MockTransport HTTP 客户端的 HA 适配器（不经 start()，不发真请求）。"""
    adapter = HomeAssistantAdapter()
    adapter.set_instance_id("ha-test-instance")
    adapter.initialize({"ha_url": "http://ha.local:8123", "ha_token": "test-token"})
    adapter._http_client = httpx.AsyncClient(
        base_url="http://ha.local:8123",
        headers={"Authorization": "Bearer test-token"},
        transport=httpx.MockTransport(handler),
    )
    return adapter


# ── HA 设备列表映射 ────────────────────────────────────────────────────────────


@pytest.fixture
async def ha_adapter():
    """正常返回 HA 状态的适配器（测试结束后关闭 HTTP 客户端）。"""
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["auth"] = request.headers.get("authorization", "")
        return httpx.Response(200, json=_ha_states_payload())

    adapter = _make_ha_adapter(handler)
    yield adapter, captured
    await adapter._http_client.aclose()


class TestHomeAssistantListDevices:
    """list_devices 映射与降级行为。"""

    async def test_maps_states_to_unified_device_model(self, ha_adapter):
        adapter, captured = ha_adapter
        devices = await adapter.list_devices()

        # 复用 Bearer 认证请求 REST API
        assert captured["path"] == "/api/states"
        assert captured["auth"] == "Bearer test-token"

        # 可控 + 传感域保留，automation/script/sun/zone 被过滤
        device_ids = [d["device_id"] for d in devices]
        assert device_ids == [
            "light.living_room",
            "switch.plug",
            "climate.ac",
            "cover.garage",
            "sensor.temperature",
            "binary_sensor.door",
            "fan.bedroom_fan",
            "media_player.tv",
        ]

        light = devices[0]
        assert light["name"] == "客厅灯"
        assert light["state"] == "on"
        assert light["online"] is True
        assert light["status"]["brightness"] == 180
        assert light["location"] == "客厅"
        assert light["domain"] == "light"
        assert light["supported_actions"] == ["turn_on", "turn_off", "toggle", "set_brightness"]
        assert light["source"] == "home_assistant"
        assert light["instance_id"] == "ha-test-instance"

    async def test_unavailable_entity_is_offline(self, ha_adapter):
        adapter, _ = ha_adapter
        devices = await adapter.list_devices()

        door = next(d for d in devices if d["device_id"] == "binary_sensor.door")
        assert door["online"] is False
        assert door["state"] == "unavailable"

    async def test_sensor_domain_is_read_only(self, ha_adapter):
        adapter, _ = ha_adapter
        devices = await adapter.list_devices()

        sensor = next(d for d in devices if d["device_id"] == "sensor.temperature")
        assert sensor["supported_actions"] == []

        climate = next(d for d in devices if d["device_id"] == "climate.ac")
        assert "set_temperature" in climate["supported_actions"]

    async def test_fallback_to_entity_id_without_friendly_name(self, ha_adapter):
        adapter, _ = ha_adapter
        devices = await adapter.list_devices()

        cover = next(d for d in devices if d["device_id"] == "cover.garage")
        assert cover["name"] == "cover.garage"
        assert cover["location"] == ""

    async def test_missing_fields_tolerated(self):
        """实体缺 entity_id / attributes 非法时不炸，逐条跳过或容错。"""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json=[
                    {"entity_id": "light.ok", "state": "on", "attributes": {"friendly_name": "OK"}},
                    {"state": "on"},  # 缺 entity_id → 跳过
                    "not-a-dict-entry",  # 非法条目 → 跳过
                    {"entity_id": "fan.broken", "state": "on", "attributes": "bad"},  # 属性非法 → 容错为空
                ],
            )

        adapter = _make_ha_adapter(handler)
        try:
            devices = await adapter.list_devices()
            assert [d["device_id"] for d in devices] == ["light.ok", "fan.broken"]
            assert devices[1]["status"] == {}
            assert devices[1]["name"] == "fan.broken"
        finally:
            await adapter._http_client.aclose()

    async def test_no_http_client_returns_empty(self):
        """未 start()（无 HTTP 客户端）→ 空列表 + 不抛错。"""
        adapter = HomeAssistantAdapter()
        adapter.set_instance_id("ha-idle")
        adapter.initialize({"ha_url": "http://ha.local:8123", "ha_token": "t"})
        assert await adapter.list_devices() == []

    async def test_http_error_returns_empty(self):
        """HA 5xx → 空列表 + 不抛错（聚合端点不被拖垮）。"""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, json={"message": "unavailable"})

        adapter = _make_ha_adapter(handler)
        try:
            assert await adapter.list_devices() == []
        finally:
            await adapter._http_client.aclose()

    async def test_transport_error_returns_empty(self):
        """连接失败（超时/拒连）→ 空列表 + 不抛错。"""

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused")

        adapter = _make_ha_adapter(handler)
        try:
            assert await adapter.list_devices() == []
        finally:
            await adapter._http_client.aclose()

    async def test_non_list_payload_returns_empty(self):
        """响应不是数组（如网关错误页转 JSON object）→ 空列表。"""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"unexpected": "shape"})

        adapter = _make_ha_adapter(handler)
        try:
            assert await adapter.list_devices() == []
        finally:
            await adapter._http_client.aclose()


# ── smart_home 聚合跳过逻辑 ────────────────────────────────────────────────────


class TestAggregateCapability:
    """_aggregate_capability 的统一容错与来源标注。"""

    async def test_aggregates_and_annotates_source(self, monkeypatch):
        instances = [_FakeInstance("inst-mqtt", "mqtt_terminal", _GoodAdapter())]
        monkeypatch.setattr(smart_home, "list_instances", lambda: instances)

        items, unsupported, skipped = await smart_home._aggregate_capability("list_devices", "devices")

        assert len(items) == 1
        assert items[0]["device_id"] == "esp32-1"
        assert items[0]["instance_id"] == "inst-mqtt"
        assert items[0]["adapter_type"] == "mqtt_terminal"
        assert unsupported == []
        assert skipped == []

    async def test_skips_instance_on_adapter_exception(self, monkeypatch):
        """实例离线 / 适配器异常 → 跳过该实例计入 skipped，不影响其它实例。"""
        instances = [
            _FakeInstance("inst-bad", "home_assistant", _ExplodingAdapter()),
            _FakeInstance("inst-good", "mqtt_terminal", _GoodAdapter()),
        ]
        monkeypatch.setattr(smart_home, "list_instances", lambda: instances)

        items, unsupported, skipped = await smart_home._aggregate_capability("list_devices", "devices")

        assert [d["device_id"] for d in items] == ["esp32-1"]
        assert unsupported == []
        assert skipped == [
            {"instance_id": "inst-bad", "adapter_type": "home_assistant", "reason": "connection refused"}
        ]

    async def test_records_unsupported_capability(self, monkeypatch):
        """未实现该能力的适配器 → 计入 unsupported，不视为异常。"""
        instances = [
            _FakeInstance("inst-no", "xiaomi_iot", _NoMethodAdapter()),
            _FakeInstance("inst-good", "mqtt_terminal", _GoodAdapter()),
        ]
        monkeypatch.setattr(smart_home, "list_instances", lambda: instances)

        items, unsupported, skipped = await smart_home._aggregate_capability("list_scenes", "scenes")

        assert items == []
        # _NoMethodAdapter 与只实现 list_devices 的 _GoodAdapter 均无场景能力
        assert unsupported == ["xiaomi_iot", "mqtt_terminal"]
        assert skipped == []

    async def test_skips_instance_without_adapter(self, monkeypatch):
        """实例适配器未就绪（adapter=None）→ 计入 skipped。"""
        instances = [_FakeInstance("inst-idle", "mqtt_terminal", None)]
        monkeypatch.setattr(smart_home, "list_instances", lambda: instances)

        items, unsupported, skipped = await smart_home._aggregate_capability("list_devices", "devices")

        assert items == []
        assert unsupported == []
        assert skipped == [
            {"instance_id": "inst-idle", "adapter_type": "mqtt_terminal", "reason": "adapter_not_ready"}
        ]

    async def test_non_list_result_ignored(self, monkeypatch):
        """适配器返回非列表（异常实现）→ 不贡献条目也不炸。"""

        class _BadShapeAdapter:
            async def list_devices(self):
                return {"not": "a list"}

        instances = [_FakeInstance("inst-shape", "xiaomi_iot", _BadShapeAdapter())]
        monkeypatch.setattr(smart_home, "list_instances", lambda: instances)

        items, unsupported, skipped = await smart_home._aggregate_capability("list_devices", "devices")

        assert items == []
        assert unsupported == []
        assert skipped == []

    async def test_preserves_existing_instance_id(self, monkeypatch):
        """适配器已自带 instance_id（如 mqtt_terminal）时聚合不覆盖。"""

        class _SelfAnnotatedAdapter:
            async def list_devices(self):
                return [{"device_id": "d1", "instance_id": "self-annotated"}]

        instances = [_FakeInstance("inst-x", "mqtt_terminal", _SelfAnnotatedAdapter())]
        monkeypatch.setattr(smart_home, "list_instances", lambda: instances)

        items, _, _ = await smart_home._aggregate_capability("list_devices", "devices")

        assert items[0]["instance_id"] == "self-annotated"


# ── devices 端点响应形状 ───────────────────────────────────────────────────────


class TestDevicesEndpointShape:
    """devices 端点响应包含来源标注与 skipped 列表。"""

    async def test_endpoint_returns_devices_with_skipped(self, monkeypatch):
        instances = [
            _FakeInstance("inst-bad", "home_assistant", _ExplodingAdapter()),
            _FakeInstance("inst-good", "mqtt_terminal", _GoodAdapter()),
        ]
        monkeypatch.setattr(smart_home, "list_instances", lambda: instances)

        response = await smart_home.list_devices()

        assert response["code"] == 0
        data = response["data"]
        assert data["total"] == 1
        # 实例来源标注（instance_id / adapter_type 由聚合层补齐）
        assert data["devices"][0]["instance_id"] == "inst-good"
        assert data["devices"][0]["adapter_type"] == "mqtt_terminal"
        assert data["skipped_instances"][0]["adapter_type"] == "home_assistant"
