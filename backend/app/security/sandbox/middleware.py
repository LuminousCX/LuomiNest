"""沙盒中间件 — 在 FastAPI 请求上下文中管理沙盒生命周期。

提供：
  - SandboxMiddleware: ASGI 中间件，自动为请求注入沙盒实例。
  - get_sandbox: FastAPI 依赖注入函数，获取当前请求的沙盒。
"""

import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.security.sandbox.local_sandbox import LocalSandbox
from app.security.sandbox.sandbox_provider import SandboxProvider

logger = logging.getLogger(__name__)

# 请求头中提取 session_id 的字段名
_SESSION_HEADER = "X-Session-ID"
# 备用：查询参数名
_SESSION_QUERY_PARAM = "session_id"


class SandboxMiddleware(BaseHTTPMiddleware):
    """FastAPI 中间件：在请求上下文中管理沙盒生命周期。

    流程：
      1. 从请求头或查询参数中提取 session_id。
      2. 通过 SandboxProvider 获取（或创建）对应的沙盒实例。
      3. 将沙盒存入 request.state.sandbox，供后续依赖注入使用。
      4. 执行请求。
      5. 请求完成后不立即释放沙盒（由 Provider LRU 策略管理）。
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # 提取 session_id
        session_id = self._extract_session_id(request)

        if session_id:
            try:
                provider = SandboxProvider.get_instance()
                sandbox = provider.acquire(session_id)
                request.state.sandbox = sandbox
                request.state.session_id = session_id
                logger.debug(f"请求 {request.method} {request.url.path} 绑定沙盒 session='{session_id}'")
            except Exception as e:
                logger.warning(f"沙盒获取失败 session='{session_id}': {e}")
                request.state.sandbox = None
                request.state.session_id = None
        else:
            request.state.sandbox = None
            request.state.session_id = None

        response = await call_next(request)
        return response

    @staticmethod
    def _extract_session_id(request: Request) -> str | None:
        """从请求中提取 session_id。

        优先级：请求头 X-Session-ID > 查询参数 session_id
        """
        # 1. 请求头
        session_id = request.headers.get(_SESSION_HEADER)
        if session_id:
            return session_id.strip()

        # 2. 查询参数
        session_id = request.query_params.get(_SESSION_QUERY_PARAM)
        if session_id:
            return session_id.strip()

        return None


async def get_sandbox(request: Request) -> LocalSandbox:
    """FastAPI 依赖注入：获取当前请求的沙盒实例。

    用法::

        @router.post("/execute")
        async def execute(sandbox: LocalSandbox = Depends(get_sandbox)):
            result = await sandbox.execute_command("ls -la")
            ...

    Args:
        request: FastAPI 请求对象（自动注入）。

    Returns:
        LocalSandbox 实例。

    Raises:
        RuntimeError: 如果沙盒未在当前请求上下文中初始化。
    """
    sandbox = getattr(request.state, "sandbox", None)
    if sandbox is None:
        # 尝试从 session_id 懒加载
        session_id = getattr(request.state, "session_id", None)
        if session_id is None:
            session_id = SandboxMiddleware._extract_session_id(request)

        if session_id:
            provider = SandboxProvider.get_instance()
            sandbox = provider.acquire(session_id)
            request.state.sandbox = sandbox
            return sandbox  # type: ignore[return-value]

        raise RuntimeError(
            "沙盒未初始化。请确保请求包含 X-Session-ID 头或 session_id 查询参数，"
            "且 SandboxMiddleware 已注册到 FastAPI 应用。"
        )
    return sandbox  # type: ignore[return-value]


async def get_optional_sandbox(request: Request) -> LocalSandbox | None:
    """FastAPI 依赖注入：获取当前请求的沙盒实例（可选）。

    与 get_sandbox 不同，当沙盒不可用时返回 None 而非抛出异常。

    Args:
        request: FastAPI 请求对象。

    Returns:
        LocalSandbox 实例或 None。
    """
    try:
        return await get_sandbox(request)
    except RuntimeError:
        return None
