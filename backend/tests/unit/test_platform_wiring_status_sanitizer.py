"""平台链路「接线债」两项接线的回归锁。

1. P2-2 适配器七态可观测：/instances 列表与详情响应合并 adapter.get_status()
   只读内存快照（不做真实网络探测），registry 四态冻结期 RECONNECTING/ERROR 可见。
2. P1-6（日志面）LogSanitizer 接入 platform_logger 唯一出口：message/details
   落盘与 loguru 回流前统一脱敏。
"""
import pytest

from app.runtime.platform.platform_logger import platform_logger


# ------------------------------------------------------------------
# 1. /instances 响应合并适配器七态（P2-2）
# ------------------------------------------------------------------


@pytest.fixture()
def instances_app():
    from fastapi import FastAPI

    from app.api.v1.endpoints.platform import router as platform_router
    from app.runtime.platform.registry import create_instance, remove_instance

    app = FastAPI()
    app.include_router(platform_router, prefix="/api/v1")
    create_instance(
        "inst_obs_status",
        "qq_official",
        "七态可观测测试",
        {"app_id": "11111111", "app_secret": "obs-test-secret"},
    )
    yield app
    remove_instance("inst_obs_status")


async def _get_json(app: "FastAPI", path: str) -> dict:
    import httpx

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        resp = await client.get(f"/api/v1/platforms{path}")
    assert resp.status_code == 200
    return resp.json()


async def test_instances_list_contains_adapter_status_fields(instances_app):
    data = await _get_json(instances_app, "/instances")
    target = [d for d in data if d["id"] == "inst_obs_status"]
    assert target, "instance missing from list response"
    item = target[0]
    # 新建未启动的适配器处于 PENDING 态，七态字段透出
    assert item["adapterStatus"] == "pending"
    assert item["healthy"] is False
    assert item["adapterError"] == ""
    assert item["errorCount"] == 0
    # registry 四态字段保持原语义
    assert item["status"] == "pending"


async def test_instance_detail_reflects_adapter_reconnecting(instances_app):
    from app.runtime.platform.base import AdapterStatus
    from app.runtime.platform.registry import PlatformStatus, get_instance

    inst = get_instance("inst_obs_status")
    # registry 层冻结在 RUNNING（start/stop 之间的已知缺陷），适配器已断线重连
    inst.status = PlatformStatus.RUNNING
    inst.adapter.record_error("websocket connection lost")
    inst.adapter.update_status(AdapterStatus.RECONNECTING)  # record_error 置 ERROR 后重连中

    item = await _get_json(instances_app, "/instances/inst_obs_status")
    assert item["status"] == "running"  # registry 四态（保持现状，收敛属其他任务）
    assert item["adapterStatus"] == "reconnecting"  # 适配器七态可见
    assert item["healthy"] is False
    assert item["adapterError"] == "websocket connection lost"
    assert item["errorCount"] == 1


async def test_instance_status_snapshot_tolerates_missing_adapter(instances_app):
    from app.runtime.platform.registry import get_instance

    inst = get_instance("inst_obs_status")
    original = inst.adapter
    inst.adapter = None
    try:
        item = await _get_json(instances_app, "/instances/inst_obs_status")
        assert item["adapterStatus"] == ""
        assert item["healthy"] is None
    finally:
        inst.adapter = original


# ------------------------------------------------------------------
# 2. platform_logger 出口统一过 LogSanitizer（P1-6 日志面）
# ------------------------------------------------------------------


def _cleanup_logs(instance_id: str) -> None:
    platform_logger.clear_logs(instance_id)


def test_log_outlet_masks_bot_token_and_token_in_message():
    raw = (
        "请求失败: https://api.telegram.org/bot110201543:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw/getMe "
        "token=abcdefghijklmnopqrst"
    )
    entry = platform_logger.log(
        instance_id="inst_san_msg",
        level="error",
        event="request_failed",
        message=raw,
        adapter_type="telegram",
    )
    assert "AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw" not in entry["message"]
    assert "abcdefghijklmnopqrst" not in entry["message"]
    assert "bot***:***" in entry["message"]
    assert "token=***" in entry["message"]
    _cleanup_logs("inst_san_msg")


def test_log_outlet_masks_sensitive_details_recursively():
    entry = platform_logger.log(
        instance_id="inst_san_details",
        level="warning",
        event="token_refresh_failed",
        message="access_token 刷新失败",
        adapter_type="wechat_work",
        details={
            "corpsecret": "super-secret-value",
            "note": "联系 user@example.com 或 13812345678",
            "http": {
                "url": "https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid=ww1&corpsecret=abc123def456ghi789",
                "status": 500,
            },
            "attempt": 2,
        },
    )
    d = entry["details"]
    assert d["corpsecret"] == "***"  # 敏感键名整值遮蔽
    assert "user@example.com" not in d["note"]  # 邮箱脱敏
    assert "138****5678" in d["note"]  # 手机号脱敏
    assert "abc123def456ghi789" not in d["http"]["url"]  # URL 中 secret 脱敏
    assert d["http"]["status"] == 500  # 非敏感字段原样保留
    assert d["attempt"] == 2
    _cleanup_logs("inst_san_details")


def test_log_outlet_keeps_plain_message_intact():
    entry = platform_logger.log(
        instance_id="inst_san_plain",
        level="success",
        event="instance_started",
        message="平台实例已启动: 七态可观测测试",
        adapter_type="qq_official",
        details={"status": "running"},
    )
    assert entry["message"] == "平台实例已启动: 七态可观测测试"
    assert entry["details"] == {"status": "running"}
    _cleanup_logs("inst_san_plain")


def test_get_logs_reads_back_sanitized_entries():
    platform_logger.log(
        instance_id="inst_san_readback",
        level="info",
        event="message_received",
        message="收到消息: token=yoursecrettoken123456",
        adapter_type="test",
    )
    result = platform_logger.get_logs("inst_san_readback", limit=10)
    messages = [e["message"] for e in result["entries"]]
    assert any("token=***" in m for m in messages)
    assert not any("yoursecrettoken123456" in m for m in messages)
    _cleanup_logs("inst_san_readback")
