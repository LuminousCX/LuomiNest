"""P0-3 传输安全加固的单元测试。

覆盖：
1. MCP token 生成与存储（config_items: mcp_server.token，含加密落库往返）
2. /mcp Bearer 鉴权中间件（无 token 401 / 错 token 401 / 带 token 放行 / 开关关闭放行）
3. QQ OneBot 反向 WS 握手 token 校验（Bearer 头 + ?access_token= 查询参数，
   错误 token 被 close(1008) 拒绝——用真实 websockets 服务器黑盒验证）
4. McpManager 对 streamable_http 配置的解析（url/headers 传参、缺 url fail-fast）
"""
from contextlib import asynccontextmanager

import pytest

from app.core.tools.mcp.models import McpServerConfig, McpTransportType


# ------------------------------------------------------------------
# 1. token 生成与存储
# ------------------------------------------------------------------

class _FakeStore:
    """替身 config_store（dict 存储），避免触碰真实 DB。"""

    def __init__(self) -> None:
        self.data: dict = {}

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value


@pytest.fixture(autouse=True)
def _clean_token_cache():
    """每个用例前后清空 auth 模块的进程内 token 缓存，保证用例隔离。"""
    import app.core.mcp_server.auth as auth

    auth._TOKEN_CACHE = None
    yield
    auth._TOKEN_CACHE = None


@pytest.fixture()
def fake_store(monkeypatch):
    store = _FakeStore()
    monkeypatch.setattr(
        "app.infrastructure.database.config_store.luominest_config_store", store
    )
    return store


def test_mcp_token_generated_and_persisted(fake_store):
    from app.core.mcp_server.auth import TOKEN_CONFIG_KEY, get_mcp_token

    token = get_mcp_token(create=True)
    assert token, "首次访问应自动生成 token"
    assert len(token) >= 32, "token_urlsafe(32) 应有足够熵"
    # 已持久化到 config_items 键
    assert fake_store.data.get(TOKEN_CONFIG_KEY) == token
    # 二次读取（缓存过期路径：清缓存后直读 store）应返回同一 token，不重复生成
    import app.core.mcp_server.auth as auth
    auth._TOKEN_CACHE = None
    assert get_mcp_token(create=True) == token
    assert len(fake_store.data) == 1


def test_mcp_token_reset_rotates_and_persists(fake_store):
    from app.core.mcp_server.auth import TOKEN_CONFIG_KEY, get_mcp_token, reset_mcp_token

    old = get_mcp_token(create=True)
    new = reset_mcp_token()
    assert old != new, "重置必须产生新 token"
    assert fake_store.data.get(TOKEN_CONFIG_KEY) == new
    # 重置后缓存立即生效：get 返回新 token
    assert get_mcp_token() == new


def test_mcp_token_read_only_does_not_create(fake_store):
    from app.core.mcp_server.auth import get_mcp_token

    assert get_mcp_token() is None, "create=False 时不得生成"
    assert fake_store.data == {}


@pytest.mark.usefixtures("_init_test_db")
def test_mcp_token_encrypted_roundtrip_in_config_items():
    """真实 config_items 路径：token 按 fnmatch 加密模式落库并可读回（P0-3 加固点）。"""
    from app.core.mcp_server.auth import TOKEN_CONFIG_KEY, get_mcp_token, reset_mcp_token
    from app.infrastructure.database.models.config_item import ConfigItem
    from app.infrastructure.database.session import sync_session_factory

    token = get_mcp_token(create=True)
    assert token
    with sync_session_factory() as session:
        row = session.get(ConfigItem, TOKEN_CONFIG_KEY)
    assert row is not None
    assert row.encrypted is True, "mcp_server.token 应命中加密模式"
    assert token not in (row.value or ""), "落库值不得是明文"

    reset = reset_mcp_token()
    assert reset != token
    assert get_mcp_token() == reset


# ------------------------------------------------------------------
# 2. /mcp Bearer 鉴权中间件（假挂载 app + httpx ASGI 传输）
# ------------------------------------------------------------------

async def _dummy_asgi_app(scope, receive, send):
    """被包裹的假 MCP 子应用：返回 200 + 固定标记。"""
    assert scope["type"] == "http"
    body = b"mcp-payload"
    await send({
        "type": "http.response.start",
        "status": 200,
        "headers": [(b"content-type", b"text/plain")],
    })
    await send({"type": "http.response.body", "body": body})


def _wrap_with_token(monkeypatch, token: str, *, enabled: bool | None = None):
    """构造包裹了 BearerAuthMiddleware 的假挂载 app，并把期望 token 注入假 store。"""
    import httpx

    from app.core.mcp_server.auth import BearerAuthMiddleware

    store = _FakeStore()
    store.data["mcp_server.token"] = token
    monkeypatch.setattr(
        "app.infrastructure.database.config_store.luominest_config_store", store
    )
    import app.core.mcp_server.auth as auth
    auth._TOKEN_CACHE = None

    app = BearerAuthMiddleware(_dummy_asgi_app, enabled=enabled)
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    )


@pytest.mark.asyncio
async def test_middleware_rejects_missing_token(monkeypatch):
    client = _wrap_with_token(monkeypatch, "tok-abc123")
    resp = await client.get("/mcp")
    await client.aclose()

    assert resp.status_code == 401
    data = resp.json()
    assert data["error"]["code"] == "AUTH_FAILED"
    assert resp.headers.get("www-authenticate") == "Bearer"


@pytest.mark.asyncio
async def test_middleware_rejects_wrong_token(monkeypatch):
    client = _wrap_with_token(monkeypatch, "tok-abc123")
    resp = await client.get(
        "/mcp", headers={"Authorization": "Bearer tok-wrong"}
    )
    await client.aclose()

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_middleware_allows_valid_token(monkeypatch):
    client = _wrap_with_token(monkeypatch, "tok-abc123")
    resp = await client.get(
        "/mcp", headers={"Authorization": "Bearer tok-abc123"}
    )
    await client.aclose()

    assert resp.status_code == 200
    assert resp.text == "mcp-payload"


@pytest.mark.asyncio
async def test_middleware_auth_disabled_passthrough(monkeypatch):
    """MCP_SERVER_AUTH=false（enabled=False）时整体放行。"""
    client = _wrap_with_token(monkeypatch, "tok-abc123", enabled=False)
    resp = await client.get("/mcp")  # 不带任何 token
    await client.aclose()

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_middleware_token_reset_takes_effect(monkeypatch):
    """token 轮换后旧 token 立即 401、新 token 放行（中间件每请求读当前 token）。"""
    import app.core.mcp_server.auth as auth

    client = _wrap_with_token(monkeypatch, "tok-old")
    try:
        resp_old = await client.get(
            "/mcp", headers={"Authorization": "Bearer tok-old"}
        )
        assert resp_old.status_code == 200

        # 轮换：经统一的 reset 入口（会刷新进程内缓存）
        monkeypatch.setattr(
            "app.infrastructure.database.config_store.luominest_config_store",
            _FakeStore(),
        )
        auth._TOKEN_CACHE = None
        new_token = auth.reset_mcp_token()

        resp_stale = await client.get(
            "/mcp", headers={"Authorization": "Bearer tok-old"}
        )
        assert resp_stale.status_code == 401

        resp_new = await client.get(
            "/mcp", headers={"Authorization": f"Bearer {new_token}"}
        )
        assert resp_new.status_code == 200
    finally:
        await client.aclose()


# ------------------------------------------------------------------
# 3. QQ OneBot 反向 WS 握手鉴权
# ------------------------------------------------------------------

def _make_handshake(auth_header: str = "", path: str = "/"):
    """构造带握手信息的假 websocket（模拟 websockets 新实现的 request 结构）。"""
    from websockets.datastructures import Headers

    class _FakeRequest:
        def __init__(self) -> None:
            self.headers = Headers()
            if auth_header:
                self.headers["Authorization"] = auth_header
            self.path = path

    class _FakeWS:
        def __init__(self) -> None:
            self.request = _FakeRequest()

    return _FakeWS()


def _make_adapter(access_token: str):
    from app.runtime.platform.adapters.qq_onebot import LuomiNestQQOneBotAdapter

    adapter = LuomiNestQQOneBotAdapter()
    adapter.initialize({
        "ws_host": "127.0.0.1",
        "ws_port": 0,
        "access_token": access_token,
    })
    return adapter


def test_qq_handshake_valid_bearer_header():
    adapter = _make_adapter("s3cret")
    assert adapter._verify_handshake(_make_handshake("Bearer s3cret")) is True


def test_qq_handshake_valid_query_param():
    adapter = _make_adapter("s3cret")
    assert (
        adapter._verify_handshake(_make_handshake("", "/?access_token=s3cret"))
        is True
    )


def test_qq_handshake_rejects_wrong_token():
    adapter = _make_adapter("s3cret")
    assert adapter._verify_handshake(_make_handshake("Bearer wrong")) is False
    assert adapter._verify_handshake(_make_handshake("", "/?access_token=wrong")) is False


def test_qq_handshake_rejects_missing_credentials():
    adapter = _make_adapter("s3cret")
    assert adapter._verify_handshake(_make_handshake()) is False
    # 格式不符（非 Bearer 前缀）也应拒绝
    assert adapter._verify_handshake(_make_handshake("s3cret")) is False


def test_qq_handshake_open_when_token_not_configured():
    adapter = _make_adapter("")
    assert adapter._verify_handshake(_make_handshake()) is True


@pytest.mark.asyncio
async def test_qq_ws_rejects_bad_token_close_1008():
    """黑盒验收：配了 token 的反向 WS 服务器对错误/缺失 token 的连接 close(1008)。"""
    import asyncio

    import websockets
    from websockets.exceptions import ConnectionClosed

    adapter = _make_adapter("s3cret")
    await adapter._start_server()
    port = adapter._server.sockets[0].getsockname()[1]
    try:
        # 错误 token → 服务端 close(1008)
        async with websockets.connect(
            f"ws://127.0.0.1:{port}/",
            additional_headers={"Authorization": "Bearer wrong"},
        ) as client:
            with pytest.raises(ConnectionClosed) as exc_info:
                await asyncio.wait_for(client.recv(), timeout=5.0)
            assert exc_info.value.rcvd.code == 1008

        # 缺失 token → close(1008)
        async with websockets.connect(f"ws://127.0.0.1:{port}/") as client:
            with pytest.raises(ConnectionClosed) as exc_info:
                await asyncio.wait_for(client.recv(), timeout=5.0)
            assert exc_info.value.rcvd.code == 1008

        # 正确 token（header）→ 连接保持可用
        async with websockets.connect(
            f"ws://127.0.0.1:{port}/",
            additional_headers={"Authorization": "Bearer s3cret"},
        ) as client:
            assert client.close_code is None

        # 正确 token（查询参数）→ 连接保持可用
        async with websockets.connect(
            f"ws://127.0.0.1:{port}/?access_token=s3cret"
        ) as client:
            assert client.close_code is None
    finally:
        adapter._server.close()
        await adapter._server.wait_closed()


# ------------------------------------------------------------------
# 4. McpManager 对 streamable_http 配置的解析
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_manager_streamable_http_parses_url_and_headers(monkeypatch):
    """streamable_http：url 与自定义 headers 正确传入 SDK 客户端，产出 (read, write)。"""
    from contextlib import AsyncExitStack

    import app.core.tools.mcp.manager as mgr_mod

    captured: dict = {}

    @asynccontextmanager
    async def fake_streamable_http_client(url, *, http_client=None, terminate_on_close=True):
        captured["url"] = url
        captured["http_client"] = http_client
        yield "read-stream", "write-stream"

    monkeypatch.setattr(
        "mcp.client.streamable_http.streamable_http_client",
        fake_streamable_http_client,
    )

    config = McpServerConfig(
        name="remote",
        transport=McpTransportType.STREAMABLE_HTTP,
        url="http://127.0.0.1:18000/mcp",
        headers={"Authorization": "Bearer tok-xyz"},
    )
    stack = AsyncExitStack()
    try:
        read, write = await mgr_mod.mcp_manager._open_transport(config, stack)
        assert read == "read-stream"
        assert write == "write-stream"
        assert captured["url"] == "http://127.0.0.1:18000/mcp"
        # 自定义 headers 经预配置 httpx2 客户端传入（SDK 不接受裸 headers 参数）
        assert captured["http_client"] is not None
        assert captured["http_client"].headers.get("Authorization") == "Bearer tok-xyz"
    finally:
        await stack.aclose()


@pytest.mark.asyncio
async def test_manager_streamable_http_requires_url():
    """缺 url 时 fail-fast 报错。"""
    from contextlib import AsyncExitStack

    from app.core.tools.mcp.manager import mcp_manager

    config = McpServerConfig(name="bad", transport=McpTransportType.STREAMABLE_HTTP)
    with pytest.raises(ValueError, match="url"):
        await mcp_manager._open_transport(config, AsyncExitStack())


def test_streamable_http_transport_config_persists(tmp_path, monkeypatch):
    """streamable_http 配置沿用 mcp_servers.json 结构持久化往返。"""
    config = McpServerConfig(
        name="remote",
        transport=McpTransportType.STREAMABLE_HTTP,
        url="http://127.0.0.1:18000/mcp",
        headers={"Authorization": "Bearer tok-xyz"},
        description="外部 Streamable HTTP 服务器",
    )
    payload = config.model_dump(mode="json")
    assert payload["transport"] == "streamable_http"
    # 旧结构（stdio/sse）读取不受影响，新值可完整还原
    restored = McpServerConfig(**payload)
    assert restored.transport == McpTransportType.STREAMABLE_HTTP
    assert restored.url == config.url
    assert restored.headers == config.headers


# ------------------------------------------------------------------
# 5. 非 loopback 暴露判定（辅助）
# ------------------------------------------------------------------

def test_is_loopback_host():
    from app.runtime.platform.infrastructure.exposure import is_loopback_host

    assert is_loopback_host("127.0.0.1")
    assert is_loopback_host("localhost")
    assert is_loopback_host("127.9.9.9")
    assert is_loopback_host("::1")
    assert is_loopback_host("")
    assert not is_loopback_host("0.0.0.0")
    assert not is_loopback_host("192.168.1.10")
    assert not is_loopback_host("::")


@pytest.mark.asyncio
async def test_qq_start_warns_when_exposed_without_token(monkeypatch):
    """绑定 0.0.0.0 且未配 token → start 时打告警；配了 token / loopback 则不打。"""
    from loguru import logger

    from app.runtime.platform.adapters.qq_onebot import LuomiNestQQOneBotAdapter

    warned: list[str] = []
    monkeypatch.setattr(
        logger, "warning", lambda msg, *a, **k: warned.append(str(msg))
    )

    async def _noop_start_server():
        return None  # 不真正绑定端口，只验证 start 的告警分支

    # 未配 token + 绑定非 loopback → 告警
    adapter = LuomiNestQQOneBotAdapter()
    adapter.initialize({"ws_host": "0.0.0.0", "ws_port": 8080, "access_token": ""})
    monkeypatch.setattr(adapter, "_start_server", _noop_start_server)
    await adapter.start()
    try:
        assert any("QQ OneBot 反向 WS" in w for w in warned), (
            "非 loopback + 无 token 必须打启动告警"
        )
    finally:
        await adapter.stop()

    # 配了 token → 不告警
    warned.clear()
    adapter2 = LuomiNestQQOneBotAdapter()
    adapter2.initialize({"ws_host": "0.0.0.0", "ws_port": 8080, "access_token": "x"})
    monkeypatch.setattr(adapter2, "_start_server", _noop_start_server)
    await adapter2.start()
    try:
        assert not any("QQ OneBot 反向 WS" in w for w in warned)
    finally:
        await adapter2.stop()


# ------------------------------------------------------------------
# 6. auth 模块补充分支（TTL 缓存 / fail-closed / 非 http 透传 / Bearer 解析）
# ------------------------------------------------------------------

def test_mcp_token_cache_hit_within_ttl(fake_store, monkeypatch):
    """TTL 内命中进程内缓存：不回源 store（热路径不查库）。"""
    import app.core.mcp_server.auth as auth
    from app.core.mcp_server.auth import get_mcp_token

    token = get_mcp_token(create=True)
    assert token

    calls: list = []
    orig_get = fake_store.get

    def counting_get(key, default=None):
        calls.append(key)
        return orig_get(key, default)

    monkeypatch.setattr(fake_store, "get", counting_get)
    assert get_mcp_token() == token
    assert calls == [], "TTL 内应命中缓存，不得查库"


def test_mcp_token_cache_expires_and_rereads_store(fake_store, monkeypatch):
    """超过 TTL 后缓存失效：回源 store 取同一持久化 token，并刷新缓存时间戳。"""
    import time

    import app.core.mcp_server.auth as auth
    from app.core.mcp_server.auth import get_mcp_token

    token = get_mcp_token(create=True)
    # 人为把缓存时间戳拨到 TTL 之外（确定性，不 sleep）
    auth._TOKEN_CACHE = (token, time.monotonic() - auth._TOKEN_CACHE_TTL - 1.0)

    calls: list = []
    orig_get = fake_store.get

    def counting_get(key, default=None):
        calls.append(key)
        return orig_get(key, default)

    monkeypatch.setattr(fake_store, "get", counting_get)

    before = time.monotonic()
    assert get_mcp_token() == token, "过期后回源应取到同一持久化 token"
    assert calls, "过期后必须回源 store"
    assert auth._TOKEN_CACHE is not None
    assert auth._TOKEN_CACHE[1] >= before, "回源后应刷新缓存时间戳"


def test_mcp_token_store_blank_or_non_string_treated_as_missing(fake_store):
    """store 中空串/非字符串值一律视为缺失：read-only 返回 None，create 重新生成。"""
    import app.core.mcp_server.auth as auth
    from app.core.mcp_server.auth import TOKEN_CONFIG_KEY, get_mcp_token

    fake_store.data[TOKEN_CONFIG_KEY] = ""
    assert get_mcp_token() is None

    fake_store.data[TOKEN_CONFIG_KEY] = 12345  # 非 str 一律不算有效 token
    assert get_mcp_token() is None

    generated = get_mcp_token(create=True)
    assert generated
    assert fake_store.data[TOKEN_CONFIG_KEY] == generated


def test_mcp_token_reset_on_empty_store(fake_store):
    """从未生成过 token 时也可直接 reset：生成 + 落库 + 写缓存。"""
    import app.core.mcp_server.auth as auth
    from app.core.mcp_server.auth import TOKEN_CONFIG_KEY, get_mcp_token, reset_mcp_token

    token = reset_mcp_token()
    assert token
    assert fake_store.data[TOKEN_CONFIG_KEY] == token
    # reset 已写缓存：随后的读取不回源也拿到新 token
    assert get_mcp_token() == token
    assert auth._TOKEN_CACHE is not None and auth._TOKEN_CACHE[0] == token


def test_extract_bearer_token_variants():
    """_extract_bearer_token 的头名/前缀大小写、空白、非 Bearer、缺失等分支。"""
    from app.core.mcp_server.auth import _extract_bearer_token

    # 常规
    assert _extract_bearer_token({"headers": [(b"authorization", b"Bearer tok")]}) == "tok"
    # 头名大小写不敏感
    assert _extract_bearer_token({"headers": [(b"AUTHORIZATION", b"Bearer tok")]}) == "tok"
    # scheme 前缀大小写不敏感
    assert _extract_bearer_token({"headers": [(b"authorization", b"bearer tok")]}) == "tok"
    # 宽松空白（前缀后多余空格、尾部空白）
    assert (
        _extract_bearer_token({"headers": [(b"authorization", b"  Bearer   tok  ")]})
        == "tok"
    )
    # 非 Bearer scheme → 空串
    assert (
        _extract_bearer_token({"headers": [(b"authorization", b"Basic dXNlcjpwd2Q=")]})
        == ""
    )
    # 只有 "Bearer" 无空格（不足 7 字节）→ 空串
    assert _extract_bearer_token({"headers": [(b"authorization", b"Bearer")]}) == ""
    # "Bearer " 后为空 → 空串
    assert _extract_bearer_token({"headers": [(b"authorization", b"Bearer ")]}) == ""
    # 无 authorization 头 / headers 缺失或为 None → 空串
    assert (
        _extract_bearer_token({"headers": [(b"content-type", b"application/json")]})
        == ""
    )
    assert _extract_bearer_token({}) == ""
    assert _extract_bearer_token({"headers": None}) == ""


@pytest.mark.asyncio
async def test_middleware_rejects_non_bearer_scheme(monkeypatch):
    """Authorization 存在但非 Bearer scheme → 401（等价于缺失）。"""
    client = _wrap_with_token(monkeypatch, "tok-abc123")
    resp = await client.get(
        "/mcp", headers={"Authorization": "Basic dXNlcjpwd2Q="}
    )
    await client.aclose()

    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_FAILED"


@pytest.mark.asyncio
async def test_middleware_accepts_lowercase_bearer_and_extra_spaces(monkeypatch):
    """scheme 小写 + 多余空白仍应解析出 token 并放行。"""
    client = _wrap_with_token(monkeypatch, "tok-abc123")
    resp = await client.get(
        "/mcp", headers={"Authorization": "bearer  tok-abc123 "}
    )
    await client.aclose()

    assert resp.status_code == 200
    assert resp.text == "mcp-payload"


@pytest.mark.asyncio
async def test_middleware_fail_closed_when_token_lookup_raises(monkeypatch):
    """store/读取异常 → fail-closed 401（绝不静默放行），即使带了（旧）token。"""
    import app.core.mcp_server.auth as auth

    client = _wrap_with_token(monkeypatch, "tok-abc123")
    try:
        def _boom(*args, **kwargs):
            raise RuntimeError("store down")

        monkeypatch.setattr(auth, "get_mcp_token", _boom)
        resp = await client.get(
            "/mcp", headers={"Authorization": "Bearer tok-abc123"}
        )

        assert resp.status_code == 401
        data = resp.json()
        assert data["error"]["code"] == "AUTH_FAILED"
        assert "暂不可用" in data["error"]["message"]
        assert data["data"] is None
        # 401 响应头自洽：content-length 与实际 body 一致
        assert int(resp.headers["content-length"]) == len(resp.content)
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_middleware_fail_closed_when_token_unavailable(monkeypatch):
    """get_mcp_token 返回空 → fail-closed 401（带 token 也拒绝）。"""
    import app.core.mcp_server.auth as auth

    client = _wrap_with_token(monkeypatch, "tok-abc123")
    try:
        monkeypatch.setattr(auth, "get_mcp_token", lambda *a, **k: None)
        resp = await client.get(
            "/mcp", headers={"Authorization": "Bearer tok-abc123"}
        )

        assert resp.status_code == 401
        assert "未配置" in resp.json()["error"]["message"]
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_middleware_passes_through_non_http_scope(monkeypatch):
    """scope type 非 http（websocket/lifespan）→ 不鉴权直接透传给子应用。"""
    import app.core.mcp_server.auth as auth
    from app.core.mcp_server.auth import BearerAuthMiddleware

    store = _FakeStore()
    store.data["mcp_server.token"] = "tok-abc123"
    monkeypatch.setattr(
        "app.infrastructure.database.config_store.luominest_config_store", store
    )
    auth._TOKEN_CACHE = None

    seen: list = []
    sent: list = []

    async def inner(scope, receive, send):
        seen.append(scope)

    async def send(message):
        sent.append(message)

    async def receive():
        return {"type": "http.disconnect"}

    middleware = BearerAuthMiddleware(inner)  # 不带 override：鉴权默认开启
    for scope_type in ("websocket", "lifespan"):
        seen.clear()
        sent.clear()
        await middleware({"type": scope_type, "path": "/mcp"}, receive, send)
        assert len(seen) == 1, f"{scope_type} 应直接透传给子应用"
        assert sent == [], f"{scope_type} 不应产生 401 响应"


@pytest.mark.asyncio
async def test_middleware_reads_settings_switch_when_no_override(monkeypatch):
    """enabled=None 时按 settings.MCP_SERVER_AUTH 动态判定开关。"""
    from app.core.config import settings

    import app.core.mcp_server.auth as auth
    from app.core.mcp_server.auth import BearerAuthMiddleware

    client = _wrap_with_token(monkeypatch, "tok-abc123", enabled=None)
    try:
        middleware = BearerAuthMiddleware(_dummy_asgi_app)  # enabled=None 路径

        monkeypatch.setattr(settings, "MCP_SERVER_AUTH", False)
        assert middleware._auth_enabled() is False
        resp = await client.get("/mcp")  # 不带 token
        assert resp.status_code == 200, "开关关闭时整体放行"

        monkeypatch.setattr(settings, "MCP_SERVER_AUTH", True)
        assert middleware._auth_enabled() is True
        resp = await client.get("/mcp")
        assert resp.status_code == 401, "开关开启时无 token 拒绝"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_middleware_creates_token_on_first_request(monkeypatch):
    """store 为空时首个请求触发 create=True 自动生成并落库；随后凭该 token 放行。"""
    import httpx

    import app.core.mcp_server.auth as auth
    from app.core.mcp_server.auth import TOKEN_CONFIG_KEY, BearerAuthMiddleware

    store = _FakeStore()
    monkeypatch.setattr(
        "app.infrastructure.database.config_store.luominest_config_store", store
    )
    auth._TOKEN_CACHE = None

    app = BearerAuthMiddleware(_dummy_asgi_app)
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    )
    try:
        # 首个请求：未带 token → 401，但 token 已生成并持久化
        resp1 = await client.get("/mcp")
        assert resp1.status_code == 401
        stored = store.data.get(TOKEN_CONFIG_KEY)
        assert stored, "首个请求应触发 token 生成并落库"

        # 用生成出的 token → 放行
        resp2 = await client.get(
            "/mcp", headers={"Authorization": f"Bearer {stored}"}
        )
        assert resp2.status_code == 200
    finally:
        await client.aclose()


# ------------------------------------------------------------------
# 7. exposure 模块补充分支（loopback 归一化 / env 读取 / 告警函数）
# ------------------------------------------------------------------

def test_is_loopback_host_none_and_normalization():
    """None 归一为空串、大小写与首尾空白宽容匹配、127.0.0.0/8 前缀判定。"""
    from app.runtime.platform.infrastructure.exposure import is_loopback_host

    assert is_loopback_host(None), "None 等价于未指定 → 视为 loopback"
    assert is_loopback_host("LOCALHOST"), "大小写宽容匹配"
    assert is_loopback_host("LocalHost")
    assert is_loopback_host("  127.0.0.1 "), "首尾空白宽容匹配"
    assert is_loopback_host("127.0.0.255"), "整个 127.0.0.0/8 都是 loopback"
    assert not is_loopback_host("::2"), "仅 ::1 精确匹配，其它 IPv6 不算"
    assert not is_loopback_host("fe80::1")
    assert not is_loopback_host("10.0.0.1")
    assert not is_loopback_host(" 192.168.1.10 ")


def test_get_backend_listen_host(monkeypatch):
    """env 未写入时默认 127.0.0.1；main.py 写入 LISTEN_HOST_ENV 后按 env 返回。"""
    from app.runtime.platform.infrastructure.exposure import (
        LISTEN_HOST_ENV,
        get_backend_listen_host,
    )

    monkeypatch.delenv(LISTEN_HOST_ENV, raising=False)
    assert get_backend_listen_host() == "127.0.0.1"

    monkeypatch.setenv(LISTEN_HOST_ENV, "0.0.0.0")
    assert get_backend_listen_host() == "0.0.0.0"

    monkeypatch.setenv(LISTEN_HOST_ENV, "192.168.31.7")
    assert get_backend_listen_host() == "192.168.31.7"


def test_warn_lan_exposure_only_for_non_loopback(monkeypatch):
    """loopback 不告警；非 loopback 打多行告警且包含 host 与 /mcp 鉴权提示。"""
    from loguru import logger

    from app.runtime.platform.infrastructure.exposure import warn_lan_exposure

    warned: list[str] = []
    monkeypatch.setattr(
        logger, "warning", lambda msg, *a, **k: warned.append(str(msg))
    )

    warn_lan_exposure("127.0.0.1")
    warn_lan_exposure("localhost")
    warn_lan_exposure("::1")
    warn_lan_exposure("")
    assert warned == [], "loopback 监听不应产生任何告警"

    warn_lan_exposure("192.168.1.10")
    assert warned, "非 loopback 监听必须告警"
    assert any("192.168.1.10" in w for w in warned), "告警应包含实际监听地址"
    assert any("/mcp" in w for w in warned), "告警应提示 /mcp 鉴权检查"
    assert any("access_token" in w for w in warned), "告警应提示实例凭证配置"


def test_warn_inbound_without_credential_only_for_non_loopback(monkeypatch):
    """组件入站面：loopback 不告警；非 loopback 打单行告警并含组件/地址/凭证提示。"""
    from loguru import logger

    from app.runtime.platform.infrastructure.exposure import (
        warn_inbound_without_credential,
    )

    warned: list[str] = []
    monkeypatch.setattr(
        logger, "warning", lambda msg, *a, **k: warned.append(str(msg))
    )

    warn_inbound_without_credential("REST API", "127.0.0.1", "api_key")
    warn_inbound_without_credential("REST API", "", "api_key")
    assert warned == [], "loopback（含空串）不应告警"

    warn_inbound_without_credential("REST API", "0.0.0.0", "api_key")
    assert len(warned) == 1, "非 loopback 应打且仅打一条告警"
    assert "REST API" in warned[0]
    assert "0.0.0.0" in warned[0]
    assert "api_key" in warned[0]
