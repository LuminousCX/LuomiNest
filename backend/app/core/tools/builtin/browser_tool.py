"""LuomiNest 浏览器标签页创建工具。

主 Agent 通过本工具通知前端打开浏览器标签页并导航到指定 URL。
不使用 Playwright，而是复用前端已有的 Electron BrowserView 基础设施。

工作流程：
1. 主 Agent 调用 create_browser_tab 工具
2. 后端通过 SSE 推送 browser_event 到前端
3. 前端 WorkbenchView 接收事件，转发到 taskStream store
4. BrowserView 订阅 taskStream，自动打开标签页并导航
"""
from typing import Any
import uuid

from loguru import logger

from app.core.tools.registry import ToolBase, ToolResult


class CreateBrowserTabTool(ToolBase):
    """浏览器标签页创建工具"""

    @property
    def name(self) -> str:
        return "create_browser_tab"

    @property
    def description(self) -> str:
        return (
            "在浏览器页面打开新标签页并导航到指定 URL。"
            "适用于：调研网页、爬取评论、在线搜索等需要浏览器的场景。"
            "工具调用后，前端浏览器页面会自动打开标签页。"
            "如需自动化操作（点击/滚动/截图），请使用子 Agent 配合 cli 工具或 MCP 浏览器工具。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "要打开的网址 URL（如 'https://www.bilibili.com'）",
                },
                "title": {
                    "type": "string",
                    "description": "标签页标题（可选，用于任务流展示）",
                },
                "purpose": {
                    "type": "string",
                    "description": "打开此页面的目的（可选，如'爬取B站评论'）",
                },
            },
            "required": ["url"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        url = arguments.get("url", "").strip()
        if not url:
            return ToolResult.fail("缺少 url 参数")

        # 简单 URL 校验
        if not url.startswith(("http://", "https://")):
            return ToolResult.fail(f"URL 必须以 http:// 或 https:// 开头: {url}")

        title = arguments.get("title", "") or url
        purpose = arguments.get("purpose", "")
        tab_id = f"lumi_tab_{uuid.uuid4().hex[:8]}"

        logger.info(
            f"[CreateBrowserTabTool] 创建浏览器标签页: tab_id={tab_id}, url={url}, title={title}"
        )

        # 浏览器事件通过 contextvars 注入的回调推送到 SSE
        # 与子 Agent 事件类似，使用 browser_event 字段
        from app.core.tools.builtin.subagent_tool import _subagent_event_callback_var

        callback = _subagent_event_callback_var.get()
        if callback is not None:
            try:
                await callback({
                    "subagent_id": tab_id,  # 复用 subagent_event 通道
                    "status": "started",
                    "task": f"打开浏览器: {title}",
                    "depth": 0,
                    "tool_name": "create_browser_tab",
                    "tool_args": f'{{"url": "{url}", "title": "{title}"}}',
                    "progress": f"正在打开 {url}",
                    # 浏览器专用字段
                    "browser_action": "open_tab",
                    "browser_url": url,
                    "browser_title": title,
                    "browser_purpose": purpose,
                    "browser_tab_id": tab_id,
                })
            except Exception as e:
                logger.warning(f"[CreateBrowserTabTool] 事件回调失败: {e}")

        return ToolResult.ok(
            f"浏览器标签页已创建\n"
            f"标签页ID: {tab_id}\n"
            f"URL: {url}\n"
            f"标题: {title}",
            metadata={
                "tab_id": tab_id,
                "url": url,
                "title": title,
            },
        )
