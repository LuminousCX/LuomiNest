"""LuomiNest 浏览器自动化 WebSocket 连接处理器。

处理前端 Electron Main 发起的 WS 连接生命周期：
1. 接受连接并注册到 manager
2. 循环接收消息，分发到 manager.handle_message
3. 连接断开时注销并清理 pending 请求
"""
import json

from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger

from app.api.ws.manager import browser_ws_manager


async def handle_browser_ws(websocket: WebSocket) -> None:
    """处理浏览器自动化 WS 连接的主入口

    前端 Electron Main 启动后连接 ws://127.0.0.1:18000/ws/browser，
    建立常驻双向通道，后端 AI 工具通过此通道向前端发送自动化指令。
    """
    await websocket.accept()
    await browser_ws_manager.register_connection(websocket)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
                await browser_ws_manager.handle_message(message)
            except json.JSONDecodeError:
                logger.warning(f"[BrowserWS] 收到非法 JSON: {raw[:100]}")
            except Exception as e:
                logger.error(f"[BrowserWS] 消息处理异常: {e}", exc_info=True)

    except WebSocketDisconnect:
        logger.info("[BrowserWS] 前端主动断开连接")
    except Exception as e:
        logger.warning(f"[BrowserWS] 连接异常断开: {e}")
    finally:
        await browser_ws_manager.unregister_connection()
