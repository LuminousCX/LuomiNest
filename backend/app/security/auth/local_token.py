"""本地共享密钥令牌管理。

生成、加载、验证本地认证令牌。
参考 TencentDB Gateway 的 Bearer Token + 常量时间比较模式。
"""
import os
import secrets
import stat
from pathlib import Path

from loguru import logger

TOKEN_FILE_NAME = "auth_token"
TOKEN_ENV_VAR = "LUOMINEST_AUTH_TOKEN"


def get_token_path(data_dir: str) -> Path:
    """返回认证令牌持久化文件路径。"""
    return Path(data_dir) / "config" / TOKEN_FILE_NAME


def load_auth_token() -> str | None:
    """加载认证令牌。

    优先级：环境变量 LUOMINEST_AUTH_TOKEN > 文件 data/config/auth_token。
    两者都无时返回 None（无认证模式，仅开发场景）。
    """
    env_token = os.environ.get(TOKEN_ENV_VAR, "").strip()
    if env_token:
        return env_token

    from app.core.config import settings
    token_path = get_token_path(settings.DATA_DIR)
    if token_path.exists():
        existing = token_path.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    return None


def generate_and_save_token(data_dir: str) -> str:
    """生成随机令牌并持久化到文件。"""
    token = secrets.token_urlsafe(32)
    token_path = get_token_path(data_dir)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(token, encoding="utf-8")
    try:
        os.chmod(token_path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError as exc:
        logger.warning(
            f"[Auth] Failed to set secure permissions on token file {token_path}: {exc}"
        )
    logger.success(f"[Auth] Generated local auth token at {token_path}")
    return token


def verify_token(provided: str | None, expected: str) -> bool:
    """常量时间比较令牌，避免时序侧信道。"""
    if not provided or not expected:
        return False
    return secrets.compare_digest(provided, expected)
