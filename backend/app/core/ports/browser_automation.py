"""浏览器自动化端口（六边形架构）。

内层工具（core.tools / core.workflow）只依赖本端口的 execute_browser_action 契约；
具体 WS 传输实现位于接入层（app.api.ws），可在组合根通过
register_browser_executor() 显式注入；未注入时回退到内置的 WS 兜底实现
（对 browser_ws_manager 采用延迟导入，避免核心层顶层依赖接入层）。

工作流程：
1. 后端 AI 工具调用 execute_browser_action(action, args, timeout)
2. 端口委托已注册的执行器（默认走 browser_ws_manager.send_request）
3. 前端 Electron Main 的自动化执行器执行动作
4. 前端回送 automation_response，WS manager 通过 request_id 关联 Future
5. 端口返回前端响应的 data 字段
"""
from typing import Any, Awaitable, Callable

from loguru import logger

BrowserExecutor = Callable[[str, dict[str, Any], float], Awaitable[dict[str, Any]]]

_executor: BrowserExecutor | None = None


def register_browser_executor(executor: BrowserExecutor | None) -> None:
    """注册浏览器自动化执行器（由组合根/接入层调用）。

    Args:
        executor: 异步执行器 (action, args, timeout) -> data；传 None 清除注册。
    """
    global _executor
    _executor = executor


async def _default_ws_executor(action: str, args: dict[str, Any], timeout: float) -> dict[str, Any]:
    """默认执行器：经浏览器 WS 通道转发到前端 Electron。

    延迟导入 —— WS 传输属于接入层（L5），核心层不得顶层依赖。
    """
    from app.api.ws import browser_ws_manager

    if not browser_ws_manager.is_connected:
        raise ConnectionError("浏览器未连接，请先打开 LuomiNest 桌面端浏览器页面")
    return await browser_ws_manager.send_request(action, args, timeout)


async def execute_browser_action(
    action: str,
    args: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """通过已注册的执行器执行浏览器自动化动作（未注册时回退 WS 默认实现）。

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
    executor = _executor or _default_ws_executor
    logger.debug(f"[BrowserAutomationPort] → {action}")
    return await executor(action, args or {}, timeout)
