"""LuomiNest MCP 管理器。

管理多个 MCP 服务器的连接、配置持久化与工具调用。

核心能力：
- init：加载 mcp_servers.json 并自动连接 enabled + auto_connect 的服务器
- connect/disconnect/reconnect：单服务器连接管理（基于 AsyncExitStack）
- call_tool：调用指定服务器的工具（供 McpTool 使用）
- get_all_tools_for_llm：聚合所有已连接服务器的工具（OpenAI function calling 格式）

工具命名约定：`{server_name}__{tool_name}`（双下划线分隔，避免与工具名冲突）

设计原则：
1. 连接失败不抛异常，记录 error 并将状态置为 ERROR，不影响其他服务器
2. 配置持久化到 {DATA_DIR}/mcp_servers.json
3. 所有 API 返回 dict（而非模型对象），便于端点直接序列化
"""
import json
import os
from contextlib import AsyncExitStack
from typing import Any

from loguru import logger
from pydantic import ValidationError

from app.core.config import settings
from app.core.tools.mcp.models import McpServerConfig, McpServerStatus, McpTransportType

# ------------------------------------------------------------------
# MCP 子进程安全环境变量
# ------------------------------------------------------------------

# 安全环境变量白名单
_SAFE_ENV_VARS: set[str] = {
    "PATH", "HOME", "USERPROFILE", "SYSTEMROOT", "WINDIR",
    "TEMP", "TMP", "LANG", "LC_ALL",
    "PYTHONPATH", "VIRTUAL_ENV", "CONDA_PREFIX",
}

# 环境变量前缀白名单
_SAFE_ENV_PREFIX: tuple[str, ...] = ("XDG_", "LC_", "LANG_")

# 敏感关键字（包含这些关键字的环境变量始终被排除）
_SENSITIVE_KEYWORDS: tuple[str, ...] = (
    "KEY", "SECRET", "TOKEN", "PASSWORD", "CREDENTIAL",
)


def _build_safe_env(environ: dict[str, str] | None = None) -> dict[str, str]:
    """构建安全的子进程环境变量，排除 API Key 等敏感信息。"""
    if environ is None:
        environ = dict(os.environ)
    safe: dict[str, str] = {}
    for key, value in environ.items():
        upper_key = key.upper()
        if any(kw in upper_key for kw in _SENSITIVE_KEYWORDS):
            continue
        if key in _SAFE_ENV_VARS:
            safe[key] = value
        elif any(key.startswith(p) for p in _SAFE_ENV_PREFIX):
            safe[key] = value
    return safe


class _ServerConnection:
    """单个 MCP 服务器的连接状态（内部使用）"""

    def __init__(self, config: McpServerConfig) -> None:
        self.config = config
        self.status: McpServerStatus = McpServerStatus.DISCONNECTED
        self.session: Any = None  # mcp.ClientSession
        self.exit_stack: AsyncExitStack | None = None
        self.tools: list[dict[str, Any]] = []  # OpenAI function calling 格式
        self.error: str = ""


class McpManager:
    """MCP 管理器单例

    在 app_factory lifespan 中初始化：`await mcp_manager.init()`
    在应用关闭时清理：`await mcp_manager.disconnect_all()`
    """

    def __init__(self) -> None:
        self._servers: dict[str, _ServerConnection] = {}
        self._config_file = os.path.join(settings.DATA_DIR, "mcp_servers.json")
        self._initialized = False

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    async def init(self) -> None:
        """加载配置并自动连接 enabled + auto_connect 的服务器"""
        if self._initialized:
            logger.debug("[McpManager] 已初始化，跳过")
            return

        self._load_config()
        self._initialized = True

        auto_connect_names = [
            name for name, conn in self._servers.items()
            if conn.config.enabled and conn.config.auto_connect
        ]
        logger.info(
            f"[McpManager] 初始化完成：共 {len(self._servers)} 个服务器，"
            f"{len(auto_connect_names)} 个待自动连接"
        )

        for name in auto_connect_names:
            await self.connect(name)

    async def disconnect_all(self) -> None:
        """断开所有服务器连接"""
        names = list(self._servers.keys())
        for name in names:
            await self.disconnect(name)
        logger.info(f"[McpManager] 已断开所有连接（{len(names)} 个）")

    # ------------------------------------------------------------------
    # 配置持久化
    # ------------------------------------------------------------------

    def _load_config(self) -> None:
        """从 mcp_servers.json 加载配置"""
        if not os.path.exists(self._config_file):
            logger.debug(f"[McpManager] 配置文件不存在: {self._config_file}")
            return

        try:
            with open(self._config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.warning(f"[McpManager] 配置加载失败: {e}")
            return

        if not isinstance(data, list):
            logger.warning("[McpManager] 配置格式错误：期望列表")
            return

        for item in data:
            try:
                config = McpServerConfig(**item)
                self._servers[config.name] = _ServerConnection(config)
                logger.debug(f"[McpManager] 加载服务器配置: {config.name}")
            except ValidationError as e:
                logger.warning(f"[McpManager] 服务器配置无效，跳过: {e}")

    def _save_config(self) -> None:
        """保存配置到 mcp_servers.json"""
        os.makedirs(os.path.dirname(self._config_file), exist_ok=True)
        data = [conn.config.model_dump(mode="json") for conn in self._servers.values()]
        try:
            with open(self._config_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug(f"[McpManager] 配置已保存: {len(data)} 个服务器")
        except Exception as e:
            logger.error(f"[McpManager] 配置保存失败: {e}")

    # ------------------------------------------------------------------
    # 连接管理
    # ------------------------------------------------------------------

    async def connect(self, name: str) -> bool:
        """连接指定服务器

        Returns:
            True 表示连接成功，False 表示失败（错误信息记录在 conn.error）
        """
        conn = self._servers.get(name)
        if conn is None:
            logger.warning(f"[McpManager] 服务器不存在: {name}")
            return False

        # 先断开旧连接
        await self._close_connection(conn)

        conn.status = McpServerStatus.CONNECTING
        conn.error = ""

        try:
            stack = AsyncExitStack()
            read, write = await self._open_transport(conn.config, stack)

            # 延迟导入 mcp SDK，避免未安装时影响整个模块加载
            from mcp import ClientSession

            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()

            # 获取工具列表
            tools_result = await session.list_tools()
            conn.tools = [
                self._tool_to_openai_function(t, name)
                for t in tools_result.tools
            ]

            conn.session = session
            conn.exit_stack = stack
            conn.status = McpServerStatus.CONNECTED

            logger.info(
                f"[McpManager] 服务器已连接: {name}, "
                f"工具数={len(conn.tools)}"
            )
            return True

        except Exception as e:
            conn.status = McpServerStatus.ERROR
            conn.error = str(e)
            conn.session = None
            conn.tools = []
            # 清理已创建的 stack
            try:
                await stack.aclose()
            except Exception:
                # 主错误已在下方 warning 记录，此处为二次清理噪音
                logger.debug(f"[McpManager] 连接失败后清理 stack 异常（忽略）: {name}", exc_info=True)
            logger.warning(f"[McpManager] 服务器连接失败: {name}, error={e}")
            return False

    async def _open_transport(self, config: McpServerConfig, stack: AsyncExitStack):
        """根据传输方式打开连接，返回 (read, write) 流"""
        if config.transport == McpTransportType.STDIO:
            from mcp import StdioServerParameters
            from mcp.client.stdio import stdio_client

            if not config.command:
                raise ValueError("stdio 模式需要 command 参数")

            params_kwargs: dict[str, Any] = {
                "command": config.command,
                "args": config.args or [],
            }
            # 环境变量安全过滤：始终使用过滤后的环境变量，防止泄露 API Key 等敏感信息
            if config.env is not None:
                # 用户指定的 env 也需要过滤（防止通过配置注入敏感变量）
                params_kwargs["env"] = _build_safe_env(config.env)
            else:
                # 默认使用过滤后的当前进程环境变量
                params_kwargs["env"] = _build_safe_env()
            if config.cwd is not None:
                params_kwargs["cwd"] = config.cwd

            params = StdioServerParameters(**params_kwargs)
            return await stack.enter_async_context(stdio_client(params))

        elif config.transport == McpTransportType.SSE:
            from mcp.client.sse import sse_client

            if not config.url:
                raise ValueError("sse 模式需要 url 参数")
            return await stack.enter_async_context(
                sse_client(config.url, headers=config.headers)
            )

        else:
            raise ValueError(f"不支持的传输方式: {config.transport}")

    async def disconnect(self, name: str) -> None:
        """断开指定服务器连接"""
        conn = self._servers.get(name)
        if conn is None:
            return
        await self._close_connection(conn)
        logger.info(f"[McpManager] 服务器已断开: {name}")

    async def reconnect(self, name: str) -> bool:
        """重连指定服务器"""
        return await self.connect(name)

    async def _close_connection(self, conn: _ServerConnection) -> None:
        """关闭单个连接（内部使用）"""
        conn.session = None
        conn.tools = []
        if conn.exit_stack is not None:
            try:
                await conn.exit_stack.aclose()
            except Exception as e:
                logger.debug(f"[McpManager] 关闭连接异常: {e}")
            conn.exit_stack = None
        conn.status = McpServerStatus.DISCONNECTED

    # ------------------------------------------------------------------
    # 服务器增删改查
    # ------------------------------------------------------------------

    def list_servers(self) -> list[dict[str, Any]]:
        """列出所有服务器配置及状态"""
        return [self._conn_to_dict(conn) for conn in self._servers.values()]

    def get_server(self, name: str) -> dict[str, Any] | None:
        """获取单个服务器详情（含工具列表）"""
        conn = self._servers.get(name)
        if conn is None:
            return None
        return self._conn_to_dict(conn)

    async def add_server(self, config: McpServerConfig) -> tuple[bool, str]:
        """添加服务器配置

        Returns:
            (success, message)
        """
        if config.name in self._servers:
            return False, f"服务器已存在: {config.name}"

        self._servers[config.name] = _ServerConnection(config)
        self._save_config()

        if config.enabled and config.auto_connect:
            await self.connect(config.name)

        return True, f"服务器已添加: {config.name}"

    async def update_server(self, name: str, config: McpServerConfig) -> tuple[bool, str]:
        """更新服务器配置（会触发重连）"""
        conn = self._servers.get(name)
        if conn is None:
            return False, f"服务器不存在: {name}"

        # 如果名称变更，需要迁移
        if config.name != name:
            if config.name in self._servers:
                return False, f"目标名称已存在: {config.name}"
            await self._close_connection(conn)
            del self._servers[name]
            self._servers[config.name] = _ServerConnection(config)
        else:
            await self._close_connection(conn)
            conn.config = config

        self._save_config()

        if config.enabled and config.auto_connect:
            await self.connect(config.name)

        return True, f"服务器已更新: {config.name}"

    async def remove_server(self, name: str) -> tuple[bool, str]:
        """删除服务器配置并断开连接"""
        conn = self._servers.get(name)
        if conn is None:
            return False, f"服务器不存在: {name}"

        await self._close_connection(conn)
        del self._servers[name]
        self._save_config()

        return True, f"服务器已删除: {name}"

    # ------------------------------------------------------------------
    # 工具调用与查询
    # ------------------------------------------------------------------

    def get_all_tools_for_llm(self) -> list[dict[str, Any]]:
        """获取所有已连接服务器的工具（OpenAI function calling 格式）

        工具名格式：`{server_name}__{tool_name}`
        """
        all_tools: list[dict[str, Any]] = []
        for conn in self._servers.values():
            if conn.status == McpServerStatus.CONNECTED:
                all_tools.extend(conn.tools)
        return all_tools

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        params: dict[str, Any],
    ) -> str:
        """调用指定服务器的工具

        Args:
            server_name: 服务器名称
            tool_name: 工具名称（不含 server_name 前缀）
            params: 工具参数

        Returns:
            工具执行结果文本
        """
        conn = self._servers.get(server_name)
        if conn is None:
            return f"[MCP 错误] 服务器不存在: {server_name}"
        if conn.status != McpServerStatus.CONNECTED or conn.session is None:
            return f"[MCP 错误] 服务器未连接: {server_name} (状态={conn.status.value})"

        try:
            result = await conn.session.call_tool(tool_name, params)
            # CallToolResult.content 是 ContentItem 列表
            texts: list[str] = []
            for item in result.content:
                if hasattr(item, "text"):
                    texts.append(item.text)
                else:
                    texts.append(str(item))
            return "\n".join(texts) if texts else "(MCP 工具未返回内容)"
        except Exception as e:
            logger.error(
                f"[McpManager] 工具调用失败: server={server_name}, "
                f"tool={tool_name}, error={e}"
            )
            return f"[MCP 工具调用失败] {e}"

    async def list_resources(self, name: str) -> list[dict[str, Any]]:
        """列出指定服务器的资源"""
        conn = self._servers.get(name)
        if conn is None or conn.session is None:
            return []
        try:
            result = await conn.session.list_resources()
            return [r.model_dump() if hasattr(r, "model_dump") else dict(r) for r in result.resources]
        except Exception as e:
            logger.warning(f"[McpManager] 列出资源失败: {name}, error={e}")
            return []

    async def list_prompts(self, name: str) -> list[dict[str, Any]]:
        """列出指定服务器的提示"""
        conn = self._servers.get(name)
        if conn is None or conn.session is None:
            return []
        try:
            result = await conn.session.list_prompts()
            return [p.model_dump() if hasattr(p, "model_dump") else dict(p) for p in result.prompts]
        except Exception as e:
            logger.warning(f"[McpManager] 列出提示失败: {name}, error={e}")
            return []

    # ------------------------------------------------------------------
    # 工具名解析（供 McpTool 使用）
    # ------------------------------------------------------------------

    def parse_tool_name(self, full_name: str) -> tuple[str, str] | None:
        """解析 `server__tool` 格式的工具名

        Returns:
            (server_name, tool_name) 或 None（格式无效）
        """
        parts = full_name.split("__", 1)
        if len(parts) != 2:
            return None
        return parts[0], parts[1]

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    def _conn_to_dict(self, conn: _ServerConnection) -> dict[str, Any]:
        """将连接状态转换为 API 可返回的 dict"""
        data = conn.config.to_public_dict()
        data["status"] = conn.status.value
        data["tool_count"] = len(conn.tools)
        data["tools"] = [t.get("function", {}).get("name", "") for t in conn.tools]
        data["error"] = conn.error
        return data

    @staticmethod
    def _tool_to_openai_function(tool: Any, server_name: str) -> dict[str, Any]:
        """将 MCP Tool 转换为 OpenAI function calling 格式

        工具名加 `{server_name}__` 前缀，避免跨服务器命名冲突
        """
        original_name = getattr(tool, "name", "unknown")
        prefixed_name = f"{server_name}__{original_name}"
        description = getattr(tool, "description", "") or ""
        input_schema = getattr(tool, "inputSchema", None) or {
            "type": "object",
            "properties": {},
        }

        return {
            "type": "function",
            "function": {
                "name": prefixed_name,
                "description": f"[MCP:{server_name}] {description}",
                "parameters": input_schema,
            },
        }


# 全局单例
mcp_manager = McpManager()
