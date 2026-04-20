from contextlib import asynccontextmanager
from fastapi import FastAPI
from loguru import logger

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.infrastructure.database import init_db, close_db
from app.infrastructure.redis import init_redis, close_redis
from app.infrastructure.mqtt import init_mqtt, close_mqtt
from app.runtime.event_bus import EventBus
from app.runtime.pipeline import Pipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("LuomiNest starting up...")

    await init_db()
    await init_redis()
    await init_mqtt()

    app.state.event_bus = EventBus()
    app.state.pipeline = Pipeline(app.state.event_bus)

    yield

    logger.info("LuomiNest shutting down...")
    await close_mqtt()
    await close_redis()
    await close_db()


def create_app() -> FastAPI:
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

    register_exception_handlers(app)

    return app
