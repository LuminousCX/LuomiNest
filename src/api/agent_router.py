"""Agent 人格管理 API 路由。

提供 Agent 人格的增删改查、切换等接口。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from typing_extensions import Annotated

from src.schema.agent_schema import (
    AgentCreateRequest,
    AgentDetailResponse,
    AgentListResponse,
    AgentResponse,
    AgentSwitchRequest,
    AgentUpdateRequest,
)
from src.schema.common_schema import ApiResponse
from src.service.agent_service import AgentService
from src.service.prompt_template import get_prompt_template_service
from src.utils.datetime_utils import format_datetime
from src.utils.logger import get_logger

logger = get_logger()

router = APIRouter(prefix="/agents", tags=["Agent 人格管理"])


def get_agent_service() -> AgentService:
    """获取 AgentService 实例（依赖注入）。"""
    from src.api.deps import get_services
    return get_services()["agent_service"]


def _entity_to_response(agent) -> AgentResponse:
    """将 AgentEntity 转换为 AgentResponse。"""
    return AgentResponse.from_entity(agent)


@router.get("", summary="获取所有 Agent 人格")
async def list_agents(
    agent_service: Annotated[AgentService, Depends(get_agent_service)],
) -> ApiResponse[AgentListResponse]:
    """获取所有活跃的 Agent 人格列表。"""
    agents = agent_service.get_all_agents()
    agent_responses = [_entity_to_response(a) for a in agents]
    data = AgentListResponse(agents=agent_responses, total=len(agent_responses))
    return ApiResponse.success(data=data)


@router.get("/preset", summary="获取预设 Agent 人格")
async def list_preset_agents(
    agent_service: Annotated[AgentService, Depends(get_agent_service)],
) -> ApiResponse[AgentListResponse]:
    """获取所有预设 Agent 人格。"""
    agents = agent_service.get_preset_agents()
    agent_responses = [_entity_to_response(a) for a in agents]
    data = AgentListResponse(agents=agent_responses, total=len(agent_responses))
    return ApiResponse.success(data=data)


@router.get("/current", summary="获取当前 Agent 人格")
async def get_current_agent(
    agent_service: Annotated[AgentService, Depends(get_agent_service)],
) -> ApiResponse[AgentResponse]:
    """获取当前激活的 Agent 人格。"""
    agent = agent_service.get_current_agent()
    return ApiResponse.success(data=_entity_to_response(agent))


@router.get("/{agent_id}", summary="获取指定 Agent 人格")
async def get_agent(
    agent_id: int,
    agent_service: Annotated[AgentService, Depends(get_agent_service)],
) -> ApiResponse[AgentDetailResponse]:
    """根据 ID 获取 Agent 人格详情（含 system_prompt）。"""
    agent = agent_service.get_agent_by_id(agent_id)
    template_service = get_prompt_template_service()
    system_prompt = agent.build_system_prompt(template_service)

    data = AgentDetailResponse(
        id=agent.id,
        name=agent.name,
        avatar=agent.avatar,
        title=agent.title,
        background=agent.background,
        personality=agent.personality,
        speaking_style=agent.speaking_style,
        prompt_template=agent.prompt_template,
        response_config=agent.response_config,
        agent_type=agent.agent_type,
        status=agent.status,
        system_prompt=system_prompt,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )
    return ApiResponse.success(data=data)


@router.post("", summary="创建自定义 Agent 人格")
async def create_agent(
    request: AgentCreateRequest,
    agent_service: Annotated[AgentService, Depends(get_agent_service)],
) -> ApiResponse[AgentResponse]:
    """创建自定义 Agent 人格。"""
    agent = agent_service.create_agent(request)
    return ApiResponse.success(data=_entity_to_response(agent))


@router.put("/{agent_id}", summary="更新 Agent 人格")
async def update_agent(
    agent_id: int,
    request: AgentUpdateRequest,
    agent_service: Annotated[AgentService, Depends(get_agent_service)],
) -> ApiResponse[AgentResponse]:
    """更新 Agent 人格信息。"""
    agent = agent_service.update_agent(agent_id, request)
    return ApiResponse.success(data=_entity_to_response(agent))


@router.delete("/{agent_id}", summary="删除 Agent 人格")
async def delete_agent(
    agent_id: int,
    agent_service: Annotated[AgentService, Depends(get_agent_service)],
) -> ApiResponse[None]:
    """删除自定义 Agent 人格（预设人格不可删除）。"""
    agent_service.delete_agent(agent_id)
    return ApiResponse.success(message="删除成功")


@router.post("/switch", summary="切换当前 Agent 人格")
async def switch_agent(
    request: AgentSwitchRequest,
    agent_service: Annotated[AgentService, Depends(get_agent_service)],
) -> ApiResponse[AgentResponse]:
    """切换当前激活的 Agent 人格。"""
    agent = agent_service.switch_agent(request.agent_id)
    return ApiResponse.success(data=_entity_to_response(agent))
