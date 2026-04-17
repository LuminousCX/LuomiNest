import uuid
import os
import json
from fastapi import APIRouter
from pydantic import BaseModel, Field, ConfigDict
from typing import Any
from loguru import logger

from app.runtime.provider.llm.adapter import llm_adapter

router = APIRouter(prefix="/agents", tags=["agents"])

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))), "data")
MAIN_AGENT_CONFIG_FILE = os.path.join(CONFIG_DIR, "main_agent.json")


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
    is_main: bool = False
    created_at: str = ""
    updated_at: str = ""


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
        "is_main": False,
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
        "is_main": False,
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
        "is_main": False,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    },
}

_DEFAULT_MAIN_AGENT_CONFIG = {
    "provider": "",
    "model": "",
    "system_prompt": "你是 LuomiNest 的主控智能体，负责控制 Live2D 皮套的行为和表情。你需要根据对话内容做出恰当的情感反应，并保持角色的一致性。你的回答应该简洁自然，适合通过皮套形象表达。",
    "temperature": 0.7,
    "max_tokens": 4096,
}


def _ensure_config_dir():
    os.makedirs(CONFIG_DIR, exist_ok=True)


def _load_main_agent_config() -> dict:
    _ensure_config_dir()
    if not os.path.exists(MAIN_AGENT_CONFIG_FILE):
        return dict(_DEFAULT_MAIN_AGENT_CONFIG)
    try:
        with open(MAIN_AGENT_CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load main agent config: {e}")
        return dict(_DEFAULT_MAIN_AGENT_CONFIG)


def _save_main_agent_config(config: dict):
    _ensure_config_dir()
    try:
        with open(MAIN_AGENT_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save main agent config: {e}")


@router.get("/main-agent/config", response_model=MainAgentConfigResponse)
async def get_main_agent_config():
    config = _load_main_agent_config()
    return MainAgentConfigResponse(
        provider=config.get("provider", ""),
        model=config.get("model", ""),
        system_prompt=config.get("system_prompt", ""),
        temperature=config.get("temperature", 0.7),
        max_tokens=config.get("max_tokens", 4096),
    )


@router.patch("/main-agent/config", response_model=MainAgentConfigResponse)
async def update_main_agent_config(request: MainAgentConfigUpdate):
    config = _load_main_agent_config()
    update_data = request.model_dump(exclude_unset=True, by_alias=False)

    if "system_prompt" in update_data or "systemPrompt" in update_data:
        val = update_data.get("system_prompt") or update_data.get("systemPrompt")
        if val is not None:
            config["system_prompt"] = val
    if "max_tokens" in update_data or "maxTokens" in update_data:
        val = update_data.get("max_tokens") or update_data.get("maxTokens")
        if val is not None:
            config["max_tokens"] = val

    for key in ("provider", "model", "temperature"):
        if key in update_data and update_data[key] is not None:
            config[key] = update_data[key]

    _save_main_agent_config(config)

    return MainAgentConfigResponse(
        provider=config.get("provider", ""),
        model=config.get("model", ""),
        system_prompt=config.get("system_prompt", ""),
        temperature=config.get("temperature", 0.7),
        max_tokens=config.get("max_tokens", 4096),
    )


@router.get("", response_model=list[AgentResponse])
async def list_agents():
    return [a for a in _agents.values() if not a.get("is_main", False)]


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
        "is_main": False,
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
