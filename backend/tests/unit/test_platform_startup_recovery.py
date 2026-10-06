"""P1-2 / P1-4 平台生命周期修复验收（链路审查 C 2026-10-05）。

P1-2 重启自恢复：应用启动时 registry 按持久化 enable 开关自动拉起实例——
  enabled 实例被并发 start_instance（mock 适配器断言）、disabled 实例
  不被拉起、失败实例保留 ERROR 态并写实例日志（UI 经既有字段可见）。
P1-4 HA start() 立即返回：home_assistant 适配器 start() 不再内联等待
  连接循环，连接/监听放后台任务；首连失败调度后台重连，stop() 可回收。
"""
import asyncio

import pytest

from app.runtime.platform import registry
from app.runtime.platform.adapters.home_assistant import HomeAssistantAdapter
from app.runtime.platform.base import BasePlatformAdapter, PlatformResponse
from app.runtime.platform.infrastructure.reconnect import ReconnectState


# ─── 测试用 mock 适配器 ───


class _FakeAdapter(BasePlatformAdapter):
    """记录 start/stop 调用次数的最小适配器，可注入启动失败。"""

    platform_name = "fake_recovery"

    def __init__(self) -> None:
        super().__init__()
        self.start_calls = 0
        self.stop_calls = 0
        self.start_error: str | None = None

    async def send_message(self, response: PlatformResponse, target: str) -> bool:
        return True

    async def start(self) -> None:
        self.start_calls += 1
        if self.start_error:
            raise RuntimeError(self.start_error)

    async def stop(self) -> None:
        self.stop_calls += 1


@pytest.fixture()
def clean_registry():
    """保存/恢复 registry 全局态，避免污染其他测试。"""
    saved_types = dict(registry._adapter_types)
    saved_instances = dict(registry._instances)
    yield
    registry._adapter_types.clear()
    registry._adapter_types.update(saved_types)
    registry._instances.clear()
    registry._instances.update(saved_instances)


@pytest.fixture()
def platform_log_events(monkeypatch):
    """替换 registry 内的 platform_logger，记录实例级事件（不落盘）。"""
    events: list[dict] = []

    class _Recorder:
        def log(self, instance_id, level, event, message, adapter_type="", details=None):
            events.append({"instance_id": instance_id, "level": level, "event": event})

    monkeypatch.setattr(registry, "platform_logger", _Recorder())
    return events


def _register_fake_type() -> None:
    registry.register_adapter_type(
        "fake_recovery",
        "Fake Recovery",
        "startup recovery test adapter",
        _FakeAdapter,
    )


def _create_instance(instance_id: str, enable: bool) -> _FakeAdapter:
    registry.create_instance(
        instance_id=instance_id,
        adapter_type="fake_recovery",
        name=f"inst-{instance_id}",
        config={"enable": enable},
    )
    return registry.get_instance(instance_id).adapter


# ─── P1-2：重启自恢复 ───


async def test_enabled_instances_auto_started(clean_registry, platform_log_events):
    """enable=True 实例在启动恢复时被自动拉起并置 RUNNING。"""
    _register_fake_type()
    a1 = _create_instance("recov_enabled_1", enable=True)
    a2 = _create_instance("recov_enabled_2", enable=True)
    # 模拟 _load_persisted_instances 的落位：enabled 实例加载后置 STOPPED
    for iid in ("recov_enabled_1", "recov_enabled_2"):
        registry.get_instance(iid).status = registry.PlatformStatus.STOPPED

    results = await registry.auto_start_enabled_instances()

    assert results == {"recov_enabled_1": True, "recov_enabled_2": True}
    assert a1.start_calls == 1
    assert a2.start_calls == 1
    assert registry.get_instance("recov_enabled_1").status == registry.PlatformStatus.RUNNING
    assert registry.get_instance("recov_enabled_2").status == registry.PlatformStatus.RUNNING
    events = {e["event"] for e in platform_log_events}
    assert "instance_started" in events  # 恢复结果有实例级事件


async def test_disabled_instances_not_started(clean_registry, platform_log_events):
    """enable=False 实例不被自动拉起，状态保持 PENDING。"""
    _register_fake_type()
    disabled = _create_instance("recov_disabled", enable=False)
    enabled = _create_instance("recov_enabled", enable=True)

    results = await registry.auto_start_enabled_instances()

    assert results == {"recov_enabled": True}
    assert disabled.start_calls == 0
    assert registry.get_instance("recov_disabled").status == registry.PlatformStatus.PENDING
    assert enabled.start_calls == 1


async def test_failed_start_keeps_error_state_and_logs(clean_registry, platform_log_events):
    """启动失败的实例保留 ERROR 态（UI 经既有 status/errorMessage 可见）并写日志。"""
    _register_fake_type()
    bad = _create_instance("recov_bad", enable=True)
    bad.start_error = "boom"

    results = await registry.auto_start_enabled_instances()

    assert results == {"recov_bad": False}
    inst = registry.get_instance("recov_bad")
    assert inst.status == registry.PlatformStatus.ERROR
    assert "boom" in inst.error_message
    events = {e["event"] for e in platform_log_events}
    assert "start_failed" in events


async def test_auto_start_skips_running_instances(clean_registry, platform_log_events):
    """已 RUNNING 的实例不重复拉起（幂等，二次调用为空操作）。"""
    _register_fake_type()
    running = _create_instance("recov_running", enable=True)
    registry.get_instance("recov_running").status = registry.PlatformStatus.RUNNING

    results = await registry.auto_start_enabled_instances()

    assert results == {}
    assert running.start_calls == 0


async def test_auto_start_empty_registry_returns_empty(clean_registry):
    """无可拉起实例时返回空映射（lifespan 日志不报错）。"""
    results = await registry.auto_start_enabled_instances()
    assert results == {}


# ─── P1-4：HA start() 立即返回，后台任务存活 ───


def _ha_adapter() -> HomeAssistantAdapter:
    adapter = HomeAssistantAdapter()
    adapter.initialize({"ha_url": "http://ha.example:8123", "ha_token": "token-x"})
    return adapter


async def test_ha_start_returns_immediately_and_background_task_alive():
    """start() 不等待连接循环即可返回，且后台连接任务存活。"""
    adapter = _ha_adapter()
    entered = asyncio.Event()

    async def _fake_connect_websocket():
        # 模拟真实的"连接成功后长期监听不返回"
        entered.set()
        await asyncio.sleep(3600)

    adapter._connect_websocket = _fake_connect_websocket  # type: ignore[method-assign]

    # start() 若仍内联等待监听循环，此处将超时失败
    await asyncio.wait_for(adapter.start(), timeout=1.0)

    assert adapter._ws_task is not None
    await asyncio.wait_for(entered.wait(), timeout=1.0)
    assert not adapter._ws_task.done()  # 后台任务存活

    await adapter.stop()
    assert adapter._ws_task is None or adapter._ws_task.done()
    assert adapter.get_status()["status"] == "stopped"


async def test_ha_first_connect_failure_schedules_background_reconnect():
    """首连失败不抛向调用方，转后台重连调度；stop() 可回收重连任务。"""
    adapter = _ha_adapter()

    async def _failing_connect_websocket():
        raise RuntimeError("connection refused")

    adapter._connect_websocket = _failing_connect_websocket  # type: ignore[method-assign]

    await asyncio.wait_for(adapter.start(), timeout=1.0)

    # 等后台任务完成失败处理并调度重连
    for _ in range(100):
        if adapter._reconnect_task is not None:
            break
        await asyncio.sleep(0.01)
    assert adapter._reconnect_task is not None
    assert not adapter._reconnect_task.done()

    await adapter.stop()
    assert adapter._reconnect_task is None  # 重连任务已随 stop 回收


async def test_ha_stop_during_connect_does_not_schedule_reconnect():
    """主动 stop() 引起的任务取消不得触发重连调度（防止停止后幽灵复活）。"""
    adapter = _ha_adapter()
    entered = asyncio.Event()

    async def _fake_connect_websocket():
        entered.set()
        await asyncio.sleep(3600)

    adapter._connect_websocket = _fake_connect_websocket  # type: ignore[method-assign]

    await asyncio.wait_for(adapter.start(), timeout=1.0)
    await asyncio.wait_for(entered.wait(), timeout=1.0)

    await adapter.stop()

    assert adapter._reconnect_task is None
    assert adapter.reconnect_state in (ReconnectState.STOPPED, ReconnectState.IDLE)
