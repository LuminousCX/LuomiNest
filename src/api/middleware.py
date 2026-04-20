"""FastAPI 中间件。

提供全局异常捕获、接口日志、请求追踪等中间件功能。
"""

from __future__ import annotations

import time
import uuid
from typing import AsyncGenerator, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from src.exceptions import AppException
from src.exceptions import ErrorCode
from src.utils.logger import get_logger, set_trace_id, set_user_id

logger = get_logger()


class ExceptionMiddleware(BaseHTTPMiddleware):
    """全局异常捕获中间件。

    捕获所有未处理的异常，转换为统一的 API 响应格式。
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        try:
            return await call_next(request)
        except AppException as e:
            logger.warning(f"业务异常: {e}")
            return JSONResponse(
                status_code=400,
                content={
                    "code": e.code.value,
                    "message": e.message,
                    "detail": e.detail,
                },
            )
        except Exception as e:
            logger.error(f"未处理异常: {e}", exc_info=True)
            from src.config.settings import get_settings
            show_detail = get_settings().debug
            return JSONResponse(
                status_code=500,
                content={
                    "code": ErrorCode.INTERNAL_ERROR.value,
                    "message": "服务器内部错误",
                    "detail": str(e) if show_detail else None,
                },
            )


class LoggingMiddleware(BaseHTTPMiddleware):
    """接口日志中间件。

    记录每个请求的方法、路径、耗时、状态码。
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        trace_id = request.headers.get("X-Trace-ID", uuid.uuid4().hex[:16])
        set_trace_id(trace_id)

        user_id = request.headers.get("X-User-ID", "")
        set_user_id(user_id)

        start_time = time.time()

        method = request.method
        path = request.url.path

        logger.info(f"请求开始: {method} {path}")

        response = await call_next(request)

        duration_ms = int((time.time() - start_time) * 1000)
        status_code = response.status_code

        logger.info(
            f"请求完成: {method} {path} | 状态码: {status_code} | 耗时: {duration_ms}ms"
        )

        response.headers["X-Trace-ID"] = trace_id
        return response
