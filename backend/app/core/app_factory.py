import time
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.exceptions import LuomiNestError
from app.api.v1.router import api_router
from app.api.attachment_api import router as attachment_router
from app.security.auth.local_token import load_auth_token
from app.security.auth.middleware import luomi_auth_middleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"[LuomiNest] Starting application...")
    logger.info(f"[LuomiNest] Environment: {'Development' if settings.DEBUG else 'Production'}")

    try:
        from app.infrastructure.database.conversation_store import conversation_store
        from app.infrastructure.database.json_store import conversations_store
        conversation_store.migrate_from_json_store(conversations_store)
    except Exception as e:
        logger.warning(f"[LuomiNest] Conversation migration skipped: {e}")

    try:
        from app.engines.memory import init_memory
        await init_memory()
    except Exception as e:
        logger.warning(f"[LuomiNest] Memory engine init skipped: {e}")

    # 注册内置工具
    try:
        from app.core.tools import tool_registry
        from app.core.tools.builtin import (
            CliTool, ReadFileTool, WriteFileTool, ListFilesTool, SearchFilesTool,
            McpTool, ListMcpServersTool, DelegateToSubagentTool,
            CreateScheduledTaskTool, CreateBrowserTabTool,
        )
        tool_registry.register(CliTool())
        tool_registry.register(ReadFileTool())
        tool_registry.register(WriteFileTool())
        tool_registry.register(ListFilesTool())
        tool_registry.register(SearchFilesTool())
        tool_registry.register(McpTool())
        tool_registry.register(ListMcpServersTool())
        tool_registry.register(DelegateToSubagentTool())
        tool_registry.register(CreateScheduledTaskTool())
        tool_registry.register(CreateBrowserTabTool())

        # Agent 集群调用工具：OpenAI 兼容 API 自回调
        from app.core.agents.cluster.agent_tool import LuomiNestAgentCallTool
        tool_registry.register(LuomiNestAgentCallTool())

        # Agent 集群调用工具：A2A 协议跨服务调用（根据配置动态注册）
        from app.core.agents.cluster.a2a_tool import get_luominest_a2a_tools
        for a2a_tool in get_luominest_a2a_tools():
            tool_registry.register(a2a_tool)

        # 工作台多 Agent 协作工具：主 Agent 触发临时多 Agent 协作
        from app.core.tools.builtin.collaboration_tool import LuomiNestStartCollaborationTool
        tool_registry.register(LuomiNestStartCollaborationTool())

        # 记忆主动搜索工具：群聊 Agent 主动查主 Agent 记忆（contextvar 权限控制）
        from app.core.tools.builtin.memory_search_tool import LuomiNestMemorySearchTool
        tool_registry.register(LuomiNestMemorySearchTool())

        logger.info(f"[LuomiNest] Registered {len(tool_registry.list_names())} tools: {', '.join(tool_registry.list_names())}")
    except Exception as e:
        logger.warning(f"[LuomiNest] Tool registration skipped: {e}")

    # 注册工作流内部模块接口
    try:
        from app.core.workflow.register_tools import register_internal_tools
        await register_internal_tools()
    except Exception as e:
        logger.warning(f"[LuomiNest] Workflow internal tools registration skipped: {e}")

    # 加载 CxPlugin 插件系统
    try:
        from app.services.plugin_service import cx_plugin_service
        from app.runtime.plugin.cxplugin import init_hot_reload
        plugin_count = await cx_plugin_service.initialize()
        logger.info(f"[LuomiNest] Loaded {plugin_count} CxPlugin(s)")
        init_hot_reload()
    except Exception as e:
        logger.warning(f"[LuomiNest] CxPlugin loading skipped: {e}")

    # 启动定时任务调度器（APScheduler）
    try:
        from app.core.scheduler import luomi_scheduler
        await luomi_scheduler.init()
        logger.info(f"[LuomiNest] Scheduler started, tasks: {len(luomi_scheduler.list_tasks())}")
    except Exception as e:
        logger.warning(f"[LuomiNest] Scheduler init skipped: {e}")

    # 初始化 MCP 管理器（加载配置并自动连接）
    try:
        from app.core.tools.mcp.manager import mcp_manager
        await mcp_manager.init()
        servers = mcp_manager.list_servers()
        if servers:
            logger.info(f"[LuomiNest] MCP servers: {len(servers)} configured")
        else:
            logger.info(f"[LuomiNest] No MCP servers configured")
    except Exception as e:
        logger.warning(f"[LuomiNest] MCP manager init skipped: {e}")

    # 启动平台消息路由器（QQ/微信/Minecraft/游戏等）
    try:
        from app.services.platform_router import attach_router_to_instances
        attach_router_to_instances()
        logger.info(f"[LuomiNest] Platform router attached to instances")
    except Exception as e:
        logger.warning(f"[LuomiNest] Platform router init skipped: {e}")

    # 启动时清理临时文件
    try:
        from app.services.cleanup_service import lumi_cleanup_service
        temp_cleaned = lumi_cleanup_service.cleanup_temp_files()
        if temp_cleaned > 0:
            logger.info(f"[LuomiNest] Cleaned {temp_cleaned} temp files on startup")
    except Exception as e:
        logger.warning(f"[LuomiNest] Startup cleanup skipped: {e}")

    # 注册定时清理任务（每24小时执行一次）
    try:
        from apscheduler.triggers.interval import IntervalTrigger
        from app.services.cleanup_service import lumi_cleanup_service

        async def _periodic_cleanup():
            try:
                await lumi_cleanup_service.run_all_async()
            except Exception as cleanup_err:
                logger.warning(f"[LuomiNest] Periodic cleanup failed: {cleanup_err}")

        if luomi_scheduler._scheduler is not None:
            luomi_scheduler._scheduler.add_job(
                _periodic_cleanup,
                trigger=IntervalTrigger(hours=24),
                id="lumi_periodic_cleanup",
                replace_existing=True,
            )
            logger.info(f"[LuomiNest] Periodic cleanup job registered (every 24h)")
    except Exception as e:
        logger.warning(f"[LuomiNest] Periodic cleanup registration skipped: {e}")

    yield

    # 停止 CxPlugin 热重载监听
    try:
        from app.runtime.plugin.cxplugin import shutdown_hot_reload
        await shutdown_hot_reload()
        logger.info(f"[LuomiNest] CxPlugin hot reload stopped")
    except Exception as e:
        logger.warning(f"[LuomiNest] CxPlugin shutdown skipped: {e}")

    # 停止所有平台实例
    try:
        from app.runtime.platform.registry import stop_all_instances
        await stop_all_instances()
        logger.info(f"[LuomiNest] Platform instances stopped")
    except Exception as e:
        logger.warning(f"[LuomiNest] Platform shutdown skipped: {e}")

    # 断开所有 MCP 连接
    try:
        from app.core.tools.mcp.manager import mcp_manager
        await mcp_manager.disconnect_all()
        logger.info(f"[LuomiNest] MCP connections closed")
    except Exception as e:
        logger.warning(f"[LuomiNest] MCP shutdown skipped: {e}")

    # 关闭定时任务调度器
    try:
        from app.core.scheduler import luomi_scheduler
        await luomi_scheduler.shutdown()
        logger.info(f"[LuomiNest] Scheduler stopped")
    except Exception as e:
        logger.warning(f"[LuomiNest] Scheduler shutdown skipped: {e}")

    try:
        from app.engines.memory import shutdown_memory
        await shutdown_memory()
    except Exception as e:
        logger.warning(f"[LuomiNest] Memory engine shutdown skipped: {e}")

    logger.info(f"[LuomiNest] Shutting down application...")


def create_app() -> FastAPI:
    logger.info("[AppFactory] Creating FastAPI application...")

    app = FastAPI(
        title="LuomiNest API",
        description="LuomiNest - AI Agent Platform Backend API",
        version="0.7.0",
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

    auth_token = load_auth_token()
    if auth_token:
        logger.success("[AppFactory] Auth token loaded, API routes protected")
    else:
        logger.warning("[AppFactory] No auth token, API routes unprotected (dev mode)")

    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        return await luomi_auth_middleware(request, call_next)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
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
    app.include_router(attachment_router, prefix="/api")

    @app.get("/health")
    async def health_check():
        return {"status": "ok", "service": "LuomiNest"}

    @app.get("/")
    async def root():
        return {
            "name": "LuomiNest",
            "version": "0.7.0",
            "docs": "/docs" if settings.DEBUG else "disabled",
        }

    logger.success("[AppFactory] FastAPI application created successfully")
    return app
