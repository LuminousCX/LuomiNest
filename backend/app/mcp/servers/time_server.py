"""
时间 MCP Server —— 把现有 time_tool 封装为标准 MCP 工具服务

MCP 协议版本：2024-11-05
通信方式：stdio（标准输入/输出），JSON-RPC 2.0

提供的工具：
  - get_current_time：获取当前日期、时间、星期信息

设计原则：
  1. 纯 MCP 协议封装层，业务逻辑完全复用 time_tool.py 和 SkillRegistry
  2. 严格遵循 MCP 官方规范（tools/list + tools/call + initialize）
  3. 零外部依赖（仅用 Python 标准库），可在任意环境直接运行
  4. 全链路异常处理，工具调用失败时返回结构化错误内容

用法（命令行启动）：
  python -m app.mcp.servers.time_server

用法（Trae 配置 .trae/mcp.json）：
  {
    "mcpServers": {
      "luomi-time": {
        "command": "python",
        "args": ["-m", "app.mcp.servers.time_server"],
        "cwd": "/path/to/LuomiNest/backend"
      }
    }
  }
"""

import sys
import json
import asyncio
from datetime import datetime
from loguru import logger


# =============================================================================
# 工具定义（符合 MCP Tool 规范）
# =============================================================================

TOOLS = [
    {
        "name": "get_current_time",
        "description": (
            "获取当前日期和时间信息。返回包含日期、时间、星期、年、月、日、时、分、秒的详细数据。"
            "用户询问'现在几点'、'今天几号'、'今天星期几'时使用此工具。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]


# =============================================================================
# 工具调用处理 —— 复用现有 time_tool 逻辑
# =============================================================================

def _call_get_current_time(arguments: dict) -> str:
    """调用获取当前时间 —— 优先使用 time_tool，降级使用 SkillRegistry

    两层降级策略：
      1. 尝试导入 TimeTool（自然语言格式回复，更友好）
      2. 降级到 SkillRegistry._builtin_get_time（结构化 JSON 回复）
      3. 最终兜底：纯 Python datetime
    """
    # 第一层：使用 time_tool.py 的 TimeTool（自然语言回复）
    try:
        from app.utils.time_tool import TimeTool
        tool = TimeTool(timezone="Asia/Shanghai")
        return tool.get_reply("all")
    except Exception as e:
        logger.debug(f"[MCP-Time] TimeTool 不可用 ({e})，降级到 SkillRegistry")

    # 第二层：降级到 SkillRegistry 内置的时间获取
    try:
        from app.runtime.plugin.skill.registry import SkillRegistry
        import asyncio as _asyncio
        try:
            loop = _asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            logger.debug("[MCP-Time] 已在运行的事件循环中，跳过 SkillRegistry 异步调用")
        else:
            result = _asyncio.run(SkillRegistry._builtin_get_time())
            data = result.data if hasattr(result, "data") else result
            weekday = data.get("weekday", "")
            date = data.get("date", "")
            time = data.get("time", "")
            return f"日期：{date} {weekday}，时间：{time}"
    except Exception as e:
        logger.debug(f"[MCP-Time] SkillRegistry 不可用 ({e})，降级到纯 datetime")

    # 第三层：最终兜底 —— 纯 Python 标准库
    now = datetime.now()
    weekday_names = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    weekday = weekday_names[now.weekday()]
    return (
        f"日期：{now.strftime('%Y-%m-%d')} {weekday}，"
        f"时间：{now.strftime('%H:%M:%S')}"
    )


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

    参数:
        request: 解析后的 JSON-RPC 请求字典

    返回:
        JSON 响应字符串，通知类请求返回 None
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
                "name": "luomi-time-server",
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

        if tool_name == "get_current_time":
            try:
                result_text = _call_get_current_time(arguments)
                return _build_response(request_id, {
                    "content": [
                        {"type": "text", "text": result_text},
                    ],
                })
            except Exception as e:
                return _build_response(request_id, {
                    "content": [
                        {"type": "text", "text": f"获取时间信息失败：{e}"},
                    ],
                    "isError": True,
                })
        else:
            return _build_error(request_id, -32601, f"未知工具: {tool_name}")

    # ----- 未知方法 -----
    return _build_error(request_id, -32601, f"未知方法: {method}")


# =============================================================================
# 主循环 —— stdio 通信
# =============================================================================

async def run_server():
    """MCP Server 主循环 —— 从 stdin 读取 JSON-RPC 请求，处理后写到 stdout

    使用 run_in_executor 将阻塞读取放到线程池，
    兼容 Windows 和所有平台。
    """
    loop = asyncio.get_running_loop()

    async def _read_line() -> str:
        try:
            line = await asyncio.wait_for(
                loop.run_in_executor(None, sys.stdin.readline),
                timeout=300,
            )
            return line
        except TimeoutError:
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

        # 输出响应
        if response is not None:
            sys.stdout.write(response + "\n")
            sys.stdout.flush()


def create_time_server():
    """工厂函数 —— 创建并返回时间 MCP Server 的启动函数

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

    logger.info("LuomiNest 时间 MCP Server 启动中...")
    logger.info("工具列表: get_current_time")
    logger.info("协议版本: 2024-11-05")
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        logger.info("时间 MCP Server 已停止")
    except Exception as e:
        logger.error(f"时间 MCP Server 异常退出: {e}")
        sys.exit(1)
