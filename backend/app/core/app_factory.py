import time
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from contextlib import asynccontextmanager
import os
import sys
import shutil

from app.core.config import settings
from app.core.exceptions import LuomiNestError
from app.core.hardware import get_hardware_profile
from app.api.v1.router import api_router
from app.api.attachment_api import router as attachment_router
from app.security.auth.local_token import load_auth_token
from app.security.auth.middleware import luomi_auth_middleware


def _sync_bundled_plugin_resources() -> None:
    """打包模式下首次启动时把 _internal/{plugins,skills}/ 复制到可写的 DATA_DIR 下。

    背景：PyInstaller spec 将 backend/plugins、backend/skills 作为 datas 打包，
    运行时被解压到 <exe_dir>/_internal/{plugins,skills}/（只读）。
    config.py 在 frozen 模式下把 PLUGIN_DIR/SKILL_DIR 指向 DATA_DIR 下的可写副本，
    但首次启动时该副本目录为空，导致 luominest_plugin_loader 扫描不到任何插件。

    本函数完成"首次复制 + 增量同步"：
    - 对每个内置插件/技能目录，若目标不存在则整目录复制；
    - 若目标已存在但 manifest.json 版本不同，则更新（保留用户的 data/ 子目录）；
    - 若目标已存在且版本相同，跳过（避免每次启动都覆盖用户改动）。

    dev 模式下（IS_FROZEN=False）直接 return，由源码目录加载。
    """
    if not settings.IS_FROZEN:
        return

    # PyInstaller 运行时资源根：sys._MEIPASS 指向解压临时目录（即 _internal/）
    bundle_root = getattr(sys, "_MEIPASS", None)
    if not bundle_root:
        # 某些 onefile 模式可能无 _MEIPASS，退回到 exe 同级 _internal/
        bundle_root = os.path.join(os.path.dirname(sys.executable), "_internal")

    bundle_pairs = [
        (os.path.join(bundle_root, "plugins"), settings.PLUGIN_DIR, "plugin"),
        (os.path.join(bundle_root, "skills"), settings.SKILL_DIR, "skill"),
    ]

    for src_root, dst_root, label in bundle_pairs:
        if not os.path.isdir(src_root):
            logger.debug(f"[BundledSync] {label} source not found: {src_root}, skip")
            continue
        os.makedirs(dst_root, exist_ok=True)

        for entry in os.listdir(src_root):
            if entry.startswith(".") or entry.startswith("_"):
                continue
            src_dir = os.path.join(src_root, entry)
            dst_dir = os.path.join(dst_root, entry)
            if not os.path.isdir(src_dir):
                continue

            # 读取源 manifest 版本
            src_manifest = os.path.join(src_dir, "manifest.json")
            src_skill_md = os.path.join(src_dir, "SKILL.md")
            src_version = ""
            if os.path.isfile(src_manifest):
                try:
                    import json
                    with open(src_manifest, encoding="utf-8") as f:
                        src_version = str(json.load(f).get("version", ""))
                except Exception as e:
                    logger.debug(f"[BundledSync] Failed to read src manifest {src_manifest}: {e}")
            elif os.path.isfile(src_skill_md):
                try:
                    with open(src_skill_md, encoding="utf-8") as f:
                        content = f.read()
                    if content.startswith("---"):
                        import yaml
                        parts = content.split("---", 2)
                        if len(parts) >= 3:
                            fm = yaml.safe_load(parts[1]) or {}
                            src_version = str(fm.get("version", ""))
                except Exception as e:
                    logger.debug(f"[BundledSync] Failed to read src SKILL.md {src_skill_md}: {e}")

            # 目标已存在：比较版本决定是否更新
            if os.path.isdir(dst_dir):
                dst_version = ""
                dst_manifest = os.path.join(dst_dir, "manifest.json")
                dst_skill_md = os.path.join(dst_dir, "SKILL.md")
                if os.path.isfile(dst_manifest):
                    try:
                        import json
                        with open(dst_manifest, encoding="utf-8") as f:
                            dst_version = str(json.load(f).get("version", ""))
                    except Exception:
                        logger.warning(
                            f"[BundledSync] 目标 manifest 版本读取失败（将保守跳过更新）: {dst_manifest}",
                            exc_info=True,
                        )
                elif os.path.isfile(dst_skill_md):
                    try:
                        with open(dst_skill_md, encoding="utf-8") as f:
                            content = f.read()
                        if content.startswith("---"):
                            import yaml
                            parts = content.split("---", 2)
                            if len(parts) >= 3:
                                fm = yaml.safe_load(parts[1]) or {}
                                dst_version = str(fm.get("version", ""))
                    except Exception:
                        logger.warning(
                            f"[BundledSync] 目标 SKILL.md 版本解析失败（将保守跳过更新）: {dst_skill_md}",
                            exc_info=True,
                        )

                if dst_version and src_version:
                    if dst_version == src_version:
                        # 版本相同，跳过（保留用户改动与 data/ 子目录）
                        continue
                    # 两侧版本均可读且不一致 → 继续走更新流程
                else:
                    # 版本不可比较但目标已存在：保守跳过，避免盲目覆盖用户改动
                    continue

                # 版本不同：先备份旧目录（含用户 data/），再覆盖
                logger.info(
                    f"[BundledSync] Updating {label}/{entry}: "
                    f"v{dst_version} -> v{src_version}"
                )
                # 保留用户的 data/ 子目录
                user_data_dir = os.path.join(dst_dir, "data")
                temp_data_dir = None
                if os.path.isdir(user_data_dir):
                    temp_data_dir = os.path.join(dst_root, f".{entry}.data.tmp")
                    if os.path.isdir(temp_data_dir):
                        shutil.rmtree(temp_data_dir)
                    shutil.move(user_data_dir, temp_data_dir)

                try:
                    shutil.rmtree(dst_dir, ignore_errors=True)
                    shutil.copytree(src_dir, dst_dir)
                finally:
                    # 无论复制成功与否，只要 data 已被移出就恢复回去，避免用户数据丢失
                    if temp_data_dir and os.path.isdir(temp_data_dir):
                        dst_data_dir = os.path.join(dst_dir, "data")
                        # copytree 失败时 dst_dir 可能不存在，确保父目录存在以放回用户数据
                        os.makedirs(dst_dir, exist_ok=True)
                        if os.path.isdir(dst_data_dir):
                            shutil.rmtree(dst_data_dir, ignore_errors=True)
                        shutil.move(temp_data_dir, dst_data_dir)
            else:
                # 首次复制
                logger.info(f"[BundledSync] Copying builtin {label}/{entry} v{src_version}")
                shutil.copytree(src_dir, dst_dir)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"[LuomiNest] Starting application...")
    logger.info(f"[LuomiNest] Environment: {'Development' if settings.DEBUG else 'Production'}")

    # 系统信息日志（操作系统 / 发行版 / 包管理器 / 架构）
    try:
        from app.core.platform_info import log_system_info

        log_system_info()
    except Exception as e:
        logger.debug(f"[LuomiNest] System info logging failed: {e}")

    # 硬件检测日志
    try:
        profile = get_hardware_profile()
        logger.info(
            f"[LuomiNest] 硬件概况: CPU={profile.cpu_count}核, "
            f"内存={profile.total_memory_gb:.1f}GB, "
            f"GPU={profile.gpu_type.value}"
        )
        if profile.is_low_end:
            logger.warning("=" * 60)
            logger.warning(f"  ⚠ 系统资源不足")
            logger.warning(f"  CPU: {profile.cpu_count} 核 | 内存: {profile.total_memory_gb:.1f} GB")
            logger.warning(f"  LuomiNest 需要至少 4 核 CPU + 8 GB 内存以保证稳定运行。")
            logger.warning(f"  当前配置下可能出现响应缓慢、功能受限等问题。")
            logger.warning(f"  建议升级硬件后重试。")
            logger.warning("=" * 60)
    except Exception as e:
        logger.warning(f"[LuomiNest] Hardware detection failed: {e}")

    # JWT 模式：启动时预加载密钥，密钥不可用则 fail-fast 阻止启动
    if settings.AUTH_MODE == "jwt":
        try:
            from app.security.auth.jwt_handler import ensure_jwt_secret
            ensure_jwt_secret()
            logger.success("[LuomiNest] JWT secret prewarmed successfully")
        except RuntimeError as e:
            logger.error(f"[LuomiNest] JWT secret unavailable, cannot start in jwt mode: {e}")
            raise

    # 初始化 SQLite 数据库（核心依赖，必须在任何 store 操作前完成）
    # 失败直接 raise 让进程退出，避免"能访问但功能全坏"的半死状态
    from app.infrastructure.database import init_db
    await init_db()
    logger.success("[LuomiNest] Database initialized")

    # 存储位置日志（开发/生产区分：dev=backend/data，打包=userData/Data/backend）
    logger.info(
        f"[LuomiNest] 存储位置: 模式={'打包生产(PyInstaller)' if settings.IS_FROZEN else '开发(源码)'}, "
        f"DATA_DIR={settings.DATA_DIR}, DB={settings.DATABASE_URL}"
    )
    logger.info(
        f"[LuomiNest] 存储位置: UPLOAD_DIR={settings.UPLOAD_DIR}, AVATAR_DIR={settings.AVATAR_DIR}, "
        f"PLUGIN_DIR={settings.PLUGIN_DIR}, SKILL_DIR={settings.SKILL_DIR}"
    )

    # JSON → SQLite 幂等迁移（已迁移则跳过，旧文件不删除）
    try:
        from app.infrastructure.database.migration import migrate_all_json_to_sqlite
        migration_results = await migrate_all_json_to_sqlite()
        migrated_total = sum(v for v in migration_results.values() if v > 0)
        if migrated_total > 0:
            logger.success(f"[LuomiNest] Migrated {migrated_total} records from JSON to SQLite: {migration_results}")
    except Exception as e:
        logger.warning(f"[LuomiNest] JSON→SQLite migration skipped: {e}", exc_info=True)

    # 加载持久化平台实例到 registry（替代 platform.py 的 import-time 调用，须在 init_db 之后）
    try:
        from app.api.v1.endpoints.platform import _load_persisted_instances
        _load_persisted_instances()
        logger.info("[LuomiNest] Platform instances loaded from DB")
    except Exception as e:
        logger.warning(f"[LuomiNest] Platform instances load skipped: {e}", exc_info=True)

    # 初始化默认 repo sources（替代 repo_source.py 的 import-time 调用，须在 init_db 之后）
    try:
        from app.api.v1.endpoints.repo_source import _ensure_defaults
        _ensure_defaults()
        logger.info("[LuomiNest] Repo sources defaults ensured")
    except Exception as e:
        logger.warning(f"[LuomiNest] Repo sources init skipped: {e}", exc_info=True)

    # 懒加载 LLM providers（替代 adapter.py 的 import-time 加载，解耦模块加载与 DB init）
    try:
        from app.runtime.provider.llm.adapter import llm_adapter
        llm_adapter.ensure_providers_loaded()
    except Exception as e:
        logger.error(f"[LuomiNest] LLM providers load failed (critical): {e}", exc_info=True)
        raise

    # 应用 model_config 到运行时（替代 model.py 的 import-time 调用；
    # 须在 ensure_providers_loaded() 之后，以保证 model_config.default_provider 覆盖 provider is_default）
    try:
        from app.api.v1.endpoints.model import apply_model_config_from_db
        apply_model_config_from_db()
    except Exception as e:
        logger.warning(f"[LuomiNest] Model config apply skipped: {e}", exc_info=True)

    try:
        from app.engines.memory import init_memory
        await init_memory()
    except Exception as e:
        logger.warning(f"[LuomiNest] Memory engine init skipped: {e}", exc_info=True)

    # 注册内置工具
    try:
        from app.core.tools import tool_registry
        from app.core.tools.builtin import (
            CliTool, ReadFileTool, WriteFileTool, ListFilesTool, SearchFilesTool,
            McpTool, ListMcpServersTool, DelegateToSubagentTool,
            CreateScheduledTaskTool, ListScheduledTasksTool,
            GetScheduledTaskTool, DeleteScheduledTaskTool,
            CreateBrowserTabTool,
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
        tool_registry.register(ListScheduledTasksTool())
        tool_registry.register(GetScheduledTaskTool())
        tool_registry.register(DeleteScheduledTaskTool())
        tool_registry.register(CreateBrowserTabTool())

        # 浏览器自动化工具集（25 个，通过 WS 调用前端 Electron 执行）
        from app.core.tools.builtin.browser_automation import get_luominest_browser_automation_tools
        for _browser_tool in get_luominest_browser_automation_tools():
            tool_registry.register(_browser_tool)

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

        # 技能工具：list/read/use（洋葱架构 §11.2 / B10，各场景通用）
        from app.core.tools.builtin.skills_tools import get_luominest_skills_tools
        for _skill_tool in get_luominest_skills_tools():
            tool_registry.register(_skill_tool)

        # 工具发现 meta-tool（L1 主动发现，tier=meta，对齐 tool-opt §4.2.1）
        from app.core.tools.builtin.tools_meta import (
            ListLuomiNestToolsTool,
            ReadLuomiNestToolTool,
        )
        tool_registry.register(ListLuomiNestToolsTool())
        tool_registry.register(ReadLuomiNestToolTool())

        # 文件搜索工具（tier=domain, platform=win，Everything/OsWalk 适配器，对齐 tool-opt §4.5 T6）
        from app.core.tools.builtin.search_everything_tool import SearchEverythingTool
        tool_registry.register(SearchEverythingTool())

        # 应用启动工具（tier=domain，全平台，对齐 tool-opt §4.6 T7）
        from app.core.tools.builtin.launch_tool import LaunchApplicationTool
        tool_registry.register(LaunchApplicationTool())

        # 上下文压缩工具（tier=core，对齐 tool-opt §4.3 T4）
        from app.core.tools.builtin.context_tools import CompressContextTool
        tool_registry.register(CompressContextTool())

        logger.info(f"[LuomiNest] Registered {len(tool_registry.list_names())} tools: {', '.join(tool_registry.list_names())}")
    except Exception as e:
        logger.error(f"[LuomiNest] Tool registration failed (critical): {e}", exc_info=True)
        raise

    # 注册工作流内部模块接口
    try:
        from app.core.workflow.register_tools import register_internal_tools
        await register_internal_tools()
    except Exception as e:
        logger.warning(f"[LuomiNest] Workflow internal tools registration skipped: {e}", exc_info=True)

    # 装配工作流引擎依赖（组合根注入，替代引擎内部延迟 import；未注入时引擎保留兜底）
    try:
        from app.core.workflow.engine import configure_engine
        from app.core.container import container
        configure_engine(
            chat_service_cls=container.chat_service.__class__,
            conversation_store=container.conversation_store,
            llm_adapter=container.llm_adapter,
        )
        logger.info("[LuomiNest] Workflow engine dependencies configured")

        # 清理陈旧的非终态工作流会话（服务重启后，内存中的工作流已丢失）
        from app.services.workflow_persistence import cleanup_stale_sessions
        stale_count = await cleanup_stale_sessions()
        if stale_count:
            logger.info(f"[LuomiNest] Cleaned up {stale_count} stale workflow sessions")
    except Exception as e:
        logger.warning(f"[LuomiNest] Workflow engine configure skipped: {e}", exc_info=True)

    # 加载 CxPlugin 插件系统
    try:
        from app.runtime.plugin.cxplugin import init_hot_reload
        from app.runtime.plugin.cxplugin.loader import luominest_plugin_loader
        from app.services.plugin_service import luominest_plugin_service
        # 打包模式下首次启动：将 _internal/{plugins,skills}/ 复制到可写的 DATA_DIR 下
        # 让用户安装/启用的内置插件可被运行时找到（dev 模式直接从源码目录加载，无需复制）
        _sync_bundled_plugin_resources()
        plugin_count = await luominest_plugin_service.initialize()
        # 将已加载插件注册的 API 路由挂载到 app（/api/v1/plugins/{plugin_id}/{path}）
        # 同时缓存 app 引用，供后续 install_local_builtin_plugin 动态挂载新插件路由
        applied_routes = luominest_plugin_loader.apply_routes_to_app(app)
        logger.info(
            f"[LuomiNest] Loaded {plugin_count} CxPlugin(s), applied {applied_routes} API route(s)"
        )
        init_hot_reload()
    except Exception as e:
        logger.warning(f"[LuomiNest] CxPlugin loading skipped: {e}", exc_info=True)

    # 初始化 CxSkill 技能系统（在 CxPlugin 之后，确保 plugin 类型条目已被 loader 跳过）
    try:
        from app.services.skill_service import luominest_skill_service
        skill_count = await luominest_skill_service.init()
        logger.info(f"[LuomiNest] Loaded {skill_count} CxSkill(s)")
    except Exception as e:
        logger.warning(f"[LuomiNest] CxSkill loading skipped: {e}", exc_info=True)

    # 启动定时任务调度器（APScheduler）
    try:
        from app.core.scheduler import luominest_scheduler
        # 注入任务载荷执行器（组合根装配；未注入时调度器经 subagent_delegation 端口兜底）
        from app.core.container import container
        luominest_scheduler.register_task_executor(container.subagent_executor)
        await luominest_scheduler.init()
        logger.info(f"[LuomiNest] Scheduler started, tasks: {len(luominest_scheduler.list_tasks())}")
    except Exception as e:
        logger.warning(f"[LuomiNest] Scheduler init skipped: {e}", exc_info=True)

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
        logger.warning(f"[LuomiNest] MCP manager init skipped: {e}", exc_info=True)

    # 启动平台消息路由器（QQ/微信/Minecraft/游戏等）
    try:
        from app.services.platform_router import attach_router_to_instances
        attach_router_to_instances()
        logger.info(f"[LuomiNest] Platform router attached to instances")
    except Exception as e:
        logger.warning(f"[LuomiNest] Platform router init skipped: {e}", exc_info=True)

    # 初始化 Avatar Manifest Manager（多模型清单系统，P0 基础）
    # 必须在 chat_service 调用 get_avatar_binding 之前完成（chat_service 使用同步回退）
    try:
        from app.services.avatar_manifest import avatar_manifest_manager
        await avatar_manifest_manager.init()
        logger.info(f"[LuomiNest] Avatar manifest manager initialized")
    except Exception as e:
        logger.warning(f"[LuomiNest] Avatar manifest init skipped: {e}", exc_info=True)

    # 启动时清理临时文件
    try:
        from app.services.cleanup_service import luominest_cleanup_service
        temp_cleaned = luominest_cleanup_service.cleanup_temp_files()
        if temp_cleaned > 0:
            logger.info(f"[LuomiNest] Cleaned {temp_cleaned} temp files on startup")
    except Exception as e:
        logger.warning(f"[LuomiNest] Startup cleanup skipped: {e}", exc_info=True)

    # 注册定时清理任务（每24小时执行一次）
    try:
        from apscheduler.triggers.interval import IntervalTrigger
        from app.services.cleanup_service import luominest_cleanup_service

        async def _periodic_cleanup():
            try:
                await luominest_cleanup_service.run_all_async()
            except Exception as cleanup_err:
                logger.warning(f"[LuomiNest] Periodic cleanup failed: {cleanup_err}")

        if luominest_scheduler.add_job(
            _periodic_cleanup,
            trigger=IntervalTrigger(hours=24),
            id="lumi_periodic_cleanup",
            replace_existing=True,
        ):
            logger.info(f"[LuomiNest] Periodic cleanup job registered (every 24h)")
    except Exception as e:
        logger.warning(f"[LuomiNest] Periodic cleanup registration skipped: {e}", exc_info=True)

    # 注册定时数据备份任务（可经 BACKUP_ENABLED / BACKUP_INTERVAL_HOURS 配置）
    if settings.BACKUP_ENABLED:
        try:
            from apscheduler.triggers.interval import IntervalTrigger
            from app.infrastructure.backup.backup_manager import luominest_backup_manager

            async def _periodic_backup():
                try:
                    path = await luominest_backup_manager.create_backup_async(label="scheduled")
                    if path:
                        logger.info(f"[LuomiNest] Scheduled backup created: {path}")
                except Exception as backup_err:
                    logger.warning(f"[LuomiNest] Scheduled backup failed: {backup_err}", exc_info=True)

            if luominest_scheduler.add_job(
                _periodic_backup,
                trigger=IntervalTrigger(hours=settings.BACKUP_INTERVAL_HOURS),
                id="lumi_periodic_backup",
                replace_existing=True,
            ):
                logger.info(
                    f"[LuomiNest] Periodic backup job registered "
                    f"(every {settings.BACKUP_INTERVAL_HOURS}h, keep last {luominest_backup_manager.MAX_BACKUPS})"
                )
        except Exception as e:
            logger.warning(f"[LuomiNest] Periodic backup registration skipped: {e}", exc_info=True)

    yield

    # 停止 CxPlugin 热重载监听
    try:
        from app.runtime.plugin.cxplugin import shutdown_hot_reload
        await shutdown_hot_reload()
        logger.info(f"[LuomiNest] CxPlugin hot reload stopped")
    except Exception as e:
        logger.warning(f"[LuomiNest] CxPlugin shutdown skipped: {e}", exc_info=True)

    # 停止所有平台实例
    try:
        from app.runtime.platform.registry import stop_all_instances
        await stop_all_instances()
        logger.info(f"[LuomiNest] Platform instances stopped")
    except Exception as e:
        logger.warning(f"[LuomiNest] Platform shutdown skipped: {e}", exc_info=True)

    # 断开所有 MCP 连接
    try:
        from app.core.tools.mcp.manager import mcp_manager
        await mcp_manager.disconnect_all()
        logger.info(f"[LuomiNest] MCP connections closed")
    except Exception as e:
        logger.warning(f"[LuomiNest] MCP shutdown skipped: {e}", exc_info=True)

    # 关闭定时任务调度器
    try:
        from app.core.scheduler import luominest_scheduler
        await luominest_scheduler.shutdown()
        logger.info(f"[LuomiNest] Scheduler stopped")
    except Exception as e:
        logger.warning(f"[LuomiNest] Scheduler shutdown skipped: {e}", exc_info=True)

    try:
        from app.engines.memory import shutdown_memory
        await shutdown_memory()
    except Exception as e:
        logger.warning(f"[LuomiNest] Memory engine shutdown skipped: {e}", exc_info=True)

    # 关闭 LLM provider httpx 客户端
    try:
        from app.runtime.provider.llm.adapter import llm_adapter
        await llm_adapter.aclose()
    except Exception as e:
        logger.warning(f"[LuomiNest] LLM adapter close skipped: {e}", exc_info=True)

    # 关闭浏览器自动化 WS 管理器
    try:
        from app.api.ws import browser_ws_manager
        await browser_ws_manager.shutdown()
        logger.info(f"[LuomiNest] Browser WS manager closed")
    except Exception as e:
        logger.warning(f"[LuomiNest] Browser WS shutdown skipped: {e}", exc_info=True)

    # 关闭数据库引擎
    try:
        from app.infrastructure.database import dispose_db
        await dispose_db()
    except Exception as e:
        logger.warning(f"[LuomiNest] Database dispose skipped: {e}", exc_info=True)

    logger.info(f"[LuomiNest] Shutting down application...")


def create_app() -> FastAPI:
    logger.info("[AppFactory] Creating FastAPI application...")

    # API 文档在 DEBUG 模式或显式启用 API_DOCS_ENABLED 时暴露
    _docs_enabled = settings.DEBUG or settings.API_DOCS_ENABLED

    app = FastAPI(
        title="LuomiNest API",
        description="LuomiNest - AI Agent Platform Backend API",
        version=settings.APP_VERSION,
        docs_url="/docs" if _docs_enabled else None,
        redoc_url="/redoc" if _docs_enabled else None,
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

    no_auth = os.environ.get("LUOMINEST_NO_AUTH", "").strip().lower() in ("1", "true", "yes")

    # 始终确保有认证 token — 即使在 NOAUTH / dev 模式下也自动生成，
    # 防止 API 完全无认证暴露到网络上
    auth_token = load_auth_token()
    if not auth_token:
        from app.security.auth.local_token import generate_and_save_token
        auth_token = generate_and_save_token(settings.DATA_DIR)
        if no_auth:
            logger.info("[AppFactory] LUOMINEST_NO_AUTH 模式: 已自动生成认证 token（不再完全无认证）")
        else:
            logger.info("[AppFactory] 未找到 auth token，已自动生成（dev mode）")

    if no_auth:
        logger.warning("[AppFactory] LUOMINEST_NO_AUTH 已设置 — 仍启用认证中间件以保障安全")

    if auth_token:
        logger.success("[AppFactory] Auth token ready, API routes protected")

    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        return await luomi_auth_middleware(request, call_next)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID",
                        "X-LuomiNest-Internal-Token", "X-LuomiNest-Owner-User-Id"],
    )

    @app.exception_handler(LuomiNestError)
    async def lumi_error_handler(request: Request, exc: LuomiNestError):
        logger.error(f"[Exception] LuomiNestError: {exc.message} (code={exc.code})")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": 1,
                "message": exc.message,
                "error": {"code": exc.code, "message": exc.message},
                "data": None,
            },
        )

    # FastAPI 原生 HTTPException（含 StarletteHTTPException 子类）统一转规范信封，
    # 消除 {"detail"} 裸响应 —— 全库 49 处 raise HTTPException 因此纳入错误码体系
    from starlette.exceptions import HTTPException as StarletteHTTPException

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail or "请求处理失败")
        err_code = f"HTTP_{exc.status_code}"
        logger.warning(f"[Exception] HTTPException: {detail} (status={exc.status_code}, path={request.url.path})")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": 1,
                "message": detail,
                "error": {"code": err_code, "message": detail},
                "data": None,
            },
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception):
        logger.error(f"[Exception] Unhandled exception: {exc}")
        # 生产环境不泄露内部异常细节（路径/SQL/堆栈），仅开发环境返回详情辅助调试
        message = str(exc) if settings.DEBUG else "服务器内部错误，请查看后端日志"
        return JSONResponse(
            status_code=500,
            content={
                "code": 1,
                "message": message,
                "error": {"code": "INTERNAL_ERROR", "message": message},
                "data": None,
            },
        )

    # --- 速率限制（slowapi） ---
    from slowapi.errors import RateLimitExceeded
    from app.security.rate_limiter import limiter, rate_limit_exceeded_handler

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)  # type: ignore[arg-type]

    app.include_router(api_router, prefix="/api/v1")
    app.include_router(attachment_router, prefix="/api")

    # 浏览器自动化 WebSocket 端点（前端 Electron Main 常驻连接）
    from app.api.ws import ws_router
    app.include_router(ws_router, prefix="/ws")

    @app.get("/health")
    async def health_check():
        return {"status": "ok", "service": "LuomiNest"}

    @app.get("/")
    async def root():
        return {
            "name": "LuomiNest",
            "version": settings.APP_VERSION,
            "docs": "/docs" if _docs_enabled else "disabled",
        }

    logger.success("[AppFactory] FastAPI application created successfully")
    return app
