"""LuomiNest MCP 服务器构建与挂载（mcp SDK v2 MCPServer）。

实现说明：
- 工具 schema 直接复用 ToolRegistry 的 OpenAI JSON Schema——通过 exec 为每个
  工具生成真实签名的 async 包装函数（SDK 服务端校验按函数签名建模，仅改
  Tool.parameters 会在调用期被签名模型拒绝），随后用注册表 schema 覆盖
  Tool.parameters，保证对外暴露的定义与本地完全一致。
- streamable_http_app 返回的 Starlette 子应用挂载在主应用 /mcp 下；
  子应用 lifespan 不会随主应用启动，因此 session_manager.run() 由
  attach_luominest_mcp_server 经 AsyncExitStack 绑定到主应用 lifespan。
"""
from __future__ import annotations

import json
from contextlib import AsyncExitStack
from typing import Any, Callable

from loguru import logger

from app.core.tools.registry import tool_registry

# 对外暴露白名单：陪伴安全工具（只读/记忆/桥接），不含高权限工具
MCP_EXPOSED_TOOLS: list[str] = [
    "memory_search",
    "memory_add",
    "memory_update",
    "memory_forget",
    "memory_get_daily",
    "memory_pin",
    "get_current_time",
    "query_weather",
    "compress_context",
    "browser_visit",
    "browser_screenshot",
    "platform_invoke",
    "iot_get_sensor_data",
]

_MCP_INSTRUCTIONS = (
    "LuomiNest 陪伴型 AI 的本地工具服务。你可以检索/增删改用户长期记忆、"
    "查询时间与天气、观察内置浏览器页面（截图需视觉模型）、经 platform_invoke "
    "操作已连接的聊天平台（QQ/微信/Discord/Telegram）、读取 IoT 传感器遥测。"
    "所有数据存储在用户本地。"
)


async def _execute_registry_tool(tool_name: str, arguments: dict[str, Any]) -> str:
    """执行注册表工具并返回 LLM 可读文本；失败抛异常让 MCP 标记 is_error。"""
    tool = tool_registry.get(tool_name)
    if tool is None:
        raise RuntimeError(f"工具 {tool_name} 未注册")
    result = await tool.execute(arguments)
    if result.success:
        return result.output or "（工具执行成功，无文本输出）"
    raise RuntimeError(result.error or "工具执行失败")


def _make_dynamic_fn(tool_name: str, parameters: dict[str, Any]) -> Callable:
    """按 JSON Schema 生成真实签名的 async 包装函数（SDK 校验按签名建模）。"""
    properties = (parameters or {}).get("properties") or {}
    required = set((parameters or {}).get("required") or [])
    parts: list[str] = []
    for raw_name in properties:
        safe = "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in str(raw_name))
        if not safe or safe[0].isdigit():
            safe = f"arg_{safe}"
        parts.append(f"{safe}: Any" if raw_name in required else f"{safe}: Any = None")
    src = "async def _dynamic_fn(" + ", ".join(parts) + "):\n"
    src += "    return await _execute_registry_tool(tool_name, {k: v for k, v in locals().items()})\n"
    namespace: dict[str, Any] = {
        "Any": Any,
        "_execute_registry_tool": _execute_registry_tool,
        "tool_name": tool_name,
    }
    exec(src, namespace)
    return namespace["_dynamic_fn"]


def build_luominest_mcp_server():
    """构建 LuomiNest MCP 服务器实例（mcp SDK v2 MCPServer）。"""
    from mcp.server import MCPServer
    from mcp.server.mcpserver.tools import Tool

    tools = []
    missing: list[str] = []
    for name in MCP_EXPOSED_TOOLS:
        tool = tool_registry.get(name)
        if tool is None:
            missing.append(name)
            continue
        parameters = json.loads(json.dumps(tool.parameters))  # 深拷贝
        fn = _make_dynamic_fn(name, parameters)
        mcp_tool = Tool.from_function(fn=fn, name=name, description=tool.description)
        mcp_tool.parameters = parameters
        tools.append(mcp_tool)
    if missing:
        logger.warning(f"[McpServer] 白名单中未注册的工具已跳过: {missing}")

    server = MCPServer(
        "luominest",
        title="LuomiNest Companion",
        description="LuomiNest 陪伴型 AI 本地工具（记忆/时间/天气/浏览器观察/平台桥接/IoT）",
        instructions=_MCP_INSTRUCTIONS,
        tools=tools,
    )
    logger.info(f"[McpServer] 构建完成，暴露 {len(tools)}/{len(MCP_EXPOSED_TOOLS)} 个工具")
    return server


async def attach_luominest_mcp_server(app) -> None:
    """把 MCP 服务器挂载到主 FastAPI 应用 /mcp 路径，并绑定 session manager 生命周期。

    - session_manager.run() 是 async context manager，子应用挂载不会自动运行它，
      这里经 AsyncExitStack 绑定：启动时进入、主应用 shutdown 时经
      shutdown_luominest_mcp_server 关闭。
    """
    server = build_luominest_mcp_server()
    asgi_app = server.streamable_http_app(
        stateless_http=True,
        json_response=True,
        streamable_http_path="/",
    )
    app.mount("/mcp", asgi_app, name="luominest-mcp")

    stack = AsyncExitStack()
    await stack.enter_async_context(server.session_manager.run())
    app.state.luominest_mcp_exit_stack = stack
    logger.info("[McpServer] 已挂载到 /mcp（Streamable HTTP，仅本机访问）")


async def shutdown_luominest_mcp_server(app) -> None:
    """关闭 MCP session manager（主应用 lifespan shutdown 调用）。"""
    stack = getattr(app.state, "luominest_mcp_exit_stack", None)
    if stack is not None:
        try:
            await stack.aclose()
        except Exception:
            logger.debug("[McpServer] session manager 关闭异常（忽略）", exc_info=True)
        app.state.luominest_mcp_exit_stack = None
