"""LuomiNest MCP 子包。

提供 MCP（Model Context Protocol）客户端管理能力：
- models：数据模型（McpServerConfig / McpTransportType / McpServerStatus）
- manager：MCP 管理器单例（mcp_manager）

使用方式：
    from app.core.tools.mcp.manager import mcp_manager
    from app.core.tools.mcp.models import McpServerConfig, McpTransportType
"""
from app.core.tools.mcp.models import McpServerConfig, McpServerStatus, McpTransportType

__all__ = ["McpServerConfig", "McpServerStatus", "McpTransportType"]
