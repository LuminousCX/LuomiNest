import uuid
import os
import shutil
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from loguru import logger

from app.infrastructure.database.json_store import agents_store
from app.infrastructure.database.facades.main_agent_config import (
    load_luominest_main_agent_config,
    save_luominest_main_agent_config,
)
from app.core.config import settings
from app.core.utils import utc_now, ok
from app.core.exceptions import NotFoundError

router = APIRouter(prefix="/agents", tags=["agents"])


class AgentCreate(BaseModel):
    name: str
    description: str = ""
    system_prompt: str = ""
    model: str | None = None
    provider: str | None = None
    color: str = "#0d9488"
    avatar: str | None = None
    capabilities: list[str] = Field(default_factory=lambda: ["chat"])
    memory_access: str = "none"


class AgentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    model: str | None = None
    provider: str | None = None
    color: str | None = None
    avatar: str | None = None
    capabilities: list[str] | None = None
    is_active: bool | None = None
    memory_access: str | None = None


class AgentResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, by_alias=True)

    id: str
    name: str
    description: str
    system_prompt: str = Field(alias="systemPrompt", default="")
    model: str | None = None
    provider: str | None = None
    color: str
    avatar: str | None = None
    capabilities: list[str] = Field(default_factory=lambda: ["chat"])
    memory_access: str = Field(alias="memoryAccess", default="none")
    is_active: bool = Field(alias="isActive", default=True)
    is_main: bool = Field(alias="isMain", default=False)
    created_at: str = Field(alias="createdAt", default="")
    updated_at: str = Field(alias="updatedAt", default="")


class MainAgentConfigUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    provider: str | None = None
    model: str | None = None
    system_prompt: str | None = Field(alias="systemPrompt", default=None)
    temperature: float | None = None
    max_tokens: int | None = Field(alias="maxTokens", default=None)


class MainAgentConfigResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, by_alias=True)

    provider: str = ""
    model: str = ""
    system_prompt: str = Field(alias="systemPrompt", default="")
    temperature: float = 0.7
    max_tokens: int = Field(alias="maxTokens", default=4096)


@router.get("/main-agent/config", response_model=MainAgentConfigResponse)
async def get_main_agent_config():
    logger.info("[API] GET /agents/main-agent/config - Fetching main agent config")
    config = load_luominest_main_agent_config()
    response = MainAgentConfigResponse(
        provider=config.get("provider", ""),
        model=config.get("model", ""),
        system_prompt=config.get("system_prompt", ""),
        temperature=config.get("temperature", 0.7),
        max_tokens=config.get("max_tokens", 4096),
    )
    logger.success(f"[API] GET /agents/main-agent/config - Success: provider={response.provider}, model={response.model}")
    return response


@router.patch("/main-agent/config", response_model=MainAgentConfigResponse)
async def update_main_agent_config(request: MainAgentConfigUpdate):
    logger.info("[API] PATCH /agents/main-agent/config - Updating main agent config")
    config = load_luominest_main_agent_config()
    update_data = request.model_dump(exclude_unset=True, by_alias=False)

    updated_fields = []
    if update_data.get("system_prompt") is not None:
        config["system_prompt"] = update_data["system_prompt"]
        updated_fields.append("system_prompt")
    if update_data.get("max_tokens") is not None:
        config["max_tokens"] = update_data["max_tokens"]
        updated_fields.append("max_tokens")

    for key in ("provider", "model", "temperature"):
        if key in update_data and update_data[key] is not None:
            config[key] = update_data[key]
            updated_fields.append(key)

    save_luominest_main_agent_config(config)
    logger.success(f"[API] PATCH /agents/main-agent/config - Updated fields: {updated_fields}")

    return MainAgentConfigResponse(
        provider=config.get("provider", ""),
        model=config.get("model", ""),
        system_prompt=config.get("system_prompt", ""),
        temperature=config.get("temperature", 0.7),
        max_tokens=config.get("max_tokens", 4096),
    )


@router.get("", response_model=list[AgentResponse])
async def list_agents():
    logger.info("[API] GET /agents - Listing all agents")
    agents = [a for a in await agents_store.values_async() if not a.get("is_main", False)]
    logger.success(f"[API] GET /agents - Success: returned {len(agents)} agents")
    return agents


@router.post("", response_model=AgentResponse)
async def create_agent(request: AgentCreate):
    logger.info(f"[API] POST /agents - Creating agent: name={request.name}")
    
    agents = await agents_store.all_async()
    if len(agents) >= 10:
        raise HTTPException(status_code=400, detail="最多只能创建 10 个 Agent")
    
    for agent in agents:
        if agent.get("name") == request.name:
            raise HTTPException(status_code=400, detail=f"Agent 名称 '{request.name}' 已存在")
    
    agent_id = str(uuid.uuid4())
    now = utc_now()
    agent = {
        "id": agent_id,
        "name": request.name,
        "description": request.description,
        "system_prompt": request.system_prompt,
        "model": request.model,
        "provider": request.provider,
        "color": request.color,
        "avatar": request.avatar,
        "capabilities": request.capabilities,
        "memory_access": request.memory_access,
        "is_active": True,
        "is_main": False,
        "created_at": now,
        "updated_at": now,
    }
    await agents_store.set_async(agent_id, agent)
    logger.success(f"[API] POST /agents - Agent created: id={agent_id}, name={request.name}")
    return AgentResponse(**agent)


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str):
    logger.info(f"[API] GET /agents/{agent_id} - Fetching agent")
    agent = await agents_store.get_async(agent_id)
    if not agent:
        logger.error(f"[API] GET /agents/{agent_id} - Agent not found")
        raise NotFoundError(f"Agent {agent_id} not found")
    logger.success(f"[API] GET /agents/{agent_id} - Success: name={agent['name']}")
    return AgentResponse(**agent)


@router.patch("/{agent_id}", response_model=AgentResponse)
async def update_agent(agent_id: str, request: AgentUpdate):
    logger.info(f"[API] PATCH /agents/{agent_id} - Updating agent")
    agent = await agents_store.get_async(agent_id)
    if not agent:
        logger.error(f"[API] PATCH /agents/{agent_id} - Agent not found")
        raise NotFoundError(f"Agent {agent_id} not found")

    update_data = request.model_dump(exclude_unset=True)
    
    if "name" in update_data:
        new_name = update_data["name"]
        all_agents = await agents_store.all_async()
        for ag in all_agents:
            if ag.get("id") != agent_id and ag.get("name") == new_name:
                raise HTTPException(status_code=400, detail=f"Agent 名称 '{new_name}' 已存在")
    updated_fields = list(update_data.keys())
    agent.update(update_data)
    agent["updated_at"] = utc_now()
    await agents_store.set_async(agent_id, agent)

    logger.success(f"[API] PATCH /agents/{agent_id} - Updated fields: {updated_fields}")
    return AgentResponse(**agent)


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str):
    logger.info(f"[API] DELETE /agents/{agent_id} - Deleting agent")
    agent = await agents_store.get_async(agent_id)
    if agent:
        agent_name = agent.get("name", "unknown")
        await agents_store.delete_async(agent_id)
        logger.success(f"[API] DELETE /agents/{agent_id} - Agent deleted: name={agent_name}")
    else:
        logger.warning(f"[API] DELETE /agents/{agent_id} - Agent not found (already deleted)")
    
    from app.infrastructure.database.conversation_store import conversation_store
    conversation_store.delete_by_agent_id(agent_id)
    
    agent_memory_dir = os.path.join(settings.DATA_DIR, "memory", "agents", agent_id)
    if os.path.exists(agent_memory_dir):
        shutil.rmtree(agent_memory_dir)
        logger.info(f"[API] DELETE /agents/{agent_id} - Memory directory removed")
    
    return ok({"deleted": True})
