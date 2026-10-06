"""P0-4 两个游戏 WS 网关（minecraft / game_websocket）绑定与鉴权加固的单元测试。

覆盖：
1. 共享工具 ws_gateway_auth：默认绑定解析（缺省回退 127.0.0.1）、对端 loopback
   判定、握手 token 校验（Bearer 头 / ?access_token= 查询参数，常量时间比较）、
   connection_allowed 统一接入判定（有 token 必验凭证；无 token 仅 loopback 匿名）。
2. minecraft / game_websocket 适配器：默认绑定回环、显式绑定与 token 解析保留、
   真实 WS 服务器黑盒验收（错/缺 token close(1008)；无 token 时本机匿名可接入、
   经本机局域网地址进站的非 loopback 来源被拒——Fail-Closed）。
3. game_websocket 消息级 auth 兼容路径（常量时间比较 + 非字符串 token 防御），
   以及无 token 时 loopback 客户端的完整消息往返。
4. 注册元数据：两网关 config_template 的 ws_host 默认 127.0.0.1、token 配置项存在。
"""
import asyncio
import json
import socket
from unittest.mock import AsyncMock

import pytest
import websockets
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed

from app.runtime.platform.adapters.game_websocket import LuomiNestGameWebSocketAdapter
from app.runtime.platform.adapters.minecraft import LuomiNestMinecraftAdapter
from app.runtime.platform.base import PlatformMessage, PlatformResponse
from app.runtime.platform.infrastructure.ws_gateway_auth import (
    DEFAULT_WS_BIND_HOST,
    connection_allowed,
    is_loopback_peer,
    resolve_ws_bind_host,
    verify_handshake_token,
)


# ------------------------------------------------------------------
# 公共工具
# ------------------------------------------------------------------

def _make_handshake(auth_header: str = "", path: str = "/", remote_address: object = None):
    """构造带握手信息与对端地址的假 websocket（模拟 websockets 新实现 request 结构）。"""

    class _FakeRequest:
        def __init__(self) -> None:
            self.headers = Headers()
            if auth_header:
                self.headers["Authorization"] = auth_header
            self.path = path

    class _FakeWS:
        def __init__(self) -> None:
            self.request = _FakeRequest()
            self.remote_address = remote_address

    return _FakeWS()


def _make_mc(**cfg):
    """minecraft 适配器工厂：默认回环绑定 + 临时端口，token 键为 ws_token。"""
    token = cfg.pop("token", "")
    adapter = LuomiNestMinecraftAdapter()
    adapter.initialize({
        "ws_enabled": True,
        "ws_host": "127.0.0.1",
        "ws_port": 0,
        "ws_token": token,
        "game_port": 0,          # 跳过实体伴侣派遣
        "rcon_password": "",     # 跳过 RCON
        **cfg,
    })
    return adapter


def _make_gw(**cfg):
    """game_websocket 适配器工厂：默认回环绑定 + 临时端口，token 键为 auth_token。"""
    token = cfg.pop("token", "")
    adapter = LuomiNestGameWebSocketAdapter()
    adapter.initialize({
        "ws_host": "127.0.0.1",
        "ws_port": 0,
        "auth_token": token,
        **cfg,
    })
    return adapter


async def _serve(adapter) -> int:
    """启动适配器 WS 服务器并返回实际监听端口。"""
    if isinstance(adapter, LuomiNestMinecraftAdapter):
        await adapter._start_ws_server()
        return adapter._ws_server.sockets[0].getsockname()[1]
    await adapter.start()
    return adapter._server.sockets[0].getsockname()[1]


def _adapter_token(adapter) -> str:
    """读取网关 token（两适配器配置键名不同：ws_token / auth_token）。"""
    if isinstance(adapter, LuomiNestMinecraftAdapter):
        return adapter._ws_token
    return adapter._auth_token


async def _eventually(cond, timeout: float = 5.0) -> bool:
    """轮询等待异步副作用生效（确定性超时，无固定 sleep 依赖）。"""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if cond():
            return True
        await asyncio.sleep(0.05)
    return cond()


def _discover_local_non_loopback_ip() -> str | None:
    """探测本机非 loopback 的 IPv4 地址（getaddrinfo + UDP connect 双路，不实际发包）。"""
    candidates: set[str] = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            candidates.add(info[4][0])
    except Exception:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("10.255.255.255", 1))
            candidates.add(s.getsockname()[0])
        finally:
            s.close()
    except Exception:
        pass
    for ip in sorted(candidates):
        if ip and not ip.startswith("127.") and not ip.startswith("169.254."):
            return ip
    return None


# ------------------------------------------------------------------
# 1. 共享工具 ws_gateway_auth
# ------------------------------------------------------------------

def test_resolve_ws_bind_host_defaults_to_loopback():
    """缺省/空值/纯空白一律回退 127.0.0.1，绝不静默回到 0.0.0.0。"""
    assert DEFAULT_WS_BIND_HOST == "127.0.0.1"
    assert resolve_ws_bind_host(None) == "127.0.0.1"
    assert resolve_ws_bind_host("") == "127.0.0.1"
    assert resolve_ws_bind_host("   ") == "127.0.0.1"
    # 显式配置原样保留（含显式 0.0.0.0 的 headless 场景）
    assert resolve_ws_bind_host("0.0.0.0") == "0.0.0.0"
    assert resolve_ws_bind_host("192.168.1.5") == "192.168.1.5"
    assert resolve_ws_bind_host(" 127.0.0.1 ") == "127.0.0.1"


def test_is_loopback_peer_variants():
    """对 websockets.remote_address 的元组/字符串宽容解析。"""
    assert is_loopback_peer(("127.0.0.1", 1234))
    assert is_loopback_peer(("127.8.8.8", 1))
    assert is_loopback_peer(("::1", 1, 0, 0))
    assert is_loopback_peer("localhost")
    assert not is_loopback_peer(("192.168.1.10", 5000))
    assert not is_loopback_peer(("0.0.0.0", 80))
    assert not is_loopback_peer(None)
    assert not is_loopback_peer("unknown")


def test_verify_handshake_token_bearer_header_and_query_param():
    adapter_ws = _make_handshake("Bearer s3cret")
    assert verify_handshake_token(adapter_ws, "s3cret") is True

    query_ws = _make_handshake("", "/?access_token=s3cret")
    assert verify_handshake_token(query_ws, "s3cret") is True


def test_verify_handshake_token_rejects_wrong_or_missing():
    assert verify_handshake_token(_make_handshake("Bearer wrong"), "s3cret") is False
    assert verify_handshake_token(_make_handshake("", "/?access_token=wrong"), "s3cret") is False
    # 缺失凭证 / 非 Bearer 前缀
    assert verify_handshake_token(_make_handshake(), "s3cret") is False
    assert verify_handshake_token(_make_handshake("s3cret"), "s3cret") is False
    # 空 token 不足以通过（不能拿空串匹配空配置绕过）
    assert verify_handshake_token(_make_handshake("Bearer "), "s3cret") is False


def test_verify_handshake_token_open_when_not_configured():
    """未配置 token 时不做凭证要求（是否允许匿名由 connection_allowed 兜底）。"""
    assert verify_handshake_token(_make_handshake(), "") is True


def test_connection_allowed_token_configured_requires_credentials():
    """配置了 token：任何来源（含 loopback）都必须出示匹配凭证。"""
    loopback = ("127.0.0.1", 5000)
    assert connection_allowed(_make_handshake("Bearer s3cret", "/", loopback), "s3cret") is True
    assert connection_allowed(_make_handshake("", "/?access_token=s3cret", loopback), "s3cret") is True
    # loopback 来源但无/错凭证 → 仍拒绝
    assert connection_allowed(_make_handshake(remote_address=loopback), "s3cret") is False
    assert connection_allowed(_make_handshake("Bearer wrong", "/", loopback), "s3cret") is False


def test_connection_allowed_no_token_loopback_only_fail_closed():
    """未配置 token：仅 loopback 来源匿名可入，非 loopback 一律拒绝（Fail-Closed）。"""
    assert connection_allowed(_make_handshake(remote_address=("127.0.0.1", 5000)), "") is True
    assert connection_allowed(_make_handshake(remote_address=("::1", 1, 0, 0)), "") is True
    assert connection_allowed(_make_handshake(remote_address=("192.168.1.10", 5000)), "") is False
    # 对端地址不可知（None）→ 拒绝，绝不放行
    assert connection_allowed(_make_handshake(remote_address=None), "") is False


# ------------------------------------------------------------------
# 2. 适配器默认绑定与配置解析
# ------------------------------------------------------------------

@pytest.mark.parametrize("make_adapter", [_make_mc, _make_gw], ids=["minecraft", "game_websocket"])
def test_default_bind_is_loopback_and_token_empty(make_adapter):
    """initialize 不带 ws_host 时默认 127.0.0.1（原 0.0.0.0 已收紧），token 缺省为空。"""
    adapter = make_adapter()
    assert adapter._ws_host == "127.0.0.1"
    assert _adapter_token(adapter) == ""


@pytest.mark.parametrize("make_adapter", [_make_mc, _make_gw], ids=["minecraft", "game_websocket"])
def test_explicit_bind_and_token_preserved(make_adapter):
    """显式绑定地址与 token 原样保留；空串 token 等价未配置。"""
    adapter = make_adapter(ws_host="0.0.0.0", token="tok-1")
    assert adapter._ws_host == "0.0.0.0"
    assert _adapter_token(adapter) == "tok-1"

    adapter2 = make_adapter(token="")
    assert adapter2._ws_host == "127.0.0.1"
    assert _adapter_token(adapter2) == ""


# ------------------------------------------------------------------
# 3. 黑盒验收：token 配置后的握手鉴权（真实 websockets 服务器）
# ------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("make_adapter", [_make_mc, _make_gw], ids=["minecraft", "game_websocket"])
async def test_ws_gateway_rejects_bad_or_missing_token_close_1008(make_adapter):
    """配了 token 的网关：错误/缺失 token 的连接 close(1008) 且不注册；正确 token 放行。"""
    adapter = make_adapter(token="s3cret")
    port = await _serve(adapter)
    try:
        # 错误 token（裸连 / 查询参数错误）→ close(1008)
        for url in (
            f"ws://127.0.0.1:{port}/",
            f"ws://127.0.0.1:{port}/?access_token=wrong",
        ):
            async with websockets.connect(url) as client:
                with pytest.raises(ConnectionClosed) as exc_info:
                    await asyncio.wait_for(client.recv(), timeout=5.0)
                assert exc_info.value.rcvd.code == 1008

        # 错误 token（Bearer 头）→ close(1008)
        async with websockets.connect(
            f"ws://127.0.0.1:{port}/",
            additional_headers={"Authorization": "Bearer wrong"},
        ) as client:
            with pytest.raises(ConnectionClosed) as exc_info:
                await asyncio.wait_for(client.recv(), timeout=5.0)
            assert exc_info.value.rcvd.code == 1008

        # 被拒连接一律未注册
        if isinstance(adapter, LuomiNestMinecraftAdapter):
            assert adapter._ws_connections == {}
        else:
            assert adapter._clients == {}

        # 正确 token（Bearer 头）→ 连接保持可用
        async with websockets.connect(
            f"ws://127.0.0.1:{port}/",
            additional_headers={"Authorization": "Bearer s3cret"},
        ) as client:
            assert client.close_code is None

        # 正确 token（查询参数，浏览器 WS API 场景）→ 连接保持可用
        async with websockets.connect(
            f"ws://127.0.0.1:{port}/?access_token=s3cret"
        ) as client:
            assert client.close_code is None
    finally:
        await adapter.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("make_adapter", [_make_mc, _make_gw], ids=["minecraft", "game_websocket"])
async def test_ws_gateway_fail_closed_for_non_loopback_peer_without_token(make_adapter):
    """绑 0.0.0.0 且未配 token：非 loopback 来源被拒，本机回环来源仍可匿名接入。"""
    lan_ip = _discover_local_non_loopback_ip()
    if not lan_ip:
        pytest.skip("本机无独立非 loopback IPv4 地址，跳过跨源黑盒用例")

    adapter = make_adapter(ws_host="0.0.0.0")
    port = await _serve(adapter)
    try:
        # 经本机局域网地址进站 → 服务端看到的对端非 loopback → close(1008)
        async with websockets.connect(f"ws://{lan_ip}:{port}/") as client:
            with pytest.raises(ConnectionClosed) as exc_info:
                await asyncio.wait_for(client.recv(), timeout=5.0)
            assert exc_info.value.rcvd.code == 1008

        # 同一台服务器，回环来源匿名接入保持可用
        async with websockets.connect(f"ws://127.0.0.1:{port}/") as client:
            assert client.close_code is None
    finally:
        await adapter.stop()


# ------------------------------------------------------------------
# 4. 黑盒验收：无 token 时的匿名消息链路（回归保护）
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mc_ws_loopback_anonymous_event_reaches_adapter():
    """未配 token：本机模组匿名接入后，遥测事件正常进入适配器状态。"""
    adapter = _make_mc()
    port = await _serve(adapter)
    try:
        async with websockets.connect(f"ws://127.0.0.1:{port}/") as client:
            await client.send(json.dumps({
                "type": "telemetry",
                "player": "Steve",
                "position": [1.0, 64.0, 2.0],
                "health": 20,
            }))
            assert await _eventually(lambda: "Steve" in adapter._player_states)
    finally:
        await adapter.stop()


@pytest.mark.asyncio
async def test_game_ws_loopback_anonymous_message_roundtrip():
    """未配 token：本机游戏客户端匿名接入后，消息往返完整（握手门不破坏原链路）。"""
    adapter = _make_gw()
    received: list[PlatformMessage] = []

    async def handler(msg: PlatformMessage, instance_id: str):
        received.append(msg)
        return PlatformResponse(content="pong-reply")

    adapter.set_message_handler(handler)
    port = await _serve(adapter)
    try:
        async with websockets.connect(f"ws://127.0.0.1:{port}/") as client:
            await client.send(json.dumps({"type": "message", "user_id": "p1", "content": "hello"}))
            reply = json.loads(await asyncio.wait_for(client.recv(), timeout=5.0))
        assert reply["type"] == "response"
        assert reply["content"] == "pong-reply"
        assert received and received[0].content == "hello"
    finally:
        await adapter.stop()


# ------------------------------------------------------------------
# 5. game_websocket 消息级 auth 兼容路径（常量时间比较）
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_game_ws_message_level_auth_paths():
    """消息级 auth：正确 token 通过、错误/非字符串 token 拒绝并关闭、未配置 token 直通。"""
    adapter = LuomiNestGameWebSocketAdapter()
    adapter.initialize({"auth_token": "s3cret"})

    # 正确 token → auth_ok + 标记已认证
    ws_ok = AsyncMock()
    await adapter._handle_auth({"type": "auth", "token": "s3cret"}, ws_ok, 1)
    assert adapter._client_meta[1]["authenticated"] is True
    assert json.loads(ws_ok.send.call_args[0][0])["type"] == "auth_ok"

    # 错误 token → auth_failed + close
    ws_bad = AsyncMock()
    await adapter._handle_auth({"type": "auth", "token": "wrong"}, ws_bad, 2)
    assert json.loads(ws_bad.send.call_args[0][0])["type"] == "auth_failed"
    ws_bad.close.assert_awaited()

    # 非字符串 token（防御）→ auth_failed，不得抛异常放行
    ws_obj = AsyncMock()
    await adapter._handle_auth({"type": "auth", "token": {"evil": True}}, ws_obj, 3)
    assert json.loads(ws_obj.send.call_args[0][0])["type"] == "auth_failed"
    ws_obj.close.assert_awaited()

    # 未配置 token → 任意 auth 消息直接通过（旧客户端行为保留）
    adapter_open = LuomiNestGameWebSocketAdapter()
    adapter_open.initialize({})
    ws_open = AsyncMock()
    await adapter_open._handle_auth({"type": "auth", "token": ""}, ws_open, 4)
    assert adapter_open._client_meta[4]["authenticated"] is True
    assert json.loads(ws_open.send.call_args[0][0])["type"] == "auth_ok"


# ------------------------------------------------------------------
# 6. 启动告警（对齐 qq_onebot 的非 loopback 暴露提示）
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mc_start_warns_when_exposed_without_token(monkeypatch):
    """minecraft：非 loopback 绑定且未配 ws_token → start 时告警；配 token / 回环则不打。"""
    from app.runtime.platform.adapters import minecraft as mc_mod

    warned: list[tuple] = []
    monkeypatch.setattr(
        mc_mod, "warn_inbound_without_credential",
        lambda component, host, hint: warned.append((component, host, hint)),
    )

    # 0.0.0.0 + 无 token → 告警
    adapter = _make_mc(ws_host="0.0.0.0")
    await adapter.start()
    try:
        assert any("Minecraft" in c for c, _h, _k in warned)
    finally:
        await adapter.stop()

    # 0.0.0.0 + 配 token → 不告警
    warned.clear()
    adapter2 = _make_mc(ws_host="0.0.0.0", token="x")
    await adapter2.start()
    try:
        assert warned == []
    finally:
        await adapter2.stop()

    # 127.0.0.1 + 无 token → 不告警
    warned.clear()
    adapter3 = _make_mc()
    await adapter3.start()
    try:
        assert warned == []
    finally:
        await adapter3.stop()


@pytest.mark.asyncio
async def test_game_ws_start_warns_when_exposed_without_token(monkeypatch):
    """game_websocket：非 loopback 绑定且未配 token → start 时告警；配 token / 回环则不打。"""
    from app.runtime.platform.adapters import game_websocket as gw_mod

    warned: list[tuple] = []
    monkeypatch.setattr(
        gw_mod, "warn_inbound_without_credential",
        lambda component, host, hint: warned.append((component, host, hint)),
    )

    adapter = _make_gw(ws_host="0.0.0.0")
    await adapter.start()
    try:
        assert any("WebSocket" in c for c, _h, _k in warned)
    finally:
        await adapter.stop()

    warned.clear()
    adapter2 = _make_gw(ws_host="0.0.0.0", token="x")
    await adapter2.start()
    try:
        assert warned == []
    finally:
        await adapter2.stop()

    warned.clear()
    adapter3 = _make_gw()
    await adapter3.start()
    try:
        assert warned == []
    finally:
        await adapter3.stop()


# ------------------------------------------------------------------
# 7. 注册元数据：config_template 与实现默认值一致
# ------------------------------------------------------------------

def test_registered_config_templates_default_loopback():
    """UI 建实例用的模板必须默认回环绑定，且 minecraft 提供 ws_token 配置项。"""
    import app.runtime.platform.adapters  # noqa: F401  触发 _register_all_adapter_types()
    from app.runtime.platform.registry import get_adapter_type

    mc = get_adapter_type("minecraft")
    assert mc is not None
    assert mc.config_template["ws_host"] == "127.0.0.1"
    assert "ws_token" in mc.config_template
    assert mc.config_metadata["ws_token"]["type"] == "password"

    gw = get_adapter_type("game_websocket")
    assert gw is not None
    assert gw.config_template["ws_host"] == "127.0.0.1"
    assert "auth_token" in gw.config_template
