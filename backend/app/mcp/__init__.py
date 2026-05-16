"""
LuomiNest MCP 服务包

提供符合 MCP（Model Context Protocol）2024-11-05 标准的工具 Server。
每个 Server 可独立运行，通过 stdio JSON-RPC 2.0 与 MCP 客户端通信。

提供的 MCP Server：
  - time_server：时间查询工具（get_current_time）
  - weather_server：天气查询工具（get_weather_info）

使用方式：
  # 直接运行（命令行启动）
  python -m app.mcp.servers.time_server
  python -m app.mcp.servers.weather_server

  # Trae IDE 配置（.trae/mcp.json）
  {
    "mcpServers": {
      "luomi-time": {
        "command": "python",
        "args": ["-m", "app.mcp.servers.time_server"],
        "cwd": "/path/to/LuomiNest/backend"
      },
      "luomi-weather": {
        "command": "python",
        "args": ["-m", "app.mcp.servers.weather_server"],
        "cwd": "/path/to/LuomiNest/backend"
      }
    }
  }

  # 编程方式调用
  from app.mcp.servers import create_time_server, create_weather_server
  time_srv = create_time_server()
  await time_srv()
"""

from app.mcp.servers import create_time_server, create_weather_server

__all__ = ["create_time_server", "create_weather_server"]
