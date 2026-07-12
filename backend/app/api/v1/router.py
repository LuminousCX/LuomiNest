from fastapi import APIRouter

from app.api.v1.endpoints import system, chat, agent, model, social, memory, console, stats, platform, repo_source, marketplace, tools, mcp, scheduler, scheduled_tasks, workflow, smart_home

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
api_router.include_router(tools.router)
api_router.include_router(mcp.router)
api_router.include_router(scheduler.router)
api_router.include_router(workflow.router)
api_router.include_router(scheduled_tasks.router)
api_router.include_router(smart_home.router)
