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
import re
from abc import ABC, abstractmethod
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

# 拉丁词（≥2 字符）与 CJK 串的检索正则（S1b 轻量匹配共用）
_LATIN_RE = re.compile(r"[a-z0-9_]{2,}")
_CJK_RUN_RE = re.compile(r"[\u4e00-\u9fff]{2,}")
_CJK_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")


def score_tool_match(query: str, name: str, description: str) -> int:
    """轻量相关性评分（S1b 服务端检索共用）。

    拉丁词命中 name +3 / description +1；CJK 连续串命中 name +4 / description +2；
    单个汉字命中 description +1。无新引擎依赖，嵌入检索为远期增强（替换本函数即可）。
    """
    q = (query or "").strip().lower()
    if not q:
        return 0
    name_l = name.lower()
    desc_l = description.lower()
    score = 0
    for term in _LATIN_RE.findall(q):
        if term in name_l:
            score += 3
        elif term in desc_l:
            score += 1
    for run in _CJK_RUN_RE.findall(q):
        if run in name_l:
            score += 4
        if run in desc_l:
            score += 2
    for ch in _CJK_CHAR_RE.findall(q):
        if ch in desc_l:
            score += 1
    return score


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

    声明式属性（子类可覆盖，用于工具分层与过滤，对齐 DBS tool_calls.tool_type）：
        - tier: 工具层级，core（常驻）/ domain（领域）/ meta（发现式）
        - scope: 场景归属，shared（共享，默认）/ platform（平台专用，仅平台域注入）
        - platform: 运行平台集合，win/mac/linux 的组合（默认全平台）
    """

    # 工具层级（落 DBS tool_calls.tool_type）
    tier: str = "domain"
    # 场景归属（shared / platform / platform:{instId}）
    scope: str = "shared"
    # 运行平台集合
    platform: frozenset[str] = frozenset({"win", "mac", "linux"})

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

    def to_tool_info_dict(self) -> dict[str, Any]:
        """转换为工具信息字典（含 tier/scope/platform 声明字段，供 /api/tools 端点与前端面板使用）。"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "tier": self.tier,
            "scope": self.scope,
            "platform": sorted(self.platform),
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

    def search(self, query: str, top_k: int = 8) -> list[ToolBase]:
        """按语义关键词检索工具（S1b L2 服务端检索，对齐 tool-opt §4.2.1）。

        轻量实现：对 name/description 做加权匹配（见 score_tool_match），
        不引入向量引擎（嵌入检索为远期增强，接口保持不变可直接替换内部实现）。
        meta tier 工具常驻注入，不参与召回。

        Args:
            query: 检索query（通常为用户当前消息）
            top_k: 最多返回的工具数

        Returns:
            按相关性降序的工具实例列表（score<=0 的不返回）
        """
        if not (query or "").strip():
            return []
        scored: list[tuple[int, str, ToolBase]] = []
        for tool in self._tools.values():
            if tool.tier == "meta":
                continue
            score = score_tool_match(query, tool.name, tool.description)
            if score > 0:
                scored.append((score, tool.name, tool))
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [t for _, _, t in scored[:top_k]]

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
