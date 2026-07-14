"""LuomiNest 浏览器自动化 WebSocket 路由。

注册 /ws/browser 端点，供前端 Electron Main 建立常驻双向连接。
握手阶段通过 query 参数验证本地认证令牌，防止未授权进程远程操控浏览器。
"""
from fastapi import APIRouter, WebSocket, status
from loguru import logger

from app.api.ws.handler import handle_browser_ws
from app.security.auth.local_token import load_auth_token, verify_token

ws_router = APIRouter()


@ws_router.websocket("/browser")
async def browser_ws_endpoint(websocket: WebSocket):
    """浏览器自动化 WS 端点

    连接路径：ws://127.0.0.1:18000/ws/browser?token=<auth_token>

    通过 query 参数携带本地认证令牌，握手阶段验证。
    若未配置 auth_token（开发模式），则放行。

    注意：websocket 参数必须有 WebSocket 类型注解，否则 FastAPI 无法识别
    该参数为 WebSocket 连接对象，会导致依赖解析失败并返回 403。
    """
    expected_token = load_auth_token()

    if expected_token:
        provided = websocket.query_params.get("token", "")
        if not verify_token(provided, expected_token):
            logger.warning(f"[BrowserWS] 拒绝未授权的 WS 连接: {websocket.client}")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="未授权")
            return

    await handle_browser_ws(websocket)
