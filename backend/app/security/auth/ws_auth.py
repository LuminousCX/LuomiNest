"""WebSocket 端点认证工具 — 支持 local / jwt 双模式。

供 WS 端点在握手阶段验证客户端身份，修复原实现中
JWT 模式下因 load_auth_token() 返回 None 而静默跳过认证的问题。
"""
from __future__ import annotations

from fastapi import WebSocket, status
from loguru import logger

from app.core.config import settings
from app.security.auth.local_token import load_auth_token, verify_token as local_verify_token


async def authenticate_ws(websocket: WebSocket, endpoint_name: str = "WS") -> bool:
    """验证 WebSocket 连接的认证凭据。

    根据 settings.AUTH_MODE 选择认证方式：
    - "local": 验证本地 auth token（query 参数 ?token=）
    - "jwt": 验证 JWT token（query 参数 ?token=）

    认证失败时关闭连接并返回 False。

    Args:
        websocket: WebSocket 连接对象。
        endpoint_name: 端点名称（用于日志）。

    Returns:
        True 表示认证通过，False 表示已关闭连接。
    """
    token = websocket.query_params.get("token", "")

    if settings.AUTH_MODE == "jwt":
        return await _verify_jwt_ws(websocket, token, endpoint_name)
    else:
        return await _verify_local_ws(websocket, token, endpoint_name)


async def _verify_local_ws(websocket: WebSocket, token: str, endpoint_name: str) -> bool:
    """local 模式 WS 认证。"""
    expected_token = load_auth_token()

    if not expected_token:
        # 没有配置 token 时拒绝连接（fail-closed），
        # 防止在无 token 状态下 WS 端点完全开放
        logger.warning(
            f"[{endpoint_name}] No auth token configured, rejecting WS connection "
            f"(fail-closed). Client: {websocket.client}"
        )
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="服务器未配置认证令牌，拒绝连接",
        )
        return False

    if not token or not local_verify_token(token, expected_token):
        logger.warning(f"[{endpoint_name}] Rejected unauthorized WS connection: {websocket.client}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="未授权")
        return False

    return True


async def _verify_jwt_ws(websocket: WebSocket, token: str, endpoint_name: str) -> bool:
    """jwt 模式 WS 认证。"""
    if not token:
        logger.warning(f"[{endpoint_name}/JWT] Rejected WS connection without token: {websocket.client}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="未授权，缺少认证令牌")
        return False

    from app.security.auth.jwt_handler import verify_token as jwt_verify_token, TokenError

    try:
        # expected_type 默认 "access"：refresh token 不能用于 WS 握手
        payload = jwt_verify_token(token)
    except TokenError as exc:
        logger.warning(f"[{endpoint_name}/JWT] Token verification failed: {exc.message} | {websocket.client}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=f"认证失败: {exc.message}")
        return False

    # 比对 DB token_version：登出/吊销后旧 token 的 WS 通道同样失效（握手低频，直查不缓存）
    from app.security.auth.middleware import load_user_token_version

    user_id = payload.get("sub") or ""
    current_version = await load_user_token_version(user_id, use_cache=False)
    if current_version is None or int(payload.get("ver", 1) or 1) != current_version:
        logger.warning(f"[{endpoint_name}/JWT] Stale/unknown token_version, rejecting WS: {websocket.client}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="令牌已失效，请重新登录")
        return False

    # 将用户信息存入 websocket.state（供后续使用）
    websocket.state.user = {
        "user_id": payload.get("sub"),
        "roles": payload.get("roles", []),
        "device_id": payload.get("device_id", ""),
    }

    return True
