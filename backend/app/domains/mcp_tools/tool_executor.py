from loguru import logger
from app.infrastructure.database.json_store import mcp_servers_store


class MCPToolExecutor:
    async def execute(self, server_name: str, tool_name: str, arguments: dict) -> str:
        logger.info(f"[MCP] Executing tool: {tool_name} on server: {server_name}")

        server_config = mcp_servers_store.get(server_name)
        if not server_config:
            return f"MCP server '{server_name}' not found. Please configure it in settings."

        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client

            server_params = StdioServerParameters(
                command=server_config.get("command", ""),
                args=server_config.get("args", []),
                env=server_config.get("env"),
            )

            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments)
                    return str(result)
        except ImportError:
            logger.warning("[MCP] mcp package not installed, using mock response")
            return f"[MCP Mock] Tool '{tool_name}' called on server '{server_name}' with args: {arguments}. Install 'mcp' package for real MCP support."
        except Exception as e:
            logger.error(f"[MCP] Tool execution failed: {e}")
            return f"MCP tool execution error: {e}"

    @staticmethod
    def list_servers() -> list[dict]:
        return mcp_servers_store.values()

    @staticmethod
    def add_server(name: str, config: dict):
        mcp_servers_store.set(name, config)
        logger.info(f"[MCP] Added server: {name}")

    @staticmethod
    def remove_server(name: str):
        mcp_servers_store.delete(name)
        logger.info(f"[MCP] Removed server: {name}")
