from fastapi import APIRouter
from app.core.config import settings

router = APIRouter(tags=["system"])


@router.get("/health")
async def health_check():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }


@router.get("/info")
async def system_info():
    return {
        "data": {
            "app_name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "default_provider": settings.LLM_DEFAULT_PROVIDER,
            "ollama_base_url": settings.OLLAMA_BASE_URL,
        }
    }
