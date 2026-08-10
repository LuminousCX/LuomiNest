"""LuomiNest 浏览器自动化 WebSocket 路由。

注册 /ws/browser 端点，供前端 Electron Main 建立常驻双向连接。
握手阶段通过 query 参数验证认证令牌（支持 local / jwt 双模式），
防止未授权进程远程操控浏览器。
"""
from fastapi import APIRouter, WebSocket
from loguru import logger

from app.api.ws.handler import handle_browser_ws
from app.security.auth.ws_auth import authenticate_ws

ws_router = APIRouter()


@ws_router.websocket("/browser")
async def browser_ws_endpoint(websocket: WebSocket):
    """浏览器自动化 WS 端点

    连接路径：ws://127.0.0.1:18000/ws/browser?token=<auth_token>

    通过 query 参数携带认证令牌，握手阶段验证。
    支持 local（本地 token）和 jwt 双模式认证。

    注意：websocket 参数必须有 WebSocket 类型注解，否则 FastAPI 无法识别
    该参数为 WebSocket 连接对象，会导致依赖解析失败并返回 403。
    """
    if not await authenticate_ws(websocket, endpoint_name="BrowserWS"):
        return

    await handle_browser_ws(websocket)
