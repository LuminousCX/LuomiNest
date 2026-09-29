"""LuomiNest 对外 MCP 服务器（W6-1 / P0-3 传输安全加固）。

把本地陪伴工具以标准 Model Context Protocol 暴露给外部 AI 客户端
（Claude Desktop / 任何 MCP host）。

- 传输：Streamable HTTP，挂在主 FastAPI 应用 `/mcp` 路径
- 鉴权：Bearer Token（P0-3）——token 首启自动生成并存 config_items
  键 `mcp_server.token`（落库加密）；请求缺 `Authorization: Bearer <token>`
  或不匹配返回 401。经 `/api/v1/mcp/token` 查看、`/api/v1/mcp/token/reset`
  重置；`MCP_SERVER_AUTH=false` 可关闭（不建议）
- 暴露面：陪伴安全工具白名单（记忆四件套+时间线/pin、时间/天气、
  浏览器只读观察、平台网桥、IoT 传感、上下文压缩）
- 不暴露：cli/写文件/启动应用等高权限工具（对齐 W7 裁剪决策）
- stdio 宿主（如 Claude Desktop）可通过 `mcp-remote` 桥接本 HTTP 端点：
  `npx mcp-remote http://127.0.0.1:18000/mcp --header "Authorization: Bearer <token>"`
"""
from app.core.mcp_server.auth import (
    BearerAuthMiddleware,
    get_mcp_token,
    reset_mcp_token,
)
from app.core.mcp_server.server import (
    MCP_EXPOSED_TOOLS,
    attach_luominest_mcp_server,
    build_luominest_mcp_server,
)

__all__ = [
    "BearerAuthMiddleware",
    "MCP_EXPOSED_TOOLS",
    "attach_luominest_mcp_server",
    "build_luominest_mcp_server",
    "get_mcp_token",
    "reset_mcp_token",
]
