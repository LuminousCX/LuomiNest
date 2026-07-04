"""内部模块接口注册表

管理工作流引擎可调度的内部模块接口（浏览器、计划、记忆等）。
与 ToolRegistry 不同，这里注册的是高层模块操作，供工作流引擎直接调用。

参考：
- hermes-agent: ToolRegistry 单例 + 自注册模式
- deer-flow: MCP 工具加载 + 缓存机制
"""
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from loguru import logger

from app.core.workflow.models import WorkflowTaskResult


# 内部工具执行器类型：接收参数字典，返回 WorkflowTaskResult
InternalToolHandler = Callable[[dict[str, Any]], Awaitable[WorkflowTaskResult]]


@dataclass
class InternalToolEntry:
    """内部模块接口注册项"""
    name: str
    module: str
    description: str
    handler: InternalToolHandler
    parameters_schema: dict[str, Any] = field(default_factory=dict)
    is_concurrent_safe: bool = False
    timeout_seconds: int = 60
    registered_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "module": self.module,
            "description": self.description,
            "parameters": self.parameters_schema,
            "is_concurrent_safe": self.is_concurrent_safe,
            "timeout_seconds": self.timeout_seconds,
        }


class InternalToolRegistry:
    """内部模块接口注册表

    管理工作流引擎可调度的内部模块操作。
    每个接口通过 name 唯一标识，按 module 分类组织。

    与 ToolRegistry 的区别：
    - ToolRegistry 管理 LLM function calling 工具（面向 LLM）
    - InternalToolRegistry 管理工作流内部模块操作（面向工作流引擎）
    """

    def __init__(self):
        self._tools: dict[str, InternalToolEntry] = {}
        self._lock = asyncio.Lock()

    async def register(
        self,
        name: str,
        module: str,
        description: str,
        handler: InternalToolHandler,
        parameters_schema: dict[str, Any] | None = None,
        is_concurrent_safe: bool = False,
        timeout_seconds: int = 60,
    ) -> bool:
        """注册内部模块接口

        Args:
            name: 接口唯一名称（如 "browser.navigate"）
            module: 所属模块（如 "browser", "schedule", "memory"）
            description: 接口描述
            handler: 异步执行器函数
            parameters_schema: 参数 schema（JSON Schema 格式）
            is_concurrent_safe: 是否可以并发执行
            timeout_seconds: 执行超时时间

        Returns:
            bool: 是否注册成功
        """
        if not name:
            logger.warning("[InternalToolRegistry] Tool name is empty, skipped")
            return False

        entry = InternalToolEntry(
            name=name,
            module=module,
            description=description,
            handler=handler,
            parameters_schema=parameters_schema or {"type": "object", "properties": {}},
            is_concurrent_safe=is_concurrent_safe,
            timeout_seconds=timeout_seconds,
        )

        async with self._lock:
            if name in self._tools:
                logger.debug(f"[InternalToolRegistry] Overwriting existing tool: {name}")
            self._tools[name] = entry
            logger.info(f"[InternalToolRegistry] Registered: {name} (module={module})")
        return True

    async def unregister(self, name: str) -> bool:
        """注销内部模块接口"""
        async with self._lock:
            if name in self._tools:
                del self._tools[name]
                logger.info(f"[InternalToolRegistry] Unregistered: {name}")
                return True
            return False

    def get(self, name: str) -> InternalToolEntry | None:
        """获取接口注册项"""
        return self._tools.get(name)

    def list_tools(self) -> list[InternalToolEntry]:
        """列出所有已注册的接口"""
        return list(self._tools.values())

    def list_by_module(self, module: str) -> list[InternalToolEntry]:
        """按模块列出接口"""
        return [t for t in self._tools.values() if t.module == module]

    def list_modules(self) -> list[str]:
        """列出所有已注册的模块"""
        return sorted({t.module for t in self._tools.values()})

    def list_names(self) -> list[str]:
        """列出所有接口名称"""
        return list(self._tools.keys())

    async def execute(self, name: str, arguments: dict[str, Any]) -> WorkflowTaskResult:
        """执行指定接口

        Args:
            name: 接口名称
            arguments: 调用参数

        Returns:
            WorkflowTaskResult: 执行结果
        """
        entry = self._tools.get(name)
        if entry is None:
            available = ", ".join(self._tools.keys()) or "none"
            return WorkflowTaskResult(
                success=False,
                error=f"Internal tool '{name}' not found. Available: {available}",
            )

        try:
            result = await asyncio.wait_for(
                entry.handler(arguments),
                timeout=entry.timeout_seconds,
            )
            return result
        except asyncio.TimeoutError:
            logger.error(
                f"[InternalToolRegistry] Tool '{name}' timed out "
                f"after {entry.timeout_seconds}s"
            )
            return WorkflowTaskResult(
                success=False,
                error=f"Tool '{name}' timed out after {entry.timeout_seconds}s",
            )
        except Exception as e:
            logger.error(
                f"[InternalToolRegistry] Tool '{name}' execution failed: {e}",
                exc_info=True,
            )
            return WorkflowTaskResult(
                success=False,
                error=f"Tool execution failed: {e}",
            )

    def to_openai_schemas(self) -> list[dict[str, Any]]:
        """转换为 OpenAI function calling 格式列表

        供 LLM 在规划阶段了解可用的工作流内部接口。
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": entry.name,
                    "description": entry.description,
                    "parameters": entry.parameters_schema,
                },
            }
            for entry in self._tools.values()
        ]

    def get_module_summary(self) -> list[dict[str, Any]]:
        """获取模块摘要，供 LLM 规划时参考"""
        modules: dict[str, dict[str, Any]] = {}
        for entry in self._tools.values():
            if entry.module not in modules:
                modules[entry.module] = {
                    "module": entry.module,
                    "tools": [],
                }
            modules[entry.module]["tools"].append({
                "name": entry.name,
                "description": entry.description,
            })
        return list(modules.values())

    def get_filtered_module_summary(
        self, exclude_tools: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        """获取过滤后的模块摘要，按模式裁剪工具列表。

        Args:
            exclude_tools: 需排除的工具名集合（如 STANDARD 模式排除 27 个 browser_action 工具）

        Returns:
            过滤后的模块摘要列表
        """
        exclude_set = exclude_tools or set()
        modules: dict[str, dict[str, Any]] = {}
        for entry in self._tools.values():
            if entry.name in exclude_set:
                continue
            if entry.module not in modules:
                modules[entry.module] = {
                    "module": entry.module,
                    "tools": [],
                }
            modules[entry.module]["tools"].append({
                "name": entry.name,
                "description": entry.description,
                "parameters": entry.parameters_schema,
            })
        return list(modules.values())


# 全局单例
internal_tool_registry = InternalToolRegistry()
