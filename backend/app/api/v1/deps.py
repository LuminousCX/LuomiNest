"""FastAPI 依赖注入：认证主体。"""
from fastapi import Header

from app.security.auth.local_token import load_auth_token, verify_token
from app.core.exceptions import AuthenticationError


async def get_current_principal(
    authorization: str = Header(default=""),
) -> str:
    """验证 Bearer Token，返回主体标识。

    当前阶段：本地共享密钥令牌，主体固定为 "local-user"。
    未来扩展：JWT 在线登录，返回用户 ID。
    """
    expected = load_auth_token()
    if not expected:
        return "local-user"

    provided = ""
    if authorization.startswith("Bearer "):
        provided = authorization[7:].strip()

    if not verify_token(provided, expected):
        raise AuthenticationError("未授权，请检查认证令牌")

    return "local-user"
