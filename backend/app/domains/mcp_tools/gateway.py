from loguru import logger
from app.infrastructure.database.json_store import mcp_servers_store


class MCPGateway:
    @staticmethod
    def list_servers() -> list[dict]:
        return mcp_servers_store.values()

    @staticmethod
    def get_server(name: str) -> dict | None:
        return mcp_servers_store.get(name)

    @staticmethod
    def add_server(name: str, config: dict):
        mcp_servers_store.set(name, config)
        logger.info(f"[MCPGateway] Added server: {name}")

    @staticmethod
    def remove_server(name: str):
        mcp_servers_store.delete(name)
        logger.info(f"[MCPGateway] Removed server: {name}")

    @staticmethod
    async def list_tools(server_name: str) -> list[dict]:
        server_config = mcp_servers_store.get(server_name)
        if not server_config:
            return []

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
                    tools_result = await session.list_tools()
                    return [
                        {
                            "name": t.name,
                            "description": t.description or "",
                            "parameters": t.inputSchema if hasattr(t, "inputSchema") else {},
                        }
                        for t in tools_result.tools
                    ]
        except ImportError:
            logger.warning("[MCPGateway] mcp package not installed")
            return []
        except Exception as e:
            logger.error(f"[MCPGateway] Failed to list tools for {server_name}: {e}")
            return []
