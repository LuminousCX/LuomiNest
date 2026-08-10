"""LuomiNest JWT 认证模块。

提供 JWT Access Token / Refresh Token 的签发与校验。
算法: HS256，签名密钥从 Settings.JWT_SECRET_KEY 读取。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import Enum

from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError, JWSSignatureError
from loguru import logger

from app.core.config import settings
from app.security.crypto.secret_key_manager import (
    JWT_SECRET_KEY_FILE_NAME,
    load_or_create_secret_key,
)


# ── 异常 ─────────────────────────────────────────────────────────────────────

class TokenErrorKind(str, Enum):
    """令牌错误分类。"""

    EXPIRED = "expired"
    INVALID_SIGNATURE = "invalid_signature"
    MALFORMED = "malformed"


class TokenError(Exception):
    """JWT 验证失败时抛出的异常。"""

    def __init__(self, kind: TokenErrorKind, message: str = "") -> None:
        self.kind = kind
        self.message = message or f"Token error: {kind.value}"
        super().__init__(self.message)


# ── 内部工具 ──────────────────────────────────────────────────────────────────

def _ensure_jwt_secret() -> str:
    """获取 JWT 签名密钥，若未配置则从持久化存储加载或生成。

    与 SECRET_KEY 一致采用机器指纹绑定加密存储（``data/config/jwt_secret_key``），
    确保重启后密钥不变，已签发的 Refresh Token 在 30 天有效期内持续可用。
    显式通过环境变量 ``JWT_SECRET_KEY`` 配置时优先使用配置值。
    """
    secret = settings.JWT_SECRET_KEY
    if not secret:
        secret = load_or_create_secret_key(settings.DATA_DIR, JWT_SECRET_KEY_FILE_NAME)
        settings.JWT_SECRET_KEY = secret
        logger.success("[JWT] JWT_SECRET_KEY loaded from persistent store")
    return secret


def ensure_jwt_secret() -> None:
    """启动时预加载 JWT 密钥（fail-fast）。

    在 ``AUTH_MODE == "jwt"`` 时于应用启动阶段调用，确保密钥文件可读；
    若密钥不可用（机器指纹不匹配或文件损坏），立即抛出 RuntimeError 阻止启动，
    避免运行期以 per-request 500 形式暴露。
    """
    _ensure_jwt_secret()


# ── 签发 ──────────────────────────────────────────────────────────────────────

def create_access_token(
    user_id: str,
    device_id: str,
    roles: list[str],
    token_version: int = 1,
) -> str:
    """签发 Access Token。

    Args:
        user_id: 用户 ID。
        device_id: 设备 ID。
        roles: 用户角色列表。
        token_version: 用户当前 token_version，用于密码修改后吊销旧令牌。

    Returns:
        编码后的 JWT 字符串。
    """
    secret = _ensure_jwt_secret()
    now = datetime.now(UTC)
    expires = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": user_id,
        "device_id": device_id,
        "type": "access",
        "roles": roles,
        "exp": expires,
        "iat": now,
        "ver": token_version,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def create_refresh_token(
    user_id: str,
    device_id: str,
) -> str:
    """签发 Refresh Token。

    Args:
        user_id: 用户 ID。
        device_id: 设备 ID。

    Returns:
        编码后的 JWT 字符串。
    """
    secret = _ensure_jwt_secret()
    now = datetime.now(UTC)
    expires = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    payload = {
        "sub": user_id,
        "device_id": device_id,
        "type": "refresh",
        "exp": expires,
        "iat": now,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


# ── 验证 ──────────────────────────────────────────────────────────────────────

def verify_token(token: str) -> dict:
    """验证并解码 JWT 令牌。

    Args:
        token: 编码后的 JWT 字符串。

    Returns:
        解码后的 payload 字典。

    Raises:
        TokenError: 验证失败，包含具体错误分类。
    """
    secret = _ensure_jwt_secret()
    try:
        payload: dict = jwt.decode(token, secret, algorithms=["HS256"])
        return payload
    except ExpiredSignatureError:
        raise TokenError(TokenErrorKind.EXPIRED, "Token has expired")
    except JWSSignatureError:
        raise TokenError(TokenErrorKind.INVALID_SIGNATURE, "Invalid token signature")
    except JWTError as exc:
        raise TokenError(TokenErrorKind.MALFORMED, f"Malformed token: {exc}")
