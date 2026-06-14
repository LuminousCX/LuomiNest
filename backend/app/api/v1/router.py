from fastapi import APIRouter

from app.api.v1.endpoints import system, chat, agent, model, social, memory, console, stats, platform, repo_source, marketplace

api_router = APIRouter()
api_router.include_router(system.router)
api_router.include_router(chat.router)
api_router.include_router(agent.router)
api_router.include_router(model.router)
api_router.include_router(social.router)
api_router.include_router(memory.router)
api_router.include_router(console.router)
api_router.include_router(stats.router)
api_router.include_router(platform.router)
api_router.include_router(repo_source.router)
api_router.include_router(marketplace.router)
