import argparse
import asyncio
import sys
import os
from pathlib import Path
from loguru import logger

def setup_console_encoding():
    """设置控制台编码为UTF-8，解决Windows下的中文乱码问题"""
    if sys.platform == "win32":
        # 设置环境变量
        os.environ["PYTHONIOENCODING"] = "utf-8"
        
        # 设置标准输出编码
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8')
        
        # 尝试设置控制台代码页
        try:
            import ctypes
            # 设置控制台输出代码页为UTF-8 (65001)
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            # 设置控制台输入代码页为UTF-8 (65001)
            ctypes.windll.kernel32.SetConsoleCP(65001)
        except Exception as e:
            # Best-effort on Windows: if code page update fails, continue startup.
            logger.debug(f"Failed to set Windows console code page to UTF-8: {e}")

LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)


def setup_logging():
    logger.remove()
    logger.add(
        sys.stderr,
        format=LOG_FORMAT,
        level="DEBUG" if "--debug" in sys.argv else "INFO"
    )
    # 统一日志系统：文件落盘 + 5MB 轮转 + 保留 5 份。
    # 打包后 Electron 侧经 LUOMINEST_LOG_DIR 注入 userData/Logs（backend.log 与 main.log 同目录）；
    # 即使 stdio 管道转写未接住（如 Electron 先退出），后端自身也有完整落盘与分割。
    # 无该环境变量时（纯 dev 直跑）fallback 到 backend/data/logs/backend.log。
    log_dir = os.environ.get("LUOMINEST_LOG_DIR")
    if not log_dir:
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "logs")
    try:
        os.makedirs(log_dir, exist_ok=True)
        logger.add(
            os.path.join(log_dir, "backend.log"),
            format=(
                "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
                "{name}:{function}:{line} - {message}"
            ),
            rotation="5 MB",
            retention=5,
            enqueue=True,
            encoding="utf-8",
            level="INFO",
        )
    except Exception as e:
        # 文件 sink 失败不阻塞启动，stderr sink 仍在
        logger.warning(f"[LuomiNest] Failed to add file log sink at {log_dir}: {e}")

def parse_args():
    parser = argparse.ArgumentParser(description="LuomiNest Backend Server")
    # P0-2（链路 E 容器化）：host/port 默认值不在 argparse 写死，收编进 Settings
    # （env: LUOMINEST_HOST / LUOMINEST_PORT，默认 127.0.0.1:18000 与历史一致）；
    # CLI 显式传入时仍是最高优先级（桌面启动方式不变），无头容器靠 env 配置。
    parser.add_argument("--host", type=str, default=None, help="Host to bind (default: LUOMINEST_HOST env or 127.0.0.1)")
    parser.add_argument("--port", type=int, default=None, help="Port to bind (default: LUOMINEST_PORT env or 18000)")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    return parser.parse_args()

def warn_listen_exposure(host: str) -> None:
    """监听面安全告警：非 loopback 的 LAN 暴露告警 + headless loopback 提示。

    - desktop 下显式配 0.0.0.0 维持历史行为：告警不阻断（05 报告未建议 desktop 拒绝）
    - headless 下绑 loopback 打提示性告警：容器外表现为 connection refused（P0-2 症状），
      但不阻断——sidecar/集成测试等场景确实可能只在本容器内访问
    """
    os.environ["LUOMINEST_LISTEN_HOST"] = host
    from app.core.config import settings
    from app.runtime.platform.infrastructure.exposure import is_loopback_host, warn_lan_exposure
    warn_lan_exposure(host)
    if settings.DEPLOYMENT_MODE == "headless" and is_loopback_host(host):
        logger.warning(
            f"[Headless] Listening on loopback address {host} — unreachable from outside "
            f"the container. Set LUOMINEST_HOST=0.0.0.0 (or --host 0.0.0.0) to expose the API."
        )

def main():
    args = parse_args()
    setup_console_encoding()
    setup_logging()

    # host/port 优先级链：CLI --host/--port > env LUOMINEST_HOST/PORT（Settings）> 默认值
    from app.core.config import resolve_host_port
    host, port = resolve_host_port(args.host, args.port)
    warn_listen_exposure(host)

    logger.info(f"LuomiNest Backend starting on {host}:{port}")

    # Use the default ProactorEventLoop on Windows. The SelectorEventLoop breaks
    # edge_tts (aiohttp WebSocket + SSL) — no audio is received from the service.
    # ProactorEventLoop supports subprocess, SSL, and pipes on Python 3.8+.

    # 依赖缺失时直接报错退出，绝不静默降级为 minimal mode
    # （历史教训：minimal mode 会占用端口并让前端误以为后端就绪，导致所有 /api/v1/* 返回 404）
    try:
        import uvicorn
        from app.core.app_factory import create_app
    except ImportError as e:
        logger.error(
            f"[LuomiNest] Missing dependency: {e}. "
            f"Please install backend dependencies (uvicorn/fastapi) into the venv "
            f"and restart. Refusing to start in minimal mode."
        )
        sys.exit(1)

    try:
        app = create_app()
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="debug" if args.debug else "info",
            access_log=args.debug
        )
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
