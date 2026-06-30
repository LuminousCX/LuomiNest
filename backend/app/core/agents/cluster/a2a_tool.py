"""LuomiNest A2A 协议跨服务调用工具。

参考 综合调查.md §5.2 与 python-a2a 库设计：
通过 A2A（Agent-to-Agent）协议调用远程服务器上的 Agent，
适用于跨服务、跨实例的 Agent 协作场景。

核心机制：
1. 基于 python-a2a 库的 A2AClient，调用远程 A2A 服务端点
2. 每个 A2A 服务器对应一个独立工具实例（工具名 a2a_tool_call_{server_name}）
3. 超时控制（settings.A2A_TIMEOUT_SECONDS）
4. 自动适配 ask 方法的 sync/async 形态

品牌化命名：LuomiNestA2ACallTool / get_luominest_a2a_tools。
"""
import asyncio
import inspect
from typing import Any

from loguru import logger

from app.core.config import settings
from app.core.tools.registry import ToolBase, ToolResult


def _sanitize_luominest_server_name(name: str) -> str:
    """将服务器名称清理为合法的工具名后缀（仅字母数字下划线）"""
    return "".join(c if c.isalnum() or c == "_" else "_" for c in name)


class LuomiNestA2ACallTool(ToolBase):
    """A2A 协议跨服务 Agent 调用工具

    每个 A2A 远程服务器对应一个工具实例。
    主 Agent 通过本工具调用远程 Agent 协助完成任务。
    """

    def __init__(self, server_name: str, server_url: str, api_key: str = ""):
        self._server_name = server_name
        self._server_url = server_url
        self._api_key = api_key

    @property
    def name(self) -> str:
        return f"a2a_tool_call_{_sanitize_luominest_server_name(self._server_name)}"

    @property
    def description(self) -> str:
        return (
            f"通过 A2A 协议调用远程 Agent 服务器「{self._server_name}」协助完成任务。"
            "适用于跨服务、跨实例的 Agent 协作。"
            "远程 Agent 拥有独立上下文，执行完成后返回结果。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "调用远程 Agent 的查询/任务描述（必填，应清晰具体）",
                },
            },
            "required": ["query"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        query = arguments.get("query", "").strip()
        if not query:
            return ToolResult.fail("缺少 query 参数")

        try:
            from python_a2a import A2AClient
        except ImportError:
            return ToolResult.fail(
                "python-a2a 库未安装，无法进行 A2A 调用。请联系管理员安装依赖。"
            )

        timeout_seconds = settings.A2A_TIMEOUT_SECONDS
        logger.info(
            f"[A2AToolCall] 调用远程 Agent: server={self._server_name}, "
            f"url={self._server_url}, query_len={len(query)}, "
            f"timeout={timeout_seconds}s"
        )

        try:
            client = A2AClient(self._server_url)

            # 适配 ask 方法的 sync/async 形态
            if inspect.iscoroutinefunction(client.ask):
                result = await asyncio.wait_for(
                    client.ask(query), timeout=timeout_seconds,
                )
            else:
                result = await asyncio.wait_for(
                    asyncio.to_thread(client.ask, query), timeout=timeout_seconds,
                )

            # 提取结果文本（兼容字符串/对象/dict）
            if hasattr(result, "content"):
                result_text = str(result.content)
            elif isinstance(result, dict):
                result_text = result.get("content") or result.get("text") or str(result)
            elif isinstance(result, str):
                result_text = result
            else:
                result_text = str(result)

            if not result_text or result_text.strip() in ("None", ""):
                return ToolResult.fail("远程 Agent 未返回有效内容")

            logger.info(
                f"[A2AToolCall] 远程 Agent 调用完成: server={self._server_name}, "
                f"result_len={len(result_text)}"
            )
            return ToolResult.ok(
                result_text,
                metadata={
                    "server_name": self._server_name,
                    "server_url": self._server_url,
                    "result_len": len(result_text),
                },
            )

        except asyncio.TimeoutError:
            timeout_msg = (
                f"调用远程 Agent 超时（{timeout_seconds}秒），"
                f"服务器「{self._server_name}」可能不可用或响应过慢"
            )
            logger.error(f"[A2AToolCall] 超时: server={self._server_name}")
            return ToolResult.fail(timeout_msg)
        except ConnectionError as e:
            connect_msg = f"无法连接到远程 Agent 服务器「{self._server_name}」：{e}"
            logger.error(f"[A2AToolCall] 连接失败: server={self._server_name}, error={e}")
            return ToolResult.fail(connect_msg)
        except Exception as e:
            logger.error(
                f"[A2AToolCall] 异常: server={self._server_name}, error={e}",
                exc_info=True,
            )
            return ToolResult.fail(f"调用远程 Agent 失败：{e}")


def get_luominest_a2a_tools() -> list[LuomiNestA2ACallTool]:
    """根据 settings.A2A_SERVERS 配置生成 A2A 工具列表

    仅返回 enabled=true 的服务器对应的工具实例。
    在 app_factory lifespan 中调用，将工具注册到 tool_registry。
    """
    tools: list[LuomiNestA2ACallTool] = []
    servers = settings.A2A_SERVERS or []
    for server in servers:
        if not isinstance(server, dict):
            continue
        if not server.get("enabled", False):
            continue
        name = server.get("name", "").strip()
        url = server.get("url", "").strip()
        if not name or not url:
            logger.warning(f"[A2A] 跳过配置不完整的服务器: {server}")
            continue
        api_key = server.get("api_key", "")
        tools.append(LuomiNestA2ACallTool(name, url, api_key))
        logger.info(f"[A2A] 注册工具: a2a_tool_call_{_sanitize_luominest_server_name(name)} -> {url}")
    return tools
