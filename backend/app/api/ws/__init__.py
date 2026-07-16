"""LuomiNest WebSocket 模块。

导出：
- ws_router：FastAPI 路由器，注册到 app /ws 前缀（含 /browser 与 /avatar/drive）
- browser_ws_manager：浏览器 WS 连接管理器单例，供 AI 工具调用
- avatar_drive_ws_manager：Avatar 驱动 WS 连接管理器单例
"""
from app.api.ws.manager import LuomiNestBrowserWSManager, browser_ws_manager
from app.api.ws.router import ws_router
from app.api.ws.avatar_drive import (
    avatar_drive_ws_manager,
    push_emotion_drive,
    router as avatar_drive_router,
)

# 把 avatar_drive 路由也挂到 ws_router 上
ws_router.include_router(avatar_drive_router)

__all__ = [
    "ws_router",
    "browser_ws_manager",
    "LuomiNestBrowserWSManager",
    "avatar_drive_ws_manager",
    "push_emotion_drive",
]
