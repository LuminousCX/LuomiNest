"""
MCP Server 子包 —— 存放所有标准 MCP Server 实现

每个 Server 是一个独立的 Python 模块，
可通过 stdio（标准输入/输出）以 JSON-RPC 2.0 协议与 MCP 客户端通信。
"""

from app.mcp.servers.time_server import create_time_server
from app.mcp.servers.weather_server import create_weather_server

__all__ = ["create_time_server", "create_weather_server"]
