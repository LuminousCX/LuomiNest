"""LuomiNest 浏览器自动化客户端。

工具层与 WebSocket 管理器之间的薄封装：解耦工具模块对 WS 内部实现的依赖。
所有浏览器自动化工具通过本模块向前端 Electron Main 发送自动化请求并等待结果。

工作流程：
1. 后端 AI 工具调用 execute_browser_action(action, args, timeout)
2. 本模块委托 browser_ws_manager.send_request 发送 WS 消息
3. 前端 Electron Main 的 LuomiAutomationExecutor 执行动作
4. 前端回送 automation_response，WS manager 通过 request_id 关联 Future
5. 本模块返回前端响应的 data 字段
"""
from typing import Any

from loguru import logger

from app.api.ws import browser_ws_manager


async def execute_browser_action(
    action: str,
    args: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """通过 WS 向前端 Electron 发送浏览器自动化请求并等待结果。

    Args:
        action: 自动化动作名（navigate/click/type/screenshot 等）
        args: 动作参数（透传给前端 executor）
        timeout: 超时秒数（默认 30s，截图等慢操作建议 60s）

    Returns:
        前端执行结果（前端 AutomationResult 的 data 字段）

    Raises:
        ConnectionError: 浏览器 WS 未连接（前端未启动或浏览器页面未打开）
        asyncio.TimeoutError: 等待前端响应超时
        RuntimeError: 前端执行返回的错误
    """
    if not browser_ws_manager.is_connected:
        raise ConnectionError("浏览器未连接，请先打开 LuomiNest 桌面端浏览器页面")

    logger.debug(f"[BrowserAutomationClient] → {action}")
    return await browser_ws_manager.send_request(action, args or {}, timeout)
