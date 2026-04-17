from contextlib import asynccontextmanager
from loguru import logger

from app.core.config import settings
from app.core.exceptions import register_exception_handlers


@asynccontextmanager
async def lifespan(app):
    logger.info("LuomiNest starting up...")
    yield
    logger.info("LuomiNest shutting down...")


def create_app():
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    app = FastAPI(
        title="LuomiNest API",
        version="0.1.0",
        description="LuomiNest Distributed Whole-House AI Companion System",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from app.api.v1.router import api_router
    app.include_router(api_router, prefix="/api/v1")

    from app.api.ws.router import ws_router
    app.include_router(ws_router, prefix="/ws")

    @app.get("/health")
    async def health():
        return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}

    register_exception_handlers(app)

    return app
