from fastapi import APIRouter
from pydantic import BaseModel, Field
from loguru import logger

from app.domains.mcp_tools.gateway import MCPGateway
from app.domains.mcp_tools.tool_executor import MCPToolExecutor
from app.infrastructure.database.json_store import mcp_servers_store

router = APIRouter(prefix="/mcp", tags=["mcp"])


class MCPServerCreate(BaseModel):
    name: str
    command: str = ""
    args: list[str] = Field(default_factory=list)
    env: dict | None = None
    transport: str = "stdio"
    url: str | None = None
    description: str = ""


class MCPServerUpdate(BaseModel):
    command: str | None = None
    args: list[str] | None = None
    env: dict | None = None
    transport: str | None = None
    url: str | None = None
    description: str | None = None
    is_active: bool | None = None


class MCPToolCallRequest(BaseModel):
    tool_name: str
    arguments: dict = Field(default_factory=dict)


@router.get("/servers")
async def list_mcp_servers():
    logger.info("[API] GET /mcp/servers - Listing MCP servers")
    servers = MCPGateway.list_servers()
    return {"error": None, "data": servers}


@router.post("/servers")
async def add_mcp_server(request: MCPServerCreate):
    logger.info(f"[API] POST /mcp/servers - Adding MCP server: {request.name}")
    config = {
        "name": request.name,
        "command": request.command,
        "args": request.args,
        "env": request.env,
        "transport": request.transport,
        "url": request.url,
        "description": request.description,
        "is_active": True,
    }
    MCPGateway.add_server(request.name, config)
    return {"error": None, "data": config}


@router.patch("/servers/{server_name}")
async def update_mcp_server(server_name: str, request: MCPServerUpdate):
    logger.info(f"[API] PATCH /mcp/servers/{server_name} - Updating MCP server")
    server = mcp_servers_store.get(server_name)
    if not server:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"MCP server '{server_name}' not found")

    update_data = request.model_dump(exclude_unset=True)
    server.update(update_data)
    mcp_servers_store.set(server_name, server)
    return {"error": None, "data": server}


@router.delete("/servers/{server_name}")
async def remove_mcp_server(server_name: str):
    logger.info(f"[API] DELETE /mcp/servers/{server_name} - Removing MCP server")
    MCPGateway.remove_server(server_name)
    return {"error": None, "data": {"deleted": True}}


@router.get("/servers/{server_name}/tools")
async def list_mcp_tools(server_name: str):
    logger.info(f"[API] GET /mcp/servers/{server_name}/tools - Listing tools")
    tools = await MCPGateway.list_tools(server_name)
    return {"error": None, "data": tools}


@router.post("/servers/{server_name}/call")
async def call_mcp_tool(server_name: str, request: MCPToolCallRequest):
    logger.info(f"[API] POST /mcp/servers/{server_name}/call - Calling tool: {request.tool_name}")
    executor = MCPToolExecutor()
    result = await executor.execute(server_name, request.tool_name, request.arguments)
    return {"error": None, "data": {"result": result}}
