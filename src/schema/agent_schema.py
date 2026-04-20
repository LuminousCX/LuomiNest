"""Agent 人格相关请求/响应参数校验模型。

定义 API 层的数据传输对象（DTO）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from src.model.agent import AgentStatus, AgentType, ResponseConfig


class AgentCreateRequest(BaseModel):
    """创建 Agent 人格请求。"""

    name: str = Field(..., min_length=1, max_length=50, description="人格名称")
    avatar: Optional[str] = Field(default=None, max_length=500, description="头像URL")
    title: str = Field(default="", max_length=200, description="一句话介绍")
    background: str = Field(default="", max_length=5000, description="经历背景")
    personality: str = Field(default="", max_length=2000, description="性格特点")
    speaking_style: str = Field(default="", max_length=2000, description="说话风格")
    constraints: str = Field(default="", max_length=3000, description="行为约束")
    prompt_template: Optional[str] = Field(default=None, max_length=10000, description="自定义prompt模板")
    response_config: ResponseConfig = Field(
        default_factory=ResponseConfig, description="响应配置"
    )


class AgentUpdateRequest(BaseModel):
    """更新 Agent 人格请求。"""

    name: Optional[str] = Field(default=None, min_length=1, max_length=50, description="人格名称")
    avatar: Optional[str] = Field(default=None, max_length=500, description="头像URL")
    title: Optional[str] = Field(default=None, max_length=200, description="一句话介绍")
    background: Optional[str] = Field(default=None, max_length=5000, description="经历背景")
    personality: Optional[str] = Field(default=None, max_length=2000, description="性格特点")
    speaking_style: Optional[str] = Field(default=None, max_length=2000, description="说话风格")
    constraints: Optional[str] = Field(default=None, max_length=3000, description="行为约束")
    prompt_template: Optional[str] = Field(default=None, max_length=10000, description="自定义prompt模板")
    response_config: Optional[ResponseConfig] = Field(default=None, description="响应配置")
    status: Optional[AgentStatus] = Field(default=None, description="状态")


class AgentResponse(BaseModel):
    """Agent 人格响应。"""

    id: int = Field(description="主键ID")
    name: str = Field(description="人格名称")
    avatar: Optional[str] = Field(default=None, description="头像URL")
    title: str = Field(default="", description="一句话介绍")
    background: str = Field(default="", description="经历背景")
    personality: str = Field(default="", description="性格特点")
    speaking_style: str = Field(default="", description="说话风格")
    constraints: str = Field(default="", description="行为约束")
    prompt_template: Optional[str] = Field(default=None, description="自定义prompt模板")
    response_config: ResponseConfig = Field(description="响应配置")
    agent_type: AgentType = Field(description="人格类型")
    status: AgentStatus = Field(description="状态")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")

    @classmethod
    def from_entity(cls, entity) -> AgentResponse:
        """从 AgentEntity 创建响应。"""
        return cls(
            id=entity.id,
            name=entity.name,
            avatar=entity.avatar,
            title=entity.title,
            background=entity.background,
            personality=entity.personality,
            speaking_style=entity.speaking_style,
            constraints=entity.constraints,
            prompt_template=entity.prompt_template,
            response_config=entity.response_config,
            agent_type=entity.agent_type,
            status=entity.status,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )


class AgentListResponse(BaseModel):
    """Agent 人格列表响应。"""

    agents: list[AgentResponse] = Field(default_factory=list, description="人格列表")
    total: int = Field(default=0, description="总数")


class AgentSwitchRequest(BaseModel):
    """切换当前 Agent 人格请求。"""

    agent_id: int = Field(..., ge=1, description="目标 Agent ID")


class AgentDetailResponse(BaseModel):
    """Agent 人格详情响应（含 system_prompt）。"""

    id: int = Field(description="主键ID")
    name: str = Field(description="人格名称")
    avatar: Optional[str] = Field(default=None, description="头像URL")
    title: str = Field(default="", description="一句话介绍")
    background: str = Field(default="", description="经历背景")
    personality: str = Field(default="", description="性格特点")
    speaking_style: str = Field(default="", description="说话风格")
    constraints: str = Field(default="", description="行为约束")
    prompt_template: Optional[str] = Field(default=None, description="自定义prompt模板")
    response_config: ResponseConfig = Field(description="响应配置")
    agent_type: AgentType = Field(description="人格类型")
    status: AgentStatus = Field(description="状态")
    system_prompt: str = Field(default="", description="生成的系统prompt")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")
