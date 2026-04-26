from fastapi import APIRouter

from app.api.v1.endpoints import system, chat, agent, model, skill, mcp, social

api_router = APIRouter()

api_router.include_router(system.router)
api_router.include_router(chat.router)
api_router.include_router(agent.router)
api_router.include_router(model.router)
api_router.include_router(skill.router)
api_router.include_router(mcp.router)
api_router.include_router(social.router)
