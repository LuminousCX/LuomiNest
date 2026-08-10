from fastapi import APIRouter

from app.core.config import settings
from app.core.platform_info import get_system_info

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
    """返回应用信息与运行环境（操作系统 / 发行版 / 包管理器 / 架构）."""
    from app.core.hardware import get_hardware_profile

    sys_info = get_system_info()
    profile = get_hardware_profile()
    return {
        "data": {
            "app_name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "default_provider": settings.LLM_DEFAULT_PROVIDER,
            "ollama_base_url": settings.OLLAMA_BASE_URL,
            "system": sys_info.to_dict(),
            "hardware": {
                "cpu_count": profile.cpu_count,
                "total_memory_gb": profile.total_memory_gb,
                "gpu_type": profile.gpu_type.value,
                "gpu_count": profile.gpu_count,
                "gpu_names": profile.gpu_names or [],
            },
        }
    }
