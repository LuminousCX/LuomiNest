import argparse
import asyncio
import sys
from pathlib import Path
from loguru import logger

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
    setup_logging()
    
    logger.info(f"LuomiNest Backend starting on {args.host}:{args.port}")
    
    try:
        import uvicorn
        from app.core.app_factory import create_app
        
        app = create_app()
        
        @app.get("/health")
        async def health_check():
            return {"status": "ok", "service": "luominest-backend"}
        
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            log_level="debug" if args.debug else "info",
            access_log=args.debug
        )
    except ImportError as e:
        logger.error(f"Failed to import dependencies: {e}")
        logger.info("Running in minimal mode...")
        
        from http.server import HTTPServer, BaseHTTPRequestHandler
        import json
        
        class MinimalHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/health":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "ok", "mode": "minimal"}).encode())
                else:
                    self.send_response(404)
                    self.end_headers()
            
            def log_message(self, format, *args):
                logger.info(f"HTTP: {args[0]}")
        
        server = HTTPServer((args.host, args.port), MinimalHandler)
        logger.info(f"Minimal server running on http://{args.host}:{args.port}")
        server.serve_forever()
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
