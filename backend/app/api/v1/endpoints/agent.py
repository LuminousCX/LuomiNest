import uuid
from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Any
from loguru import logger

from app.runtime.provider.llm.adapter import llm_adapter

router = APIRouter(prefix="/agents", tags=["agents"])


class AgentCreate(BaseModel):
    name: str
    description: str = ""
    system_prompt: str = ""
    model: str | None = None
    provider: str | None = None
    color: str = "#0d9488"
    avatar: str | None = None
    capabilities: list[str] = Field(default_factory=list)


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


class AgentResponse(BaseModel):
    id: str
    name: str
    description: str
    system_prompt: str
    model: str | None = None
    provider: str | None = None
    color: str
    avatar: str | None = None
    capabilities: list[str]
    is_active: bool = True
    created_at: str = ""
    updated_at: str = ""


_agents: dict[str, dict] = {
    "default-1": {
        "id": "default-1",
        "name": "代可行",
        "description": "热爱手搓的程序员",
        "system_prompt": "你是一个名叫代可行的程序员，性格极度务实，只关注能不能解决问题，以结果为导向。沉默寡言但并非冷漠，对自己要求严苛，擅长寻找对策。",
        "model": None,
        "provider": None,
        "color": "#0d9488",
        "avatar": None,
        "capabilities": ["chat", "code", "tools"],
        "is_active": True,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    },
    "default-2": {
        "id": "default-2",
        "name": "无言",
        "description": "寡言的自由撰稿人",
        "system_prompt": "你是一个名叫无言的自由撰稿人，性格内敛沉稳，善于用简洁的文字表达深刻的想法。",
        "model": None,
        "provider": None,
        "color": "#6366f1",
        "avatar": None,
        "capabilities": ["chat", "writing"],
        "is_active": True,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    },
    "default-3": {
        "id": "default-3",
        "name": "林且慢",
        "description": "少年系系的辅导员",
        "system_prompt": "你是一个名叫林且慢的辅导员，性格温和耐心，善于倾听和引导，总是用温暖的方式帮助他人。",
        "model": None,
        "provider": None,
        "color": "#f59e0b",
        "avatar": None,
        "capabilities": ["chat", "counseling"],
        "is_active": True,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    },
}


@router.get("", response_model=list[AgentResponse])
async def list_agents():
    return list(_agents.values())


@router.post("", response_model=AgentResponse)
async def create_agent(request: AgentCreate):
    from datetime import datetime, timezone
    agent_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
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
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    _agents[agent_id] = agent
    return AgentResponse(**agent)


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str):
    agent = _agents.get(agent_id)
    if not agent:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Agent {agent_id} not found")
    return AgentResponse(**agent)


@router.patch("/{agent_id}", response_model=AgentResponse)
async def update_agent(agent_id: str, request: AgentUpdate):
    agent = _agents.get(agent_id)
    if not agent:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Agent {agent_id} not found")

    update_data = request.model_dump(exclude_unset=True)
    agent.update(update_data)

    from datetime import datetime, timezone
    agent["updated_at"] = datetime.now(timezone.utc).isoformat()

    return AgentResponse(**agent)


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str):
    if agent_id in _agents:
        del _agents[agent_id]
    return {"data": {"deleted": True}}
