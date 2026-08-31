"""MCP 服务器管理 API。

提供 MCP 服务器的增删改查、连接管理、工具列表查询等接口。
"""
import os
from typing import Any

from fastapi import APIRouter
from loguru import logger
from pydantic import BaseModel, Field

from app.core.exceptions import BadRequestError, NotFoundError

from app.core.tools.mcp.manager import mcp_manager
from app.core.tools.mcp.models import McpServerConfig, McpTransportType
from app.core.utils import ok

router = APIRouter(prefix="/mcp", tags=["mcp"])


# ------------------------------------------------------------------
# MCP 子进程安全环境变量
# ------------------------------------------------------------------

# 安全环境变量白名单（允许传递给 MCP 子进程）
SAFE_ENV_VARS: set[str] = {
    "PATH", "HOME", "USERPROFILE", "SYSTEMROOT", "WINDIR",
    "TEMP", "TMP", "LANG", "LC_ALL",
    "PYTHONPATH", "VIRTUAL_ENV", "CONDA_PREFIX",
}

# 环境变量前缀白名单（匹配的变量也允许传递）
SAFE_ENV_PREFIX: tuple[str, ...] = ("XDG_", "LC_", "LANG_")

# 敏感环境变量关键字（即使匹配白名单也要排除）
_SENSITIVE_KEYWORDS: tuple[str, ...] = (
    "KEY", "SECRET", "TOKEN", "PASSWORD", "CREDENTIAL",
)


def _build_safe_env(environ: dict[str, str] | None = None) -> dict[str, str]:
    """构建安全的子进程环境变量。

    仅保留白名单内的环境变量，并排除所有包含敏感关键字的变量
    （如 API Key、Token 等）。

    Args:
        environ: 源环境变量，默认使用 os.environ。

    Returns:
        过滤后的安全环境变量字典。
    """
    if environ is None:
        environ = dict(os.environ)

    safe: dict[str, str] = {}
    for key, value in environ.items():
        # 排除包含敏感关键字的变量
        upper_key = key.upper()
        if any(kw in upper_key for kw in _SENSITIVE_KEYWORDS):
            continue
        # 精确白名单匹配
        if key in SAFE_ENV_VARS:
            safe[key] = value
        # 前缀白名单匹配
        elif any(key.startswith(prefix) for prefix in SAFE_ENV_PREFIX):
            safe[key] = value
    return safe


# ------------------------------------------------------------------
# 请求模型
# ------------------------------------------------------------------

class CreateServerRequest(BaseModel):
    """创建 MCP 服务器请求。"""
    name: str = Field(..., description="服务器唯一名称")
    transport: McpTransportType = Field(..., description="传输方式：stdio 或 sse")
    command: str | None = Field(None, description="stdio: 可执行命令")
    args: list[str] = Field(default_factory=list, description="stdio: 命令参数")
    env: dict[str, str] | None = Field(None, description="stdio: 环境变量")
    cwd: str | None = Field(None, description="stdio: 工作目录")
    url: str | None = Field(None, description="sse: 服务器 URL")
    headers: dict[str, str] | None = Field(None, description="sse: 请求头")
    description: str = ""
    enabled: bool = True
    auto_connect: bool = True


class UpdateServerRequest(BaseModel):
    """更新 MCP 服务器请求。"""
    transport: McpTransportType | None = None
    command: str | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None
    cwd: str | None = None
    url: str | None = None
    headers: dict[str, str] | None = None
    description: str | None = None
    enabled: bool | None = None
    auto_connect: bool | None = None


class ServerActionRequest(BaseModel):
    """服务器操作请求。"""
    action: str = Field(..., description="操作类型：connect, disconnect, reconnect")


# ------------------------------------------------------------------
# 响应模型
# ------------------------------------------------------------------

class ServerListResponse(BaseModel):
    success: bool = True
    servers: list[dict[str, Any]] = []
    count: int = 0


class ServerDetailResponse(BaseModel):
    success: bool = True
    server: dict[str, Any] | None = None


class ServerActionResponse(BaseModel):
    success: bool
    message: str


class ToolListResponse(BaseModel):
    success: bool = True
    tools: list[dict[str, Any]] = []
    count: int = 0


# ------------------------------------------------------------------
# 路由
# ------------------------------------------------------------------

@router.get("/servers", response_model=ServerListResponse)
async def list_servers():
    """列出所有 MCP 服务器配置及状态。"""
    servers = mcp_manager.list_servers()
    return ServerListResponse(servers=servers, count=len(servers))


@router.get("/servers/{name}", response_model=ServerDetailResponse)
async def get_server(name: str):
    """获取单个 MCP 服务器详情（含工具列表）。"""
    server = mcp_manager.get_server(name)
    if server is None:
        raise NotFoundError(f"Server '{name}' not found", code="MCP_SERVER_NOT_FOUND")
    return ServerDetailResponse(server=server)


@router.post("/servers", response_model=ServerActionResponse)
async def create_server(req: CreateServerRequest):
    """添加 MCP 服务器配置并可选自动连接。"""
    config = McpServerConfig(
        name=req.name,
        transport=req.transport,
        command=req.command,
        args=req.args,
        env=req.env,
        cwd=req.cwd,
        url=req.url,
        headers=req.headers,
        description=req.description,
        enabled=req.enabled,
        auto_connect=req.auto_connect,
    )
    success, message = await mcp_manager.add_server(config)
    if not success:
        raise BadRequestError(message, code="MCP_OPERATION_FAILED")
    logger.info(f"[McpAPI] Created server: {req.name}")
    return ServerActionResponse(success=success, message=message)


@router.put("/servers/{name}", response_model=ServerActionResponse)
async def update_server(name: str, req: UpdateServerRequest):
    """更新 MCP 服务器配置（会触发重连）。"""
    existing = mcp_manager.get_server(name)
    if existing is None:
        raise NotFoundError(f"Server '{name}' not found", code="MCP_SERVER_NOT_FOUND")

    # 合并更新
    update_data = req.model_dump(exclude_unset=True)
    merged = {**existing, **update_data}
    # 移除非配置字段
    merged.pop("status", None)
    merged.pop("tool_count", None)
    merged.pop("tools", None)
    merged.pop("error", None)

    try:
        config = McpServerConfig(**merged)
    except Exception as e:
        raise BadRequestError(f"Invalid config: {e}", code="MCP_CONFIG_INVALID")

    success, message = await mcp_manager.update_server(name, config)
    if not success:
        raise BadRequestError(message, code="MCP_OPERATION_FAILED")
    logger.info(f"[McpAPI] Updated server: {name}")
    return ServerActionResponse(success=success, message=message)


@router.delete("/servers/{name}", response_model=ServerActionResponse)
async def delete_server(name: str):
    """删除 MCP 服务器配置并断开连接。"""
    success, message = await mcp_manager.remove_server(name)
    if not success:
        raise NotFoundError(message, code="MCP_SERVER_NOT_FOUND")
    logger.info(f"[McpAPI] Deleted server: {name}")
    return ServerActionResponse(success=success, message=message)


@router.post("/servers/{name}/action", response_model=ServerActionResponse)
async def server_action(name: str, req: ServerActionRequest):
    """执行服务器操作：connect / disconnect / reconnect。"""
    if name not in {s["name"] for s in mcp_manager.list_servers()}:
        raise NotFoundError(f"Server '{name}' not found", code="MCP_SERVER_NOT_FOUND")

    try:
        if req.action == "connect":
            ok = await mcp_manager.connect(name)
            return ServerActionResponse(
                success=ok,
                message=f"Server '{name}' connected" if ok else f"Server '{name}' connection failed",
            )
        elif req.action == "disconnect":
            await mcp_manager.disconnect(name)
            return ServerActionResponse(success=True, message=f"Server '{name}' disconnected")
        elif req.action == "reconnect":
            ok = await mcp_manager.reconnect(name)
            return ServerActionResponse(
                success=ok,
                message=f"Server '{name}' reconnected" if ok else f"Server '{name}' reconnect failed",
            )
        else:
            raise BadRequestError(f"Unknown action: {req.action}")
    except ValueError as e:
        raise BadRequestError(str(e), code="MCP_OPERATION_FAILED")


@router.get("/tools", response_model=ToolListResponse)
async def list_all_tools():
    """列出所有已连接 MCP 服务器的工具（OpenAI function calling 格式）。"""
    tools = mcp_manager.get_all_tools_for_llm()
    return ToolListResponse(tools=tools, count=len(tools))


@router.get("/servers/{name}/resources")
async def list_resources(name: str):
    """列出指定服务器的资源。"""
    if name not in {s["name"] for s in mcp_manager.list_servers()}:
        raise NotFoundError(f"Server '{name}' not found", code="MCP_SERVER_NOT_FOUND")
    resources = await mcp_manager.list_resources(name)
    return ok({"resources": resources, "count": len(resources)})


@router.get("/servers/{name}/prompts")
async def list_prompts(name: str):
    """列出指定服务器的提示。"""
    if name not in {s["name"] for s in mcp_manager.list_servers()}:
        raise NotFoundError(f"Server '{name}' not found", code="MCP_SERVER_NOT_FOUND")
    prompts = await mcp_manager.list_prompts(name)
    return ok({"prompts": prompts, "count": len(prompts)})
