import uuid
from datetime import datetime, timezone
from fastapi import APIRouter
from pydantic import BaseModel, Field
from loguru import logger

from app.runtime.plugin.skill.registry import SkillRegistry
from app.runtime.plugin.skill.base import SkillDefinition
from app.runtime.plugin.skill.parser import SkillParser
from app.infrastructure.database.json_store import skills_store

router = APIRouter(prefix="/skills", tags=["skills"])


class SkillCreate(BaseModel):
    name: str
    description: str = ""
    category: str = "custom"
    parameters: dict = Field(default_factory=dict)
    is_active: bool = True
    prompt_template: str | None = None
    tags: list[str] = Field(default_factory=list)


class SkillUpdate(BaseModel):
    description: str | None = None
    category: str | None = None
    parameters: dict | None = None
    is_active: bool | None = None
    prompt_template: str | None = None
    tags: list[str] | None = None


class SkillResponse(BaseModel):
    name: str
    description: str
    category: str
    parameters: dict = Field(default_factory=dict)
    is_active: bool = True
    is_builtin: bool = False
    prompt_template: str | None = None
    tags: list[str] = Field(default_factory=list)


@router.get("", response_model=list[SkillResponse])
async def list_skills():
    logger.info("[API] GET /skills - Listing all skills")
    skills = SkillRegistry.list_skills()
    return [SkillResponse(**s) for s in skills]


@router.post("", response_model=SkillResponse)
async def create_skill(request: SkillCreate):
    logger.info(f"[API] POST /skills - Creating skill: {request.name}")
    skill = SkillDefinition(
        name=request.name,
        description=request.description,
        category=request.category,
        parameters=request.parameters,
        is_active=request.is_active,
        is_builtin=False,
        prompt_template=request.prompt_template,
        tags=request.tags,
    )
    SkillRegistry.register(skill)
    return SkillResponse(
        name=skill.name,
        description=skill.description,
        category=skill.category,
        parameters=skill.parameters,
        is_active=skill.is_active,
        is_builtin=skill.is_builtin,
        prompt_template=skill.prompt_template,
        tags=skill.tags,
    )


@router.get("/{skill_name}", response_model=SkillResponse)
async def get_skill(skill_name: str):
    logger.info(f"[API] GET /skills/{skill_name} - Fetching skill")
    skill = SkillRegistry.get_skill(skill_name)
    if not skill:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Skill '{skill_name}' not found")
    return SkillResponse(**skill)


@router.patch("/{skill_name}", response_model=SkillResponse)
async def update_skill(skill_name: str, request: SkillUpdate):
    logger.info(f"[API] PATCH /skills/{skill_name} - Updating skill")
    skill_data = SkillRegistry.get_skill(skill_name)
    if not skill_data:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Skill '{skill_name}' not found")

    update_data = request.model_dump(exclude_unset=True)
    skill_data.update(update_data)
    skills_store.set(skill_name, skill_data)
    return SkillResponse(**skill_data)


@router.delete("/{skill_name}")
async def delete_skill(skill_name: str):
    logger.info(f"[API] DELETE /skills/{skill_name} - Deleting skill")
    skill_data = SkillRegistry.get_skill(skill_name)
    if not skill_data:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Skill '{skill_name}' not found")
    if skill_data.get("is_builtin"):
        from app.core.exceptions import ValidationError
        raise ValidationError("Cannot delete builtin skills")
    SkillRegistry.unregister(skill_name)
    return {"error": None, "data": {"deleted": True}}


@router.post("/{skill_name}/execute")
async def execute_skill(skill_name: str, arguments: dict = {}):
    logger.info(f"[API] POST /skills/{skill_name}/execute - Executing skill")
    from app.runtime.plugin.skill.executor import SkillExecutor
    executor = SkillExecutor()
    result = await executor.execute(skill_name, arguments)
    return {"error": None, "data": {"result": result}}


@router.get("/tools/openai")
async def get_openai_tools():
    logger.info("[API] GET /skills/tools/openai - Getting OpenAI format tools")
    tools = SkillRegistry.get_openai_tools()
    return {"error": None, "data": tools}
