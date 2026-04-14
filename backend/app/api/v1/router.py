from fastapi import APIRouter

from app.api.v1.endpoints import model_asset

api_router = APIRouter()

api_router.include_router(model_asset.router)
