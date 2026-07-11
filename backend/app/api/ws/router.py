"""LuomiNest 浏览器自动化 WebSocket 路由。

注册 /ws/browser 端点，供前端 Electron Main 建立常驻双向连接。
"""
from fastapi import APIRouter, WebSocket

from app.api.ws.handler import handle_browser_ws

ws_router = APIRouter()


@ws_router.websocket("/browser")
async def browser_ws_endpoint(websocket: WebSocket):
    """浏览器自动化 WS 端点

    连接路径：ws://127.0.0.1:18000/ws/browser
    无需鉴权（仅本机访问，且 WS 握手不走 HTTP 中间件）

    注意：websocket 参数必须有 WebSocket 类型注解，否则 FastAPI 无法识别
    该参数为 WebSocket 连接对象，会导致依赖解析失败并返回 403。
    """
    await handle_browser_ws(websocket)
