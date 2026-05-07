"""
天气 MCP Server —— 把现有天气爬虫工具封装为标准 MCP 工具服务

MCP 协议版本：2024-11-05
通信方式：stdio（标准输入/输出），JSON-RPC 2.0

提供的工具：
  - get_weather_info：获取指定城市的天气信息（含温度、天气状况、出行建议）

设计原则：
  1. 纯 MCP 协议封装层，业务逻辑完全复用 weather.py 的 get_weather 函数
  2. 严格遵循 MCP 官方规范（tools/list + tools/call + initialize）
  3. 支持异步天气查询（Open-Meteo API），带本地缓存（复用 weather.py 缓存）
  4. 全链路异常处理，工具调用失败时返回结构化错误内容

用法（命令行启动）：
  python -m app.mcp.servers.weather_server

用法（Trae 配置 .trae/mcp.json）：
  {
    "mcpServers": {
      "luomi-weather": {
        "command": "python",
        "args": ["-m", "app.mcp.servers.weather_server"],
        "cwd": "/path/to/LuomiNest/backend"
      }
    }
  }
"""

import sys
import json
import asyncio
from datetime import datetime, timedelta
from loguru import logger


# =============================================================================
# 工具定义（符合 MCP Tool 规范）
# =============================================================================

TOOLS = [
    {
        "name": "get_weather_info",
        "description": (
            "获取指定城市的天气信息。返回城市名称、天气状况、气温、出行建议。"
            "当用户询问'天气怎么样'、'会不会下雨'、'穿什么衣服'、'气温多少度'时使用此工具。"
            "支持查询今天、明天、后天的天气。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "城市名称，如：北京、上海、广州、深圳",
                },
                "date": {
                    "type": "string",
                    "description": "日期，如：今天、明天、后天、2026-05-03，默认为今天",
                },
            },
            "required": ["city"],
        },
    },
]


# =============================================================================
# 日期参数解析
# =============================================================================

def _resolve_date(date_input: str) -> str:
    """将自然语言日期（今天/明天/后天）转为 YYYY-MM-DD 格式

    参数:
        date_input: 日期输入，可为 "今天"、"明天"、"后天"、YYYY-MM-DD 或空

    返回:
        YYYY-MM-DD 格式的日期字符串
    """
    if not date_input or date_input in ["今天", "今日", ""]:
        return datetime.now().strftime("%Y-%m-%d")
    if date_input in ["明天", "明日"]:
        return (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    if date_input in ["后天"]:
        return (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
    # 已经是 YYYY-MM-DD 格式或其它格式，原样返回
    return date_input


# =============================================================================
# 工具调用处理 —— 复用现有天气爬虫逻辑
# =============================================================================

async def _call_get_weather_info(arguments: dict) -> str:
    """调用获取天气信息 —— 复用 weather.py 的 get_weather 和 _format_weather_for_user

    三层降级策略：
      1. 尝试导入 weather.py 的 get_weather（完整 Open-Meteo API + 缓存）
      2. 降级到 SkillRegistry（如果天气已注册）
      3. 最终兜底：返回结构化错误信息

    参数:
        arguments: {"city": "北京", "date": "今天"}

    返回:
        格式化的天气信息自然语言字符串
    """
    city = arguments.get("city", "")
    date_input = arguments.get("date", "")

    if not city:
        return "请提供城市名称，如：北京、上海、广州"

    date = _resolve_date(date_input)

    # 第一层：使用 weather.py 的 get_weather（完整 API + 缓存）
    try:
        from app.runtime.plugin.skill.builtin.weather import (
            get_weather,
            _format_weather_for_user,
        )
        result = await get_weather(city=city, date=date_input)
        if result.success and result.data:
            # weather.py 的 get_weather 已在内部调用了 _format_weather_for_user
            formatted = result.data.get("formatted", "")
            if formatted:
                return formatted
            # 回退：手动格式化
            return _format_weather_for_user(result.data)
        return result.error or "未能获取天气数据"
    except Exception as e:
        logger.debug(f"[MCP-Weather] weather.py 不可用 ({e})，降级到 SkillRegistry")

    # 第二层：降级到 SkillRegistry
    try:
        from app.runtime.plugin.skill.registry import SkillRegistry
        handler = SkillRegistry.get_handler("get_weather")
        if handler:
            result = await handler(city=city, date=date_input)
            if hasattr(result, "to_text"):
                return result.to_text()
            return str(result)
        return f"天气工具未注册，无法获取 {city} 的天气信息。"
    except Exception as e:
        logger.debug(f"[MCP-Weather] SkillRegistry 不可用 ({e})，降级到兜底")

    # 第三层：最终兜底
    return f"暂时无法获取 {city}（{date}）的天气数据，建议查看天气预报应用获取最新信息。"


# =============================================================================
# MCP 协议处理 —— JSON-RPC 2.0 over stdio
# =============================================================================

def _build_response(request_id, result):
    """构建成功响应"""
    return json.dumps({
        "jsonrpc": "2.0",
        "id": request_id,
        "result": result,
    }, ensure_ascii=False)


def _build_error(request_id, code: int, message: str):
    """构建错误响应"""
    return json.dumps({
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": code,
            "message": message,
        },
    }, ensure_ascii=False)


def handle_request(request: dict) -> str | None:
    """处理单个 JSON-RPC 请求，返回响应 JSON 字符串

    支持的 MCP 方法：
      - initialize：握手初始化
      - tools/list：列出工具
      - tools/call：调用工具
      - notifications/initialized：初始化通知（无需响应）

    注意：tools/call 中的天气查询是异步的，需要在主循环中 await。
          此函数返回一个特殊标记 "ASYNC_WEATHER"，主循环检测到后执行异步调用。

    参数:
        request: 解析后的 JSON-RPC 请求字典

    返回:
        JSON 响应字符串，通知类请求返回 None，
        tools/call 天气请求返回 ("ASYNC_WEATHER", request_id, arguments) 元组
    """
    method = request.get("method", "")
    request_id = request.get("id")
    params = request.get("params", {})

    # ----- initialize：MCP 握手 -----
    if method == "initialize":
        return _build_response(request_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {},
            },
            "serverInfo": {
                "name": "luomi-weather-server",
                "version": "1.0.0",
            },
        })

    # ----- notifications/initialized：初始化完成（无需响应）-----
    if method == "notifications/initialized":
        return None

    # ----- tools/list：返回工具列表 -----
    if method == "tools/list":
        return _build_response(request_id, {"tools": TOOLS})

    # ----- tools/call：执行工具调用 -----
    if method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        if tool_name == "get_weather_info":
            # 天气查询是异步的，返回特殊标记让主循环处理
            return ("ASYNC_WEATHER", request_id, arguments)
        else:
            return _build_error(request_id, -32601, f"未知工具: {tool_name}")

    # ----- 未知方法 -----
    return _build_error(request_id, -32601, f"未知方法: {method}")


async def _handle_weather_call(request_id, arguments: dict) -> str:
    """处理异步天气查询并构建响应"""
    try:
        result_text = await _call_get_weather_info(arguments)
        return _build_response(request_id, {
            "content": [
                {"type": "text", "text": result_text},
            ],
        })
    except Exception as e:
        return _build_response(request_id, {
            "content": [
                {"type": "text", "text": f"获取天气信息失败：{e}"},
            ],
            "isError": True,
        })


# =============================================================================
# 主循环 —— stdio 通信
# =============================================================================

async def run_server():
    """MCP Server 主循环 —— 从 stdin 读取 JSON-RPC 请求，处理后写到 stdout

    天气查询是异步的（httpx 请求 Open-Meteo API），
    在主循环中 await 确保非阻塞执行。
    """
    loop = asyncio.get_event_loop()

    async def _read_line() -> str:
        try:
            line = await asyncio.wait_for(
                loop.run_in_executor(None, sys.stdin.readline),
                timeout=300,
            )
            return line
        except asyncio.TimeoutError:
            return ""

    while True:
        try:
            line = await _read_line()
        except Exception:
            break

        if not line:
            break

        line = line.strip()
        if not line:
            continue

        # 解析 JSON-RPC 请求
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            err = _build_error(None, -32700, "JSON 解析错误")
            sys.stdout.write(err + "\n")
            sys.stdout.flush()
            continue

        # 处理请求
        try:
            response = handle_request(request)
        except Exception as e:
            response = _build_error(
                request.get("id"),
                -32603,
                f"内部错误: {e}",
            )

        # 处理异步天气调用
        if isinstance(response, tuple) and response[0] == "ASYNC_WEATHER":
            _, req_id, args = response
            response = await _handle_weather_call(req_id, args)

        # 输出响应
        if response is not None:
            sys.stdout.write(response + "\n")
            sys.stdout.flush()


def create_weather_server():
    """工厂函数 —— 创建并返回天气 MCP Server 的启动函数

    返回:
        run_server 协程，调用方可 await 启动服务
    """
    return run_server


# =============================================================================
# 直接运行入口
# =============================================================================

if __name__ == "__main__":
    # 配置 loguru 输出到 stderr（避免污染 stdout 的 JSON-RPC 通信）
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="<level>{level}</level> | {message}")

    logger.info("LuomiNest 天气 MCP Server 启动中...")
    logger.info("工具列表: get_weather_info")
    logger.info("协议版本: 2024-11-05")
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        logger.info("天气 MCP Server 已停止")
    except Exception as e:
        logger.error(f"天气 MCP Server 异常退出: {e}")
        sys.exit(1)
