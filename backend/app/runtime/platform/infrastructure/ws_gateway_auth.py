"""游戏类 WS 网关的绑定与鉴权安全（P0-4：minecraft / game_websocket 共用语义）。

桌面单人本地场景的安全基线（对齐 qq_onebot._verify_handshake 质量标杆并升级为 Fail-Closed）：
- 默认仅绑定 127.0.0.1（原先两网关默认 0.0.0.0 全网开放）；
- 实例配置了 token：握手阶段校验凭证（Authorization: Bearer 头 或
  ?access_token= 查询参数），常量时间比较，失败 close(1008) 干净拒绝；
- 未配置 token：仅允许 loopback 来源匿名接入；非 loopback 来源一律拒绝
  （Fail-Closed）——headless 部署绑 0.0.0.0 时，局域网客户端必须配 token。
"""
from __future__ import annotations

import secrets
import urllib.parse
from typing import Any

from app.runtime.platform.infrastructure.exposure import is_loopback_host

# 游戏类 WS 网关的默认绑定地址（收紧原 0.0.0.0；显式配置仍可覆盖）
DEFAULT_WS_BIND_HOST = "127.0.0.1"


def resolve_ws_bind_host(config_value: Any) -> str:
    """解析实例配置的绑定地址：缺省/空值回退 127.0.0.1，绝不静默回到 0.0.0.0。"""
    host = "" if config_value is None else str(config_value).strip()
    return host or DEFAULT_WS_BIND_HOST


def is_loopback_peer(remote_address: Any) -> bool:
    """判断 WS 对端是否来自本机回环（对 websockets.remote_address 做宽容解析）。

    注意与监听地址语义相反：对端地址不可知（None/空）一律视为非回环
    （Fail-Closed），绝不因解析失败而放行。
    """
    host = ""
    if isinstance(remote_address, (tuple, list)):
        if remote_address:
            host = str(remote_address[0] or "")
    elif isinstance(remote_address, str):
        host = remote_address
    if not host.strip():
        return False
    return is_loopback_host(host)


def extract_handshake_credentials(websocket: Any) -> tuple[str, str]:
    """从握手对象提取 (Authorization 头, 原始路径)，兼容新旧 websockets 实现。

    - websockets >= 13（asyncio 新实现）：websocket.request.headers / request.path
    - 旧版 legacy 实现：websocket.request_headers / websocket.path
    """
    request = getattr(websocket, "request", None)
    headers = getattr(request, "headers", None)
    if headers is None:
        headers = getattr(websocket, "request_headers", None)

    auth_value = ""
    if headers is not None:
        try:
            auth_value = str(headers.get("Authorization", "") or "")
        except Exception:
            auth_value = ""

    raw_path = (
        getattr(request, "path", None)
        or getattr(websocket, "path", "")
        or ""
    )
    return auth_value, str(raw_path)


def verify_handshake_token(websocket: Any, access_token: str) -> bool:
    """校验 WS 握手凭证（P0-4）。

    两种携带方式均认可：
    1. Authorization: Bearer <token> 请求头；
    2. ?access_token=<token> 查询参数（浏览器 WebSocket API 无法自定义请求头）。

    常量时间比较防时序侧信道；空 provided 直接拒绝。
    未配置 token 时恒为 True（是否允许匿名接入由 connection_allowed 的
    loopback 判定兜底）。
    """
    if not access_token:
        return True

    auth_value, raw_path = extract_handshake_credentials(websocket)

    provided = ""
    if auth_value.lower().startswith("bearer "):
        provided = auth_value[7:].strip()
    if not provided and raw_path:
        parsed = urllib.parse.urlparse(raw_path)
        provided = (urllib.parse.parse_qs(parsed.query).get("access_token") or [""])[0].strip()

    return bool(provided) and secrets.compare_digest(provided, access_token)


def connection_allowed(websocket: Any, access_token: str) -> bool:
    """握手阶段统一接入判定（minecraft / game_websocket 共用语义）。

    - 配置了 token：任何来源（含 loopback）都必须出示匹配凭证；
    - 未配置 token：仅 loopback 来源允许匿名接入，非 loopback 一律拒绝
      （Fail-Closed：绑 0.0.0.0 的 headless 场景下，局域网客户端必须配 token）。
    """
    if access_token:
        return verify_handshake_token(websocket, access_token)
    return is_loopback_peer(getattr(websocket, "remote_address", None))
