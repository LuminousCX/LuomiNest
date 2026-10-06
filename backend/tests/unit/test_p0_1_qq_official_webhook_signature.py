"""P0-1 QQ 官方机器人 Webhook Ed25519 验签的单元测试。

覆盖：
1. 合法签名（官方种子推导 + timestamp+原始body 签名）→ 验签通过、事件正常分发
2. 非法签名（密钥不符 / body 被篡改 / hex 格式非法）→ 拒绝且不触发业务逻辑
3. 缺失 X-Signature-Ed25519 / X-Signature-Timestamp → 拒绝（含旧式无验签材料调用）
4. 未配置 secret（app_secret / webhook_secret 均空）→ fail-closed 拒绝
5. platform endpoint 接线黑盒：验签通过 200 / 验签失败或缺头 401
"""
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.runtime.platform.adapters.qq_official import LuomiNestQQOfficialAdapter

# 官方文档示例 secret（16 字节，会触发种子翻倍推导路径）
_SECRET = "DG5g3B4j9X2KOErG"
_TIMESTAMP = "1725442341"

_GROUP_EVENT = {
    "event_type": "GROUP_AT_MESSAGE_CREATE",
    "event": {
        "group_openid": "G888",
        "id": "ROBOT1.0_abc",
        "author": {"member_openid": "U10001", "username": "群友甲"},
        "content": "在吗",
    },
}


def _derive_seed(secret: str) -> bytes:
    """官方 Go 示例同款种子推导：反复翻倍至 >=32 字节后截取 32 字节。"""
    seed = secret.encode("utf-8")
    while len(seed) < 32:
        seed = seed * 2
    return seed[:32]


def _sign(secret: str, timestamp: str, body: bytes) -> str:
    """按官方算法生成事件推送签名（hex），供测试构造合法/伪造请求。"""
    key = Ed25519PrivateKey.from_private_bytes(_derive_seed(secret))
    return key.sign(timestamp.encode("utf-8") + body).hex()


def _event_body() -> bytes:
    return json.dumps(_GROUP_EVENT).encode("utf-8")


def _make_adapter(secret: str = _SECRET) -> LuomiNestQQOfficialAdapter:
    adapter = LuomiNestQQOfficialAdapter()
    adapter.initialize({"app_id": "11111111", "app_secret": secret})
    return adapter


def _capture_emit(monkeypatch, adapter: LuomiNestQQOfficialAdapter) -> list:
    """替换 _emit_message 捕获分发事件，避免触达真实路由器。"""
    seen: list = []

    async def fake_emit(msg):
        seen.append(msg)
        return None

    monkeypatch.setattr(adapter, "_emit_message", fake_emit)
    return seen


# ------------------------------------------------------------------
# 1. 合法签名
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_webhook_valid_signature_dispatches_group_message(monkeypatch):
    adapter = _make_adapter()
    seen = _capture_emit(monkeypatch, adapter)

    body = _event_body()
    sig = _sign(_SECRET, _TIMESTAMP, body)
    handled = await adapter.handle_webhook(
        _GROUP_EVENT, signature=sig, timestamp=_TIMESTAMP, raw_body=body
    )

    assert handled is True, "合法签名必须放行"
    assert len(seen) == 1, "验签通过后事件必须进入分发"
    assert seen[0].group_id == "G888"
    assert seen[0].user_id == "U10001"
    assert seen[0].content == "在吗"
    assert seen[0].is_group is True


@pytest.mark.asyncio
async def test_webhook_valid_signature_with_long_secret(monkeypatch):
    """secret 已 >= 32 字节时官方算法直接截取前 32 字节作种子。"""
    long_secret = "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0"  # 40 字节
    adapter = _make_adapter(long_secret)
    seen = _capture_emit(monkeypatch, adapter)

    body = _event_body()
    sig = _sign(long_secret, _TIMESTAMP, body)
    assert (
        await adapter.handle_webhook(
            _GROUP_EVENT, signature=sig, timestamp=_TIMESTAMP, raw_body=body
        )
        is True
    )
    assert len(seen) == 1


# ------------------------------------------------------------------
# 2. 非法签名
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_webhook_wrong_key_signature_rejected(monkeypatch):
    adapter = _make_adapter()
    seen = _capture_emit(monkeypatch, adapter)

    body = _event_body()
    forged = _sign("attacker-secret", _TIMESTAMP, body)
    handled = await adapter.handle_webhook(
        _GROUP_EVENT, signature=forged, timestamp=_TIMESTAMP, raw_body=body
    )

    assert handled is False, "非本机 secret 派生密钥的签名必须拒绝"
    assert seen == [], "验签失败不得触发任何业务逻辑"


@pytest.mark.asyncio
async def test_webhook_tampered_body_rejected(monkeypatch):
    """签名合法但 body 被篡改（尾部追加空格）→ 拒绝。"""
    adapter = _make_adapter()
    seen = _capture_emit(monkeypatch, adapter)

    body = _event_body()
    sig = _sign(_SECRET, _TIMESTAMP, body)
    handled = await adapter.handle_webhook(
        _GROUP_EVENT, signature=sig, timestamp=_TIMESTAMP, raw_body=body + b" "
    )

    assert handled is False, "body 与签名不一致必须拒绝"
    assert seen == []


@pytest.mark.asyncio
async def test_webhook_malformed_hex_signature_rejected(monkeypatch):
    adapter = _make_adapter()
    seen = _capture_emit(monkeypatch, adapter)

    handled = await adapter.handle_webhook(
        _GROUP_EVENT,
        signature="not-a-hex-signature!!",
        timestamp=_TIMESTAMP,
        raw_body=_event_body(),
    )

    assert handled is False, "hex 解码失败必须 fail-closed 拒绝"
    assert seen == []


# ------------------------------------------------------------------
# 3. 缺失签名头
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_webhook_missing_signature_headers_rejected(monkeypatch):
    adapter = _make_adapter()
    seen = _capture_emit(monkeypatch, adapter)

    body = _event_body()
    sig = _sign(_SECRET, _TIMESTAMP, body)

    # 缺 X-Signature-Ed25519
    assert (
        await adapter.handle_webhook(
            _GROUP_EVENT, signature="", timestamp=_TIMESTAMP, raw_body=body
        )
        is False
    )
    # 缺 X-Signature-Timestamp
    assert (
        await adapter.handle_webhook(
            _GROUP_EVENT, signature=sig, timestamp="", raw_body=body
        )
        is False
    )
    # 旧式无验签材料的调用（endpoint 未升级/直调）也必须拒绝
    assert await adapter.handle_webhook(_GROUP_EVENT) is False
    assert seen == [], "缺头路径不得触发任何业务逻辑"


# ------------------------------------------------------------------
# 4. 未配置 secret → fail-closed
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_webhook_rejected_when_secret_not_configured(monkeypatch):
    adapter = _make_adapter("")  # app_secret / webhook_secret 均未配置
    seen = _capture_emit(monkeypatch, adapter)

    body = _event_body()
    # 签名本身格式合法（由任意密钥生成）也必须拒绝
    sig = _sign("whatever-secret", _TIMESTAMP, body)
    handled = await adapter.handle_webhook(
        _GROUP_EVENT, signature=sig, timestamp=_TIMESTAMP, raw_body=body
    )

    assert handled is False, "未配置 secret 必须 fail-closed 拒绝"
    assert seen == []


def test_webhook_secret_fallback_to_app_secret():
    """webhook_secret 缺省回退 app_secret；显式配置时优先生效。"""
    adapter = _make_adapter(_SECRET)
    assert adapter._webhook_secret == _SECRET

    adapter2 = LuomiNestQQOfficialAdapter()
    adapter2.initialize({"app_id": "11111111", "app_secret": "a", "webhook_secret": "b"})
    assert adapter2._webhook_secret == "b"


@pytest.mark.asyncio
async def test_start_warns_fail_closed_when_secret_missing(monkeypatch):
    """secret 缺失时启动即告警（fail-closed），提示 webhook 事件将被拒绝。"""
    from loguru import logger

    warned: list[str] = []
    monkeypatch.setattr(
        logger, "warning", lambda msg, *a, **k: warned.append(str(msg))
    )

    adapter = LuomiNestQQOfficialAdapter()
    adapter.initialize({"app_id": "", "app_secret": ""})
    await adapter.start()

    assert any("fail-closed" in w for w in warned), "secret 缺失必须在启动时打告警"


# ------------------------------------------------------------------
# 5. platform endpoint 接线黑盒（最小 FastAPI 装配）
# ------------------------------------------------------------------


@pytest.fixture()
def webhook_app():
    from fastapi import FastAPI

    from app.api.v1.endpoints.platform import router as platform_router
    from app.runtime.platform.registry import create_instance, remove_instance

    app = FastAPI()
    app.include_router(platform_router, prefix="/api/v1")
    create_instance(
        "inst_qq_p0_1_signed",
        "qq_official",
        "QQ官方验签测试（已配secret）",
        {"app_id": "11111111", "app_secret": _SECRET},
    )
    create_instance(
        "inst_qq_p0_1_unsigned",
        "qq_official",
        "QQ官方验签测试（未配secret）",
        {},
    )
    yield app
    remove_instance("inst_qq_p0_1_signed")
    remove_instance("inst_qq_p0_1_unsigned")


def _signed_request_headers(secret: str, body: bytes, timestamp: str = _TIMESTAMP):
    return {
        "content-type": "application/json",
        "X-Signature-Ed25519": _sign(secret, timestamp, body),
        "X-Signature-Timestamp": timestamp,
    }


@pytest.mark.asyncio
async def test_endpoint_accepts_valid_signature(webhook_app):
    import httpx

    body = _event_body()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=webhook_app), base_url="http://testserver"
    ) as client:
        resp = await client.post(
            "/api/v1/platforms/instances/inst_qq_p0_1_signed/webhook",
            content=body,
            headers=_signed_request_headers(_SECRET, body),
        )
    assert resp.status_code == 200
    assert resp.json()["data"] == {"received": True}


@pytest.mark.asyncio
async def test_endpoint_rejects_forged_signature_with_401(webhook_app):
    import httpx

    body = _event_body()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=webhook_app), base_url="http://testserver"
    ) as client:
        # 伪造密钥签名 → 401
        resp_forged = await client.post(
            "/api/v1/platforms/instances/inst_qq_p0_1_signed/webhook",
            content=body,
            headers=_signed_request_headers("attacker-secret", body),
        )
        # 缺签名头 → 401
        resp_missing = await client.post(
            "/api/v1/platforms/instances/inst_qq_p0_1_signed/webhook",
            content=body,
            headers={"content-type": "application/json"},
        )
        # 未配置 secret 的实例 → 401（fail-closed）
        resp_unconfigured = await client.post(
            "/api/v1/platforms/instances/inst_qq_p0_1_unsigned/webhook",
            content=body,
            headers=_signed_request_headers(_SECRET, body),
        )

    assert resp_forged.status_code == 401
    assert resp_missing.status_code == 401
    assert resp_unconfigured.status_code == 401
