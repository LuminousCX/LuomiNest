"""LuomiNest 工具注册表。

定义工具系统的核心数据模型与注册表：
- ToolResult：工具执行结果（与 /api/v1/tools 端点的 ToolCallResponse 字段对齐）
- ToolBase：工具抽象基类，所有内置工具与 MCP 工具均继承此类
- ToolRegistry：工具注册表单例，提供 register/list/execute 能力

设计原则：
1. 所有工具统一使用 `arguments: dict[str, Any]` 签名，便于 LLM function calling 直传
2. 工具执行返回 ToolResult，含 success/output/error/metadata 四字段
3. 注册表仅负责登记与查找，不负责工具的实例化时机（由 app_factory 在 lifespan 中注册）
"""
from abc import ABC, abstractmethod
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    """工具执行结果。

    Attributes:
        success: 是否执行成功
        output: 工具输出内容（文本形式，将作为 LLM 上下文）
        error: 失败时的错误信息（success=True 时为空字符串）
        metadata: 额外元数据（如执行耗时、工具内部状态等，不进入 LLM 上下文）
    """
    success: bool = True
    output: str = ""
    error: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def ok(cls, output: str, metadata: dict[str, Any] | None = None) -> "ToolResult":
        """构造成功结果"""
        return cls(success=True, output=output, error="", metadata=metadata or {})

    @classmethod
    def fail(cls, error: str, metadata: dict[str, Any] | None = None) -> "ToolResult":
        """构造失败结果"""
        return cls(success=False, output="", error=error, metadata=metadata or {})


class ToolBase(ABC):
    """工具抽象基类。

    子类必须实现：
        - name: 工具唯一标识（用于 LLM function calling 的 function name）
        - description: 工具描述（LLM 据此判断是否调用该工具）
        - parameters: OpenAI JSON Schema 格式的参数定义
        - execute: 异步执行方法，接收 arguments 字典，返回 ToolResult
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称（唯一键）"""

    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述（供 LLM 理解工具用途）"""

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """参数 schema（OpenAI function calling 格式）"""

    @abstractmethod
    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        """执行工具

        Args:
            arguments: LLM 传入的参数字典

        Returns:
            ToolResult 执行结果
        """

    def to_openai_function(self) -> dict[str, Any]:
        """转换为 OpenAI function calling 格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    """工具注册表。

    负责工具的登记、查询与执行。全局单例 `tool_registry` 在 app_factory lifespan 中填充。
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolBase] = {}

    def register(self, tool: ToolBase) -> None:
        """注册工具。同名工具将被覆盖并记录警告"""
        if tool.name in self._tools:
            logger.warning(f"[ToolRegistry] 工具已存在，覆盖注册: {tool.name}")
        self._tools[tool.name] = tool
        logger.debug(f"[ToolRegistry] 注册工具: {tool.name}")

    def unregister(self, name: str) -> bool:
        """注销工具"""
        if name in self._tools:
            del self._tools[name]
            logger.debug(f"[ToolRegistry] 注销工具: {name}")
            return True
        return False

    def get(self, name: str) -> ToolBase | None:
        """按名称获取工具"""
        return self._tools.get(name)

    def list_tools(self) -> list[ToolBase]:
        """列出所有已注册工具"""
        return list(self._tools.values())

    def list_names(self) -> list[str]:
        """列出所有已注册工具名称"""
        return list(self._tools.keys())

    async def execute(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        """按名称执行工具

        Args:
            name: 工具名称
            arguments: 工具参数

        Returns:
            ToolResult。工具不存在或执行异常时返回失败结果
        """
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult.fail(f"工具不存在: {name}")

        try:
            result = await tool.execute(arguments)
            if not isinstance(result, ToolResult):
                # 兼容子类直接返回字符串的情况
                return ToolResult.ok(str(result))
            return result
        except Exception as e:
            logger.error(
                f"[ToolRegistry] 工具执行异常: name={name}, error={e}",
                exc_info=True,
            )
            return ToolResult.fail(f"工具执行异常: {e}")


# 全局单例
tool_registry = ToolRegistry()
