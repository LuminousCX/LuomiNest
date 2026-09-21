"""LuomiNest 浏览器观察工具集。

只读观察工具集（产品定位：内置浏览器精简为只读——
Agent 只需"访问网页 + 看见 + 管理标签页"，不做任何页面交互）：
- browser_visit: 打开网址 → 等待加载 → 自动截图（复合动作，一次返回结果）
- browser_screenshot: 对当前浏览器页面重新截图（base64 PNG）
- browser_get_tabs / browser_switch_tab / browser_open_tab / browser_close_tab:
  多标签页查看与切换（2026-09-21 恢复，覆盖多 tab 浏览场景）

截图经 ToolResult.metadata 传递，由 AgentRunner 在模型具备视觉能力时
注入为 image_url 消息（见 runner._append_vision_feedback）。

通过 WebSocket 调用前端 Electron Main 的 LuomiAutomationExecutor 执行
（Electron 原生 API，不依赖 Playwright/Puppeteer）。

设计模式：DRY 规格表
- BROWSER_ACTION_SPECS 描述每个工具的 name/action/description/parameters/timeout
- LuomiBrowserAutomationTool 通用类按规格实例化
- get_luominest_browser_automation_tools() 工厂返回全部工具实例

历史说明：曾包含 29 个全量自动化工具（导航/交互/等待/execute_js 等），
已于 2026-09 工具链瘦身中移除；browser_get_html 已于 2026-09 只读化改造中
从工具面移除（executor 内部能力保留，WS 协议兼容不动）。
"""
import json
from typing import Any

from loguru import logger

from app.core.tools.registry import ToolBase, ToolResult
from app.core.ports.browser_automation import execute_browser_action


# ============================================================================
# 工具规格表：每个工具的 name → {action, description, parameters, timeout}
# ============================================================================

_TAB_ID_PARAM = {
    "type": "string",
    "description": "标签页 ID（可选，缺省为当前活跃标签页）",
}

BROWSER_ACTION_SPECS: dict[str, dict[str, Any]] = {
    "browser_visit": {
        "action": "navigate_and_screenshot",
        "description": (
            "在内置浏览器中打开指定网址：导航 → 等待页面加载完成（load 事件 + 约 1.5 秒渲染稳定期）"
            "→ 自动截图。返回页面标题、最终 URL 及截图。"
            "对于支持视觉处理的多模态大模型，画面截图将自动同步，供模型直观分析网页内容。"
            "只读操作，不会对网页执行任何危险输入。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "要访问的完整网址（含 http:// 或 https://）",
                },
                "wait_seconds": {
                    "type": "number",
                    "description": "页面 load 后的额外渲染稳定等待秒数（默认 1.5，范围 0~10）",
                },
                "tab_id": _TAB_ID_PARAM,
            },
            "required": ["url"],
        },
        "timeout": 60.0,
    },
    "browser_screenshot": {
        "action": "screenshot",
        "description": "截取内置浏览器当前活跃或指定标签页的最新画面截图。多模态大模型可直接查看该截图。",
        "parameters": {
            "type": "object",
            "properties": {"tab_id": _TAB_ID_PARAM},
        },
        "timeout": 60.0,
    },
    "browser_get_tabs": {
        "action": "get_tabs",
        "description": "获取内置浏览器当前已打开的所有标签页列表（含标签页 ID、标题、URL、是否当前激活）。",
        "parameters": {
            "type": "object",
            "properties": {},
        },
        "timeout": 10.0,
    },
    "browser_switch_tab": {
        "action": "switch_tab",
        "description": "切换内置浏览器当前激活的标签页。多标签页浏览时，可先调用 browser_get_tabs 查到 tab_id 后切换。",
        "parameters": {
            "type": "object",
            "properties": {
                "tab_id": {
                    "type": "string",
                    "description": "目标标签页 ID",
                },
            },
            "required": ["tab_id"],
        },
        "timeout": 10.0,
    },
    "browser_open_tab": {
        "action": "open_tab",
        "description": "在内置浏览器中新建一个标签页，并可选择性打开指定网址。",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "初始打开的网址（可选）",
                },
                "title": {
                    "type": "string",
                    "description": "标签页预设标题（可选）",
                },
            },
        },
        "timeout": 15.0,
    },
    "browser_close_tab": {
        "action": "close_tab",
        "description": "关闭内置浏览器中指定的标签页。",
        "parameters": {
            "type": "object",
            "properties": {
                "tab_id": {
                    "type": "string",
                    "description": "要关闭的标签页 ID",
                },
            },
            "required": ["tab_id"],
        },
        "timeout": 10.0,
    },
}


# ============================================================================
# 输出格式化：将前端返回的 dict 转为 LLM 友好的文本
# ============================================================================

def _format_output(tool_name: str, data: dict[str, Any]) -> str:
    """将前端执行结果格式化为 LLM 友好的文本输出。"""
    if not data:
        return f"{tool_name} 执行完成（无数据返回）"

    # browser_get_tabs
    if "tabs" in data:
        tabs = data.get("tabs", [])
        active_id = data.get("activeTabId")
        lines = [f"【内置浏览器标签页列表（共 {len(tabs)} 个）】:"]
        for idx, t in enumerate(tabs, 1):
            is_cur = " (当前激活)" if t.get("id") == active_id or t.get("active") else ""
            lines.append(f"{idx}. [{t.get('id')}] {t.get('title') or '无标题'} - {t.get('url') or '空白页'}{is_cur}")
        return "\n".join(lines)

    # browser_switch_tab
    if "tabId" in data and "url" in data:
        return f"已成功切换到标签页 [{data.get('tabId')}]：{data.get('title') or '无标题'} ({data.get('url')})"

    # browser_open_tab
    if "tab_id" in data:
        return f"已成功新建标签页 [{data.get('tab_id')}]：{data.get('title') or '新标签页'} ({data.get('url') or 'about:blank'})"

    # browser_close_tab
    if "closed_tab_id" in data:
        return f"已成功关闭标签页 [{data.get('closed_tab_id')}]"

    # browser_visit（navigate_and_screenshot）
    if "final_url" in data:
        data_url = str(data.get("screenshot", ""))
        ok = bool(data.get("ok"))
        error = data.get("error")
        lines = [
            f"网页访问{'成功' if ok else '未完全加载'}：{data.get('title') or '（无标题）'}",
            f"目标 URL：{data['final_url']}",
        ]
        if data_url:
            lines.append("【视觉截图已就绪】页面画面截图已捕获并传递至视觉上下文。")
        else:
            lines.append("【截图提示】页面加载未生成有效截图。")
        if error:
            lines.append(f"附加状态信息：{error}")
        return "\n".join(lines)

    # 截图：返回简短提示
    if "screenshot" in data:
        return "【视觉截图已就绪】当前页面画面截图已捕获并同步至视觉上下文。"

    # 通用：JSON 序列化
    try:
        text = json.dumps(data, ensure_ascii=False, default=str)
    except Exception:
        text = str(data)
    if len(text) > 2000:
        text = text[:2000] + "...（已截断）"
    return f"{tool_name} 结果：\n{text}"


# ============================================================================
# 通用工具类：按规格表实例化
# ============================================================================

class LuomiBrowserAutomationTool(ToolBase):
    """浏览器只读工具。

    每个实例对应一个 action（navigate_and_screenshot/screenshot），
    通过 WS 调用前端 Electron Main 的 LuomiAutomationExecutor 执行。
    """

    def __init__(self, tool_name: str, spec: dict[str, Any]) -> None:
        self._name = tool_name
        self._spec = spec

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._spec["description"]

    @property
    def parameters(self) -> dict[str, Any]:
        return self._spec["parameters"]

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        action = self._spec["action"]
        timeout = self._spec.get("timeout", 30.0)

        try:
            data = await execute_browser_action(action, arguments, timeout)
            output = _format_output(self._name, data)
            logger.info(f"[BrowserAutomationTool] {self._name} 执行成功")
            return ToolResult.ok(output, metadata=data)
        except ConnectionError as e:
            logger.warning(f"[BrowserAutomationTool] {self._name} 连接失败: {e}")
            return ToolResult.fail(str(e))
        except TimeoutError as e:
            logger.warning(f"[BrowserAutomationTool] {self._name} 超时: {e}")
            return ToolResult.fail(f"浏览器操作超时（{timeout}s）: {e}")
        except Exception as e:
            logger.error(f"[BrowserAutomationTool] {self._name} 执行异常: {e}", exc_info=True)
            return ToolResult.fail(f"浏览器工具执行失败: {e}")


def get_luominest_browser_automation_tools() -> list[LuomiBrowserAutomationTool]:
    """工厂函数：返回全部 2 个浏览器只读工具实例。"""
    return [LuomiBrowserAutomationTool(name, spec) for name, spec in BROWSER_ACTION_SPECS.items()]
