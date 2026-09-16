"""LuomiNest 浏览器观察工具集。

仅保留 2 个**只读**工具（产品定位：内置浏览器精简为只读——
Agent 只需"访问网页 + 看见"内嵌浏览器，不做任何页面交互）：
- browser_visit: 打开网址 → 等待加载 → 自动截图（复合动作，一次返回结果）
- browser_screenshot: 对当前浏览器页面重新截图（base64 PNG）

通过 WebSocket 调用前端 Electron Main 的 LuomiAutomationExecutor 执行
（Electron 原生 API，不依赖 Playwright/Puppeteer）。

设计模式：DRY 规格表
- BROWSER_ACTION_SPECS 描述每个工具的 name/action/description/parameters/timeout
- LuomiBrowserAutomationTool 通用类按规格实例化
- get_luominest_browser_automation_tools() 工厂返回全部工具实例

历史说明：曾包含 29 个全量自动化工具（导航/交互/标签页/等待/execute_js 等），
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
            "→ 自动截图。返回 JSON：ok（是否加载成功）、final_url（最终 URL，含重定向）、"
            "title（页面标题）、screenshot（data URL 格式的 base64 PNG 截图）。"
            "加载超时或失败时仍会尽力返回当前截图与已获得的信息（ok=false）。"
            "只读操作，不会与页面交互。"
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
        "description": "截取内置浏览器当前页面的最新截图。返回 data URL（base64 PNG）。",
        "parameters": {
            "type": "object",
            "properties": {"tab_id": _TAB_ID_PARAM},
        },
        "timeout": 60.0,
    },
}


# ============================================================================
# 输出格式化：将前端返回的 dict 转为 LLM 友好的文本
# ============================================================================

def _format_output(tool_name: str, data: dict[str, Any]) -> str:
    """将前端执行结果格式化为 LLM 友好的文本输出。

    策略：
    - 截图：不返回 base64（避免 token 爆炸），仅提示已生成
    - browser_visit：报告访问结果（final_url/title/是否成功）
    - 其他：JSON 序列化后截断
    """
    if not data:
        return f"{tool_name} 执行成功（无返回数据）"

    # browser_visit（navigate_and_screenshot）：包含 final_url/title/screenshot
    if "final_url" in data:
        data_url = str(data.get("screenshot", ""))
        ok = bool(data.get("ok"))
        error = data.get("error")
        lines = [
            f"访问{'成功' if ok else '未完全成功'}：{data.get('title') or '（无标题）'}",
            f"最终 URL：{data['final_url']}",
        ]
        if data_url:
            lines.append(f"截图已生成（data URL 长度 {len(data_url)} 字符，PNG 格式）")
        else:
            lines.append("截图未生成")
        if error:
            lines.append(f"加载信息：{error}")
        return "\n".join(lines)

    # 截图：返回简短提示，完整 data URL 在 metadata
    if "screenshot" in data:
        data_url = str(data.get("screenshot", ""))
        return f"截图已生成（data URL 长度 {len(data_url)} 字符，PNG 格式）"

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
