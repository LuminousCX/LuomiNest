"""MCP 服务器管理 API。

提供 MCP 服务器的增删改查、连接管理、工具列表查询等接口，
以及 P0-3 对外 MCP 服务器的 Bearer token 查看/重置。
"""
from typing import Any

from fastapi import APIRouter
from loguru import logger
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.exceptions import BadRequestError, NotFoundError

from app.core.tools.mcp.manager import mcp_manager
from app.core.tools.mcp.models import McpServerConfig, McpTransportType
from app.core.utils import ok

router = APIRouter(prefix="/mcp", tags=["mcp"])


# ------------------------------------------------------------------
# 请求模型
# ------------------------------------------------------------------

class CreateServerRequest(BaseModel):
    """创建 MCP 服务器请求。"""
    name: str = Field(..., description="服务器唯一名称")
    transport: McpTransportType = Field(..., description="传输方式：stdio / sse / streamable_http")
    command: str | None = Field(None, description="stdio: 可执行命令")
    args: list[str] = Field(default_factory=list, description="stdio: 命令参数")
    env: dict[str, str] | None = Field(None, description="stdio: 环境变量")
    cwd: str | None = Field(None, description="stdio: 工作目录")
    url: str | None = Field(None, description="sse / streamable_http: 服务器 URL")
    headers: dict[str, str] | None = Field(None, description="sse / streamable_http: 请求头")
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


class TokenResponse(BaseModel):
    """对外 MCP 服务器访问 token（P0-3）。"""
    success: bool = True
    token: str
    auth_enabled: bool


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


# ------------------------------------------------------------------
# 对外 MCP 服务器访问 token（P0-3 传输安全）
# ------------------------------------------------------------------
# 本端点挂在 /api 下，受 luomi_auth_middleware 正常鉴权；
# 返回的 token 供用户在 mcp-remote --header 中使用，日志不落明文。

@router.get("/token", response_model=TokenResponse)
async def get_mcp_access_token():
    """查看对外 MCP 服务器的 Bearer token（首次访问自动生成并持久化）。"""
    # 延迟导入避免模块加载期触碰 DB
    from app.core.mcp_server.auth import get_mcp_token

    token = get_mcp_token(create=True)
    if not token:
        raise BadRequestError("MCP token 生成失败，请检查数据库", code="MCP_TOKEN_UNAVAILABLE")
    return TokenResponse(token=token, auth_enabled=bool(settings.MCP_SERVER_AUTH))


@router.post("/token/reset", response_model=TokenResponse)
async def reset_mcp_access_token():
    """重置对外 MCP 服务器的 Bearer token（旧 token 即刻失效）。"""
    from app.core.mcp_server.auth import reset_mcp_token as do_reset

    token = do_reset()
    logger.info("[McpAPI] MCP access token reset via API")  # 只记事件，不落 token 明文
    return TokenResponse(token=token, auth_enabled=bool(settings.MCP_SERVER_AUTH))
