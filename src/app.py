"""LuomiNest FastAPI 应用入口。

创建 FastAPI 应用实例，注册路由、中间件，
提供应用生命周期管理。
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware

from src.api.agent_router import router as agent_router
from src.api.chat_router import router as chat_router
from src.api.deps import init_services
from src.api.file_api import router as file_router
from src.api.memory_router import router as memory_router
from src.api.middleware import ExceptionMiddleware, LoggingMiddleware
from src.config.settings import get_settings
from src.utils.logger import get_logger

logger = get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理。"""
    settings = get_settings()
    logger.info(f"LuomiNest 后端服务启动中...")
    logger.info(f"数据目录: {settings.data_dir}")
    logger.info(f"模型: {settings.llm_model_id}")

    init_services()
    logger.info("服务初始化完成")

    yield

    from src.api.deps import get_services
    services = get_services()
    memory_service = services.get("memory_service")
    if memory_service and hasattr(memory_service, "recall_engine"):
        memory_service.recall_engine.shutdown()

    logger.info("LuomiNest 后端服务关闭")


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例。"""
    settings = get_settings()

    app = FastAPI(
        title="LuomiNest API",
        description="AI Agent 桌面应用后端服务",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )

    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(ExceptionMiddleware)
    app.add_middleware(LoggingMiddleware)

    app.include_router(agent_router, prefix="/api/v1")
    app.include_router(chat_router, prefix="/api/v1")
    app.include_router(file_router, prefix="/api/v1")
    app.include_router(memory_router, prefix="/api/v1")

    @app.get("/health", tags=["健康检查"])
    async def health_check() -> dict:
        """健康检查接口。"""
        return {"status": "ok", "service": "LuomiNest"}

    return app


app = create_app()


def main():
    """应用入口函数。"""
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "src.app:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )


if __name__ == "__main__":
    main()
