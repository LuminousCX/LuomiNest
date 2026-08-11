"""LuomiNest 浏览器自动化工具集。

29 个浏览器自动化工具，通过 WebSocket 调用前端 Electron Main 的
LuomiAutomationExecutor 执行（Electron 原生 API，不依赖 Playwright/Puppeteer）。

设计模式：DRY 规格表
- BROWSER_ACTION_SPECS 描述每个工具的 name/action/description/parameters/timeout
- LuomiBrowserAutomationTool 通用类按规格实例化，避免 29 个重复类定义
- get_luominest_browser_automation_tools() 工厂返回全部工具实例

工具分类（29 个）：
- 导航(6): navigate/go_back/go_forward/reload/get_url/get_page_title
- 交互(9): click/double_click/right_click/hover/type/clear_input/press_key/select_option/scroll
- 提取(5): get_dom_tree/get_text/get_attribute/get_html/screenshot
- 等待(3): wait_for_load/wait_for_element/wait_for_url
- 执行(2): execute_js/get_history
- 标签页管理(4): get_tabs/switch_tab/open_tab/close_tab

元素定位策略（前端 executor 实现）：
- selector 为纯数字 → 按 data-luomi-index 属性查找（AI 友好）
- selector 为字符串 → 按 CSS 选择器查找
"""
import json
from typing import Any

from loguru import logger

from app.core.tools.registry import ToolBase, ToolResult
from app.core.ports.browser_automation import execute_browser_action


# ============================================================================
# 工具规格表：每个工具的 name → {action, description, parameters, timeout}
# ============================================================================

# 通用可选参数：tab_id（缺省活跃标签）、human（交互类，缺省 true）
_TAB_ID_PARAM = {
    "type": "string",
    "description": "标签页 ID（可选，缺省为当前活跃标签页）",
}

BROWSER_ACTION_SPECS: dict[str, dict[str, Any]] = {
    # ===== 导航类 (6) =====
    "browser_navigate": {
        "action": "navigate",
        "description": (
            "在浏览器当前活跃标签页导航到指定 URL。"
            "适用于打开网页、跳转到新地址。"
            "如需新开标签页，请先使用 create_browser_tab 工具。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "目标 URL（需以 http:// 或 https:// 开头）"},
                "tab_id": _TAB_ID_PARAM,
            },
            "required": ["url"],
        },
        "timeout": 30.0,
    },
    "browser_go_back": {
        "action": "go_back",
        "description": "浏览器后退到上一页（历史记录）。",
        "parameters": {
            "type": "object",
            "properties": {"tab_id": _TAB_ID_PARAM},
        },
        "timeout": 15.0,
    },
    "browser_go_forward": {
        "action": "go_forward",
        "description": "浏览器前进到下一页（历史记录）。",
        "parameters": {
            "type": "object",
            "properties": {"tab_id": _TAB_ID_PARAM},
        },
        "timeout": 15.0,
    },
    "browser_reload": {
        "action": "reload",
        "description": "刷新当前浏览器标签页。",
        "parameters": {
            "type": "object",
            "properties": {"tab_id": _TAB_ID_PARAM},
        },
        "timeout": 30.0,
    },
    "browser_get_url": {
        "action": "get_url",
        "description": "获取当前浏览器标签页的 URL。",
        "parameters": {
            "type": "object",
            "properties": {"tab_id": _TAB_ID_PARAM},
        },
        "timeout": 10.0,
    },
    "browser_get_page_title": {
        "action": "get_page_title",
        "description": "获取当前浏览器标签页的页面标题。",
        "parameters": {
            "type": "object",
            "properties": {"tab_id": _TAB_ID_PARAM},
        },
        "timeout": 10.0,
    },

    # ===== 交互类 (9) =====
    "browser_click": {
        "action": "click",
        "description": (
            "点击页面元素。selector 为纯数字时按 data-luomi-index 索引查找（推荐，先调用 browser_get_dom_tree 获取索引），"
            "否则按 CSS 选择器查找。默认使用人类化鼠标移动（贝塞尔曲线）。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "元素选择器（数字索引或 CSS 选择器）"},
                "tab_id": _TAB_ID_PARAM,
                "human": {"type": "boolean", "description": "是否使用人类化输入（默认 true）"},
            },
            "required": ["selector"],
        },
        "timeout": 30.0,
    },
    "browser_double_click": {
        "action": "double_click",
        "description": "双击页面元素。selector 同 browser_click。",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "元素选择器（数字索引或 CSS 选择器）"},
                "tab_id": _TAB_ID_PARAM,
                "human": {"type": "boolean", "description": "是否使用人类化输入（默认 true）"},
            },
            "required": ["selector"],
        },
        "timeout": 30.0,
    },
    "browser_right_click": {
        "action": "right_click",
        "description": "右键点击页面元素（触发上下文菜单）。selector 同 browser_click。",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "元素选择器（数字索引或 CSS 选择器）"},
                "tab_id": _TAB_ID_PARAM,
            },
            "required": ["selector"],
        },
        "timeout": 30.0,
    },
    "browser_hover": {
        "action": "hover",
        "description": "鼠标悬停在页面元素上（触发 hover 效果）。selector 同 browser_click。",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "元素选择器（数字索引或 CSS 选择器）"},
                "tab_id": _TAB_ID_PARAM,
                "human": {"type": "boolean", "description": "是否使用人类化输入（默认 true）"},
            },
            "required": ["selector"],
        },
        "timeout": 30.0,
    },
    "browser_type": {
        "action": "type",
        "description": (
            "在输入框中输入文本。会先聚焦元素，可选清空原有内容。"
            "默认使用人类化逐字符输入（含随机延迟和偶尔误打纠正）。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "输入框元素选择器（数字索引或 CSS 选择器）"},
                "text": {"type": "string", "description": "要输入的文本内容"},
                "clear": {"type": "boolean", "description": "输入前是否清空原有内容（默认 false）"},
                "tab_id": _TAB_ID_PARAM,
                "human": {"type": "boolean", "description": "是否使用人类化输入（默认 true）"},
            },
            "required": ["selector", "text"],
        },
        "timeout": 60.0,
    },
    "browser_clear_input": {
        "action": "clear_input",
        "description": "清空指定输入框的内容。",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "输入框元素选择器（数字索引或 CSS 选择器）"},
                "tab_id": _TAB_ID_PARAM,
            },
            "required": ["selector"],
        },
        "timeout": 15.0,
    },
    "browser_press_key": {
        "action": "press_key",
        "description": (
            "按下并释放键盘按键。key 为 Electron 键码（如 'Enter', 'Tab', 'Escape', 'ArrowDown'）。"
            "适用于提交表单、切换焦点、快捷键等。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "按键名（如 Enter/Tab/Escape/ArrowDown）"},
                "tab_id": _TAB_ID_PARAM,
            },
            "required": ["key"],
        },
        "timeout": 10.0,
    },
    "browser_select_option": {
        "action": "select_option",
        "description": "在下拉选择框（<select>）中选中指定值的选项。",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "<select> 元素选择器（数字索引或 CSS 选择器）"},
                "value": {"type": "string", "description": "要选中的 option 值（value 属性）"},
                "tab_id": _TAB_ID_PARAM,
            },
            "required": ["selector", "value"],
        },
        "timeout": 15.0,
    },
    "browser_scroll": {
        "action": "scroll",
        "description": (
            "滚动页面。deltaY 正向下、负向上；deltaX 正向右、负向左。"
            "默认向下滚动 300 像素。默认使用人类化滚动（加速/减速）。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "deltaX": {"type": "number", "description": "水平滚动量（正向右，默认 0）"},
                "deltaY": {"type": "number", "description": "垂直滚动量（正向下，默认 300）"},
                "tab_id": _TAB_ID_PARAM,
                "human": {"type": "boolean", "description": "是否使用人类化滚动（默认 true）"},
            },
        },
        "timeout": 30.0,
    },

    # ===== 提取类 (5) =====
    "browser_get_dom_tree": {
        "action": "get_dom_tree",
        "description": (
            "获取当前页面的索引化 DOM 树。每个可交互元素带 data-luomi-index 数字索引，"
            "可用于后续 browser_click/browser_type 等工具的 selector 参数。"
            "建议在执行交互前先调用本工具了解页面结构。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "maxDepth": {"type": "integer", "description": "DOM 树最大深度（默认 10）"},
                "maxElements": {"type": "integer", "description": "最大元素数量（默认 200，防止 token 爆炸）"},
                "tab_id": _TAB_ID_PARAM,
            },
        },
        "timeout": 30.0,
    },
    "browser_get_text": {
        "action": "get_text",
        "description": "获取元素的文本内容。不传 selector 时返回整页文本（最多 5000 字符）。",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "元素选择器（可选，缺省返回整页文本）"},
                "tab_id": _TAB_ID_PARAM,
            },
        },
        "timeout": 15.0,
    },
    "browser_get_attribute": {
        "action": "get_attribute",
        "description": "获取指定元素的某个 HTML 属性值（如 href、src、class 等）。",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "元素选择器（数字索引或 CSS 选择器）"},
                "attribute": {"type": "string", "description": "属性名（如 href/src/class/value）"},
                "tab_id": _TAB_ID_PARAM,
            },
            "required": ["selector", "attribute"],
        },
        "timeout": 15.0,
    },
    "browser_get_html": {
        "action": "get_html",
        "description": "获取元素的 outerHTML（最多 5000 字符）。不传 selector 时返回 body 的 HTML。",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "元素选择器（可选，缺省返回 body）"},
                "tab_id": _TAB_ID_PARAM,
            },
        },
        "timeout": 15.0,
    },
    "browser_screenshot": {
        "action": "screenshot",
        "description": "截取当前浏览器页面的截图。返回 data URL（base64 PNG）。",
        "parameters": {
            "type": "object",
            "properties": {"tab_id": _TAB_ID_PARAM},
        },
        "timeout": 60.0,
    },

    # ===== 等待类 (3) =====
    "browser_wait_for_load": {
        "action": "wait_for_load",
        "description": "等待当前页面加载完成。若页面已在加载中则等待 did-finish-load 事件。",
        "parameters": {
            "type": "object",
            "properties": {
                "timeout": {"type": "number", "description": "超时秒数（默认 30）"},
                "tab_id": _TAB_ID_PARAM,
            },
        },
        "timeout": 35.0,
    },
    "browser_wait_for_element": {
        "action": "wait_for_element",
        "description": "轮询等待指定元素出现在页面中。",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "元素选择器（数字索引或 CSS 选择器）"},
                "timeout": {"type": "number", "description": "超时秒数（默认 30）"},
                "tab_id": _TAB_ID_PARAM,
            },
            "required": ["selector"],
        },
        "timeout": 35.0,
    },
    "browser_wait_for_url": {
        "action": "wait_for_url",
        "description": "等待页面 URL 发生变化（如跳转、重定向）。可选 url_pattern 正则匹配目标 URL。",
        "parameters": {
            "type": "object",
            "properties": {
                "url_pattern": {"type": "string", "description": "目标 URL 正则（可选，缺省只等 URL 变化）"},
                "timeout": {"type": "number", "description": "超时秒数（默认 30）"},
                "tab_id": _TAB_ID_PARAM,
            },
        },
        "timeout": 35.0,
    },

    # ===== 执行类 (2) =====
    "browser_execute_js": {
        "action": "execute_js",
        "description": (
            "在页面中执行任意 JavaScript 代码并返回结果。"
            "适用于复杂操作（如提取动态数据、触发自定义事件）。谨慎使用。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "script": {"type": "string", "description": "要执行的 JavaScript 代码（表达式或语句）"},
                "tab_id": _TAB_ID_PARAM,
            },
            "required": ["script"],
        },
        "timeout": 30.0,
    },
    "browser_get_history": {
        "action": "get_history",
        "description": "获取当前标签页的导航历史状态（可后退/可前进）。",
        "parameters": {
            "type": "object",
            "properties": {"tab_id": _TAB_ID_PARAM},
        },
        "timeout": 10.0,
    },

    # ===== 标签页管理类 (2) =====
    "browser_get_tabs": {
        "action": "get_tabs",
        "description": (
            "获取浏览器当前所有标签页列表（含 id/title/url/active/sleeping/loading 状态）。"
            "在切换标签页前建议先调用本工具获取 tab_id，再使用 browser_switch_tab 切换。"
        ),
        "parameters": {
            "type": "object",
            "properties": {},
        },
        "timeout": 10.0,
    },
    "browser_switch_tab": {
        "action": "switch_tab",
        "description": (
            "切换到指定标签页（使其成为活跃标签页，显示在前台）。"
            "需先通过 browser_get_tabs 获取目标标签页的 tab_id。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "tab_id": {
                    "type": "string",
                    "description": "要切换到的目标标签页 ID（必需）",
                },
            },
            "required": ["tab_id"],
        },
        "timeout": 15.0,
    },
    "browser_open_tab": {
        "action": "open_tab",
        "description": (
            "在浏览器中打开新标签页（始终新开标签，不在当前标签导航）。"
            "适用于需要同时查看多个页面的场景。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "要打开的 URL（可选，缺省为默认页）"},
                "title": {"type": "string", "description": "标签页标题（可选）"},
            },
        },
        "timeout": 15.0,
    },
    "browser_close_tab": {
        "action": "close_tab",
        "description": "关闭浏览器中指定的标签页。",
        "parameters": {
            "type": "object",
            "properties": {
                "tab_id": {"type": "string", "description": "要关闭的标签页 ID"},
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
    """将前端执行结果格式化为 LLM 友好的文本输出。

    策略：
    - 截图：不返回 base64（避免 token 爆炸），仅提示已生成
    - DOM 树：格式化为缩进文本，截断到 4000 字符
    - 文本/HTML：截断到合理长度
    - 其他：JSON 序列化后截断
    """
    if not data:
        return f"{tool_name} 执行成功（无返回数据）"

    # 截图：返回简短提示，完整 data URL 在 metadata
    if "screenshot" in data:
        data_url = str(data.get("screenshot", ""))
        return f"截图已生成（data URL 长度 {len(data_url)} 字符，PNG 格式）"

    # DOM 树：尝试格式化
    if "tree" in data or "root" in data:
        try:
            tree_text = _format_dom_tree(data.get("tree") or data.get("root"), 0)
            if len(tree_text) > 4000:
                tree_text = tree_text[:4000] + "\n...（DOM 树已截断，共更多节点）"
            return f"DOM 树：\n{tree_text}"
        except Exception:
            pass

    # URL / 标题
    if "url" in data and len(data) == 1:
        return f"当前 URL: {data['url']}"
    if "title" in data and len(data) == 1:
        return f"页面标题: {data['title']}"

    # 文本内容
    if "text" in data:
        text = str(data["text"])
        if len(text) > 4000:
            text = text[:4000] + "...（已截断）"
        tag = data.get("tag", "")
        return f"元素文本{f'（<{tag}>）' if tag else ''}：\n{text}"

    # HTML
    if "html" in data:
        html = str(data["html"])
        if len(html) > 4000:
            html = html[:4000] + "...（已截断）"
        return f"元素 HTML：\n{html}"

    # 属性
    if "attribute" in data and "value" in data:
        return f"属性 {data['attribute']} = {data['value']}"

    # 历史状态
    if "canGoBack" in data or "canGoForward" in data:
        return f"导航历史：可后退={data.get('canGoBack')}, 可前进={data.get('canGoForward')}, 当前索引={data.get('activeIndex', '未知')}"

    # 标签页列表
    if "tabs" in data and isinstance(data.get("tabs"), list):
        tabs_list = data["tabs"]
        active_id = data.get("activeTabId")
        lines = [f"当前共 {data.get('count', len(tabs_list))} 个标签页："]
        for t in tabs_list:
            mark = "★" if t.get("id") == active_id else " "
            state = []
            if t.get("loading"):
                state.append("加载中")
            if t.get("sleeping"):
                state.append("休眠")
            state_str = f"（{','.join(state)}）" if state else ""
            title = str(t.get("title", ""))[:40]
            lines.append(f"  {mark} [{t.get('id')}] {title}{state_str}")
            lines.append(f"      URL: {t.get('url', '')}")
        return "\n".join(lines)

    # 标签页切换结果
    if "tabId" in data and "title" in data and "url" in data and len(data) == 3:
        return f"已切换到标签页：{data['title']}\nURL: {data['url']}"

    # 通用：JSON 序列化
    try:
        text = json.dumps(data, ensure_ascii=False, default=str)
    except Exception:
        text = str(data)
    if len(text) > 2000:
        text = text[:2000] + "...（已截断）"
    return f"{tool_name} 结果：\n{text}"


def _format_dom_tree(node: Any, depth: int) -> str:
    """递归格式化 DOM 树节点为缩进文本。"""
    if not isinstance(node, dict):
        return str(node)

    indent = "  " * depth
    index = node.get("index")
    tag = node.get("tag", "?")
    role = node.get("role", "")
    text = str(node.get("text", "")).strip()[:60]

    # 索引标记（AI 据此构造 selector）
    index_mark = f"[{index}]" if index is not None else ""
    role_mark = f" role={role}" if role else ""
    text_mark = f" \"{text}\"" if text else ""

    lines = [f"{indent}<{tag}>{index_mark}{role_mark}{text_mark}"]

    children = node.get("children", [])
    if isinstance(children, list):
        for child in children[:20]:  # 每层最多 20 个子节点
            lines.append(_format_dom_tree(child, depth + 1))

    return "\n".join(lines)


# ============================================================================
# 通用工具类：按规格表实例化
# ============================================================================

class LuomiBrowserAutomationTool(ToolBase):
    """浏览器自动化通用工具。

    每个实例对应一个 action（如 navigate/click/screenshot），
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
            return ToolResult.fail(f"浏览器自动化执行失败: {e}")


def get_luominest_browser_automation_tools() -> list[LuomiBrowserAutomationTool]:
    """工厂函数：返回全部 27 个浏览器自动化工具实例。"""
    return [LuomiBrowserAutomationTool(name, spec) for name, spec in BROWSER_ACTION_SPECS.items()]
