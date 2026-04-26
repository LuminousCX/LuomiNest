import uuid
import os
import json
from datetime import datetime, timezone
from fastapi import APIRouter
from pydantic import BaseModel, Field, ConfigDict
from loguru import logger

from app.infrastructure.database.json_store import agents_store
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
    capabilities: list[str] = Field(default_factory=lambda: ["chat"])
    skills: list[str] = Field(default_factory=list)
    mcp_servers: list[str] = Field(default_factory=list)


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
    skills: list[str] | None = None
    mcp_servers: list[str] | None = None


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
    is_active: bool = Field(alias="isActive", default=True)
    is_main: bool = Field(alias="isMain", default=False)
    skills: list[str] = Field(default_factory=list)
    mcp_servers: list[str] = Field(default_factory=list)
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


_DEFAULT_MAIN_AGENT_CONFIG = {
    "provider": "",
    "model": "",
    "system_prompt": "你是 LuomiNest 的主控智能体，负责控制 Live2D 皮套的行为和表情。你需要根据对话内容做出恰当的情感反应，并保持角色的一致性。你的回答应该简洁自然，适合通过皮套形象表达。\n\n你可以使用以下工具来帮助用户：\n- search: 搜索知识库获取相关信息\n- execute_skill: 执行已注册的技能\n- call_mcp_tool: 调用MCP工具\n\n当需要使用工具时，请在回复中使用以下格式：\n<tool_call name=\"工具名\">参数</tool_call\n\n请根据用户的需求选择合适的工具，如果不需要工具则直接回复。",
    "temperature": 0.7,
    "max_tokens": 4096,
}


def _ensure_config_dir():
    os.makedirs(CONFIG_DIR, exist_ok=True)


def _load_main_agent_config() -> dict:
    _ensure_config_dir()
    if not os.path.exists(MAIN_AGENT_CONFIG_FILE):
        logger.debug("Main agent config file not found, using defaults")
        return dict(_DEFAULT_MAIN_AGENT_CONFIG)
    try:
        with open(MAIN_AGENT_CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
            logger.debug(f"Loaded main agent config from {MAIN_AGENT_CONFIG_FILE}")
            return config
    except Exception as e:
        logger.warning(f"Failed to load main agent config: {e}")
        return dict(_DEFAULT_MAIN_AGENT_CONFIG)


def _save_main_agent_config(config: dict):
    _ensure_config_dir()
    try:
        with open(MAIN_AGENT_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        logger.success(f"Saved main agent config to {MAIN_AGENT_CONFIG_FILE}")
    except Exception as e:
        logger.error(f"Failed to save main agent config: {e}")
        raise


@router.get("/main-agent/config", response_model=MainAgentConfigResponse)
async def get_main_agent_config():
    logger.info("[API] GET /agents/main-agent/config - Fetching main agent config")
    config = _load_main_agent_config()
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
    config = _load_main_agent_config()
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

    _save_main_agent_config(config)
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
    agents = [a for a in agents_store.values() if not a.get("is_main", False)]
    logger.success(f"[API] GET /agents - Success: returned {len(agents)} agents")
    return agents


@router.post("", response_model=AgentResponse)
async def create_agent(request: AgentCreate):
    logger.info(f"[API] POST /agents - Creating agent: name={request.name}")
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
        "skills": request.skills,
        "mcp_servers": request.mcp_servers,
        "created_at": now,
        "updated_at": now,
    }
    agents_store.set(agent_id, agent)
    logger.success(f"[API] POST /agents - Agent created: id={agent_id}, name={request.name}")
    return AgentResponse(**agent)


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str):
    logger.info(f"[API] GET /agents/{agent_id} - Fetching agent")
    agent = agents_store.get(agent_id)
    if not agent:
        logger.error(f"[API] GET /agents/{agent_id} - Agent not found")
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Agent {agent_id} not found")
    logger.success(f"[API] GET /agents/{agent_id} - Success: name={agent['name']}")
    return AgentResponse(**agent)


@router.patch("/{agent_id}", response_model=AgentResponse)
async def update_agent(agent_id: str, request: AgentUpdate):
    logger.info(f"[API] PATCH /agents/{agent_id} - Updating agent")
    agent = agents_store.get(agent_id)
    if not agent:
        logger.error(f"[API] PATCH /agents/{agent_id} - Agent not found")
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Agent {agent_id} not found")

    update_data = request.model_dump(exclude_unset=True)
    updated_fields = list(update_data.keys())
    agent.update(update_data)
    agent["updated_at"] = datetime.now(timezone.utc).isoformat()
    agents_store.set(agent_id, agent)

    logger.success(f"[API] PATCH /agents/{agent_id} - Updated fields: {updated_fields}")
    return AgentResponse(**agent)


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str):
    logger.info(f"[API] DELETE /agents/{agent_id} - Deleting agent")
    agent = agents_store.get(agent_id)
    if agent:
        agent_name = agent.get("name", "unknown")
        agents_store.delete(agent_id)
        logger.success(f"[API] DELETE /agents/{agent_id} - Agent deleted: name={agent_name}")
    else:
        logger.warning(f"[API] DELETE /agents/{agent_id} - Agent not found (already deleted)")
    return {"error": None, "data": {"deleted": True}}
