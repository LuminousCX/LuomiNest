"""LuomiNest 浏览器自动化 WebSocket 模块。

导出：
- ws_router：FastAPI 路由器，注册到 app /ws 前缀
- browser_ws_manager：WS 连接管理器单例，供 AI 工具调用
"""
from app.api.ws.manager import LuomiNestBrowserWSManager, browser_ws_manager
from app.api.ws.router import ws_router

__all__ = ["ws_router", "browser_ws_manager", "LuomiNestBrowserWSManager"]
