"""LuomiNest MCP 数据模型。

定义 MCP 服务器配置与状态的数据结构：
- McpTransportType：传输方式枚举（stdio / sse）
- McpServerConfig：服务器配置（持久化到 mcp_servers.json）
- McpServerStatus：运行时状态枚举
"""
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class McpTransportType(str, Enum):
    """MCP 传输方式"""
    STDIO = "stdio"
    SSE = "sse"


class McpServerStatus(str, Enum):
    """MCP 服务器运行时状态"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    ERROR = "error"


class McpServerConfig(BaseModel):
    """MCP 服务器配置

    Attributes:
        name: 服务器唯一名称
        transport: 传输方式（stdio / sse）
        command: stdio 模式的可执行命令
        args: stdio 模式的命令参数
        env: stdio 模式的环境变量
        cwd: stdio 模式的工作目录
        url: sse 模式的服务器 URL
        headers: sse 模式的请求头
        description: 服务器描述
        enabled: 是否启用
        auto_connect: 是否在初始化时自动连接
    """
    name: str
    transport: McpTransportType
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] | None = None
    cwd: str | None = None
    url: str | None = None
    headers: dict[str, str] | None = None
    description: str = ""
    enabled: bool = True
    auto_connect: bool = True

    def to_public_dict(self) -> dict[str, Any]:
        """转换为可公开返回的字典（含运行时占位字段，供 API 统一返回）"""
        return {
            "name": self.name,
            "transport": self.transport.value,
            "command": self.command,
            "args": self.args,
            "env": self.env,
            "cwd": self.cwd,
            "url": self.url,
            "headers": self.headers,
            "description": self.description,
            "enabled": self.enabled,
            "auto_connect": self.auto_connect,
        }
