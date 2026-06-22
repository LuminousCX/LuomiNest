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

def setup_logging():
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="DEBUG" if "--debug" in sys.argv else "INFO"
    )

def parse_args():
    parser = argparse.ArgumentParser(description="LuomiNest Backend Server")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind")
    parser.add_argument("--port", type=int, default=18000, help="Port to bind")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    return parser.parse_args()

def main():
    args = parse_args()
    setup_console_encoding()
    setup_logging()

    # Use the default ProactorEventLoop on Windows. The SelectorEventLoop breaks
    # edge_tts (aiohttp WebSocket + SSL) — no audio is received from the service.
    # ProactorEventLoop supports subprocess, SSL, and pipes on Python 3.8+.

    logger.info(f"LuomiNest Backend starting on {args.host}:{args.port}")

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
            host=args.host,
            port=args.port,
            log_level="debug" if args.debug else "info",
            access_log=args.debug
        )
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
