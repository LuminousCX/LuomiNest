import time
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.exceptions import LuomiNestError
from app.api.v1.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"[LuomiNest] Starting application...")
    logger.info(f"[LuomiNest] Environment: {'Development' if settings.DEBUG else 'Production'}")
    logger.info(f"[LuomiNest] API docs: http://127.0.0.1:{settings.PORT}/docs")
    yield
    logger.info(f"[LuomiNest] Shutting down application...")


def create_app() -> FastAPI:
    logger.info("[AppFactory] Creating FastAPI application...")

    app = FastAPI(
        title="LuomiNest API",
        description="LuomiNest - AI Agent Platform Backend API",
        version="0.1.0",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start_time = time.time()

        request_id = id(request)
        method = request.method
        path = request.url.path
        query = str(request.query_params) if request.query_params else ""

        logger.info(f"[HTTP] --> {method} {path}{f'?{query}' if query else ''} (id={request_id})")

        try:
            response: Response = await call_next(request)
            elapsed = time.time() - start_time
            status = response.status_code

            if status < 400:
                log_func = logger.success
            elif status < 500:
                log_func = logger.warning
            else:
                log_func = logger.error

            log_func(f"[HTTP] <-- {method} {path} {status} ({elapsed*1000:.1f}ms)")

            response.headers["X-Request-ID"] = str(request_id)
            response.headers["X-Response-Time"] = f"{elapsed*1000:.1f}ms"
            return response

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"[HTTP] <-- {method} {path} 500 ({elapsed*1000:.1f}ms) ERROR: {e}")
            raise

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(LuomiNestError)
    async def lumi_error_handler(request: Request, exc: LuomiNestError):
        logger.error(f"[Exception] LuomiNestError: {exc.message} (code={exc.code})")
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception):
        logger.error(f"[Exception] Unhandled exception: {exc}")
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": str(exc)}},
        )

    app.include_router(api_router, prefix="/api/v1")

    @app.get("/health")
    async def health_check():
        return {"status": "ok", "service": "LuomiNest"}

    @app.get("/")
    async def root():
        return {
            "name": "LuomiNest",
            "version": "0.1.0",
            "docs": "/docs" if settings.DEBUG else "disabled",
        }

    logger.success("[AppFactory] FastAPI application created successfully")
    return app
