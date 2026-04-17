from fastapi import APIRouter

from app.api.v1.endpoints import system, chat, agent, model

api_router = APIRouter()

api_router.include_router(system.router)
api_router.include_router(chat.router)
api_router.include_router(agent.router)
api_router.include_router(model.router)
