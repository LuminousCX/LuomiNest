"""工具管理 API。

提供工具列表查询和手动调用工具的能力。
"""
from typing import Any

from fastapi import APIRouter
from loguru import logger
from pydantic import BaseModel

from app.core.tools import tool_registry
from app.core.tools.orchestrator import tool_orchestrator

router = APIRouter(prefix="/tools", tags=["tools"])


class ToolInfo(BaseModel):
    """工具信息"""
    name: str
    description: str
    parameters: dict[str, Any]


class ToolCallRequest(BaseModel):
    """工具调用请求"""
    name: str
    arguments: dict[str, Any] = {}


class ToolCallResponse(BaseModel):
    """工具调用响应"""
    success: bool
    output: str = ""
    error: str = ""
    metadata: dict[str, Any] = {}


@router.get("", response_model=list[ToolInfo])
async def list_tools():
    """列出所有已注册的工具"""
    tools = tool_registry.list_tools()
    return [
        ToolInfo(
            name=t.name,
            description=t.description,
            parameters=t.parameters,
        )
        for t in tools
    ]


@router.get("/openai-format")
async def list_tools_openai_format():
    """以 OpenAI function calling 格式列出工具（供调试用）"""
    return tool_orchestrator.get_tools_for_llm()


@router.post("/call", response_model=ToolCallResponse)
async def call_tool(req: ToolCallRequest):
    """手动调用指定工具"""
    logger.info(f"[ToolsAPI] Manual call: {req.name} with args: {req.arguments}")
    result = await tool_registry.execute(req.name, req.arguments)
    return ToolCallResponse(
        success=result.success,
        output=result.output,
        error=result.error,
        metadata=result.metadata,
    )
