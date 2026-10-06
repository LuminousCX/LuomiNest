"""QQ 官方 op=13 回调地址验证应答单测（QQ 开放平台官方 Webhook「回调地址验证」节）。

覆盖：
1. 官方挑战格式 {"op": 13, "d": {"plain_token", "event_ts"}} → 按官方算法
   对「event_ts + plain_token」做 Ed25519 签名（hex），返回
   {"plain_token", "signature"} 应答载荷，且签名可用派生公钥验真
2. fail-closed：secret 未配置 / plain_token 或 event_ts 缺失 → 返回 False
3. 普通事件推送不受影响：无签名头仍拒绝（P0-1 回归），带合法签名仍放行
4. endpoint 接线黑盒：op=13 请求得到裸 {"plain_token", "signature"} 响应体
   （不能包统一信封，否则控制台校验失败），验签事件路径行为不变
"""
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.runtime.platform.adapters.qq_official import LuomiNestQQOfficialAdapter

# 官方文档示例 secret（16 字节，触发种子翻倍推导路径）
_SECRET = "DG5g3B4j9X2KOErG"
_PLAIN_TOKEN = "Arq0D5A61EgUu4OxUvOp"
_EVENT_TS = "1725442341"

_OP13_CHALLENGE = {
    "op": 13,
    "d": {"plain_token": _PLAIN_TOKEN, "event_ts": _EVENT_TS},
}

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


def _public_key(secret: str = _SECRET):
    return Ed25519PrivateKey.from_private_bytes(_derive_seed(secret)).public_key()


def _sign_event(secret: str, timestamp: str, body: bytes) -> str:
    return (
        Ed25519PrivateKey.from_private_bytes(_derive_seed(secret))
        .sign(timestamp.encode("utf-8") + body)
        .hex()
    )


def _make_adapter(secret: str = _SECRET) -> LuomiNestQQOfficialAdapter:
    adapter = LuomiNestQQOfficialAdapter()
    adapter.initialize({"app_id": "11111111", "app_secret": secret})
    return adapter


def _capture_emit(monkeypatch, adapter: LuomiNestQQOfficialAdapter) -> list:
    seen: list = []

    async def fake_emit(msg):
        seen.append(msg)
        return None

    monkeypatch.setattr(adapter, "_emit_message", fake_emit)
    return seen


# ------------------------------------------------------------------
# 1. 官方算法应答
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_op13_challenge_returns_payload_with_verifiable_signature(monkeypatch):
    adapter = _make_adapter()
    seen = _capture_emit(monkeypatch, adapter)

    result = await adapter.handle_webhook(dict(_OP13_CHALLENGE))

    assert isinstance(result, dict), "op=13 必须返回应答载荷而非布尔值"
    assert result["plain_token"] == _PLAIN_TOKEN
    signature = result["signature"]
    assert len(signature) == 128, "Ed25519 64 字节签名的 hex 应为 128 字符"
    int(signature, 16)  # hex 可解析
    # 官方算法：签名对象为 event_ts + plain_token，可用派生公钥验真
    _public_key().verify(
        bytes.fromhex(signature),
        (_EVENT_TS + _PLAIN_TOKEN).encode("utf-8"),
    )
    assert seen == [], "回调地址验证不得触发任何业务逻辑"


@pytest.mark.asyncio
async def test_op13_challenge_with_string_op_and_long_secret(monkeypatch):
    """op 以字符串形式到达、secret 已 >= 32 字节（直接截取前 32 字节）同样可应答。"""
    long_secret = "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0"  # 40 字节
    adapter = _make_adapter(long_secret)
    challenge = {"op": "13", "d": {"plain_token": "tok", "event_ts": "123"}}

    result = await adapter.handle_webhook(challenge)

    assert isinstance(result, dict)
    _public_key(long_secret).verify(
        bytes.fromhex(result["signature"]), b"123tok"
    )


@pytest.mark.asyncio
async def test_op13_signature_differs_per_challenge_inputs():
    adapter = _make_adapter()
    r1 = await adapter.handle_webhook({"op": 13, "d": {"plain_token": "a", "event_ts": "1"}})
    r2 = await adapter.handle_webhook({"op": 13, "d": {"plain_token": "a", "event_ts": "2"}})
    r3 = await adapter.handle_webhook({"op": 13, "d": {"plain_token": "b", "event_ts": "1"}})
    assert len({r1["signature"], r2["signature"], r3["signature"]}) == 3
    # 顺序敏感：event_ts 在前 plain_token 在后
    r4 = await adapter.handle_webhook({"op": 13, "d": {"plain_token": "1", "event_ts": "a"}})
    assert r4["signature"] != r1["signature"]


# ------------------------------------------------------------------
# 2. fail-closed
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_op13_rejected_when_secret_not_configured():
    adapter = _make_adapter("")  # app_secret / webhook_secret 均未配置
    result = await adapter.handle_webhook(dict(_OP13_CHALLENGE))
    assert result is False, "secret 未配置必须 fail-closed 拒绝校验"


@pytest.mark.asyncio
async def test_op13_rejected_when_challenge_fields_missing(monkeypatch):
    adapter = _make_adapter()
    assert await adapter.handle_webhook({"op": 13, "d": {"plain_token": "tok"}}) is False
    assert await adapter.handle_webhook({"op": 13, "d": {"event_ts": "123"}}) is False
    assert await adapter.handle_webhook({"op": 13}) is False


@pytest.mark.asyncio
async def test_webhook_secret_override_used_for_op13():
    """显式配置 webhook_secret 时 op=13 应以它（而非 app_secret）派生密钥。"""
    adapter = LuomiNestQQOfficialAdapter()
    adapter.initialize({"app_id": "1", "app_secret": "app-secret", "webhook_secret": "hook-secret"})
    result = await adapter.handle_webhook(dict(_OP13_CHALLENGE))
    _public_key("hook-secret").verify(
        bytes.fromhex(result["signature"]),
        (_EVENT_TS + _PLAIN_TOKEN).encode("utf-8"),
    )


# ------------------------------------------------------------------
# 3. 普通事件路径回归（P0-1 不受 op=13 分支影响）
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unsigned_event_still_rejected(monkeypatch):
    adapter = _make_adapter()
    seen = _capture_emit(monkeypatch, adapter)
    assert await adapter.handle_webhook(_GROUP_EVENT) is False
    assert seen == []


@pytest.mark.asyncio
async def test_signed_event_still_dispatched(monkeypatch):
    adapter = _make_adapter()
    seen = _capture_emit(monkeypatch, adapter)
    body = json.dumps(_GROUP_EVENT).encode("utf-8")
    ts = "1725442341"
    sig = _sign_event(_SECRET, ts, body)
    assert await adapter.handle_webhook(
        _GROUP_EVENT, signature=sig, timestamp=ts, raw_body=body
    ) is True
    assert len(seen) == 1


# ------------------------------------------------------------------
# 4. endpoint 接线黑盒（裸 JSON 透出，不包统一信封）
# ------------------------------------------------------------------


@pytest.fixture()
def op13_app():
    from fastapi import FastAPI

    from app.api.v1.endpoints.platform import router as platform_router
    from app.runtime.platform.registry import create_instance, remove_instance

    app = FastAPI()
    app.include_router(platform_router, prefix="/api/v1")
    create_instance(
        "inst_qq_op13",
        "qq_official",
        "QQ官方回调校验测试",
        {"app_id": "11111111", "app_secret": _SECRET},
    )
    yield app
    remove_instance("inst_qq_op13")


@pytest.mark.asyncio
async def test_endpoint_returns_bare_validation_json(op13_app):
    """控制台要求响应体就是 {"plain_token", "signature"}，包信封即校验失败。"""
    import httpx

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=op13_app), base_url="http://testserver"
    ) as client:
        resp = await client.post(
            "/api/v1/platforms/instances/inst_qq_op13/webhook",
            json=_OP13_CHALLENGE,
        )

    assert resp.status_code == 200
    body = resp.json()
    # 原样裸 JSON：既不是统一信封，字段也完整
    assert set(body.keys()) == {"plain_token", "signature"}
    assert body["plain_token"] == _PLAIN_TOKEN
    _public_key().verify(
        bytes.fromhex(body["signature"]),
        (_EVENT_TS + _PLAIN_TOKEN).encode("utf-8"),
    )


@pytest.mark.asyncio
async def test_endpoint_signed_event_still_enveloped_ok(op13_app):
    """回归：普通验签事件仍走统一信封 {"received": true}。"""
    import httpx

    body = json.dumps(_GROUP_EVENT).encode("utf-8")
    ts = "1725442341"
    headers = {
        "content-type": "application/json",
        "X-Signature-Ed25519": _sign_event(_SECRET, ts, body),
        "X-Signature-Timestamp": ts,
    }
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=op13_app), base_url="http://testserver"
    ) as client:
        resp = await client.post(
            "/api/v1/platforms/instances/inst_qq_op13/webhook", content=body, headers=headers
        )

    assert resp.status_code == 200
    assert resp.json()["data"] == {"received": True}
