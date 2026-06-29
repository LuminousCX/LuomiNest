"""SECRET_KEY 持久化管理。

确保 SECRET_KEY 在重启后保持不变，使 AES 加密数据可跨会话解密。
首次启动时生成 Fernet 兼容的随机密钥并写入文件（0600 权限），
后续启动直接读取。
"""
import os
import stat
from pathlib import Path

from cryptography.fernet import Fernet
from loguru import logger

DEFAULT_PLACEHOLDER = "change-me-in-production"
SECRET_KEY_FILE_NAME = "secret_key"


def get_secret_key_path(data_dir: str) -> Path:
    """返回 SECRET_KEY 持久化文件路径。"""
    return Path(data_dir) / "config" / SECRET_KEY_FILE_NAME


def load_or_create_secret_key(data_dir: str) -> str:
    """加载或生成持久化 SECRET_KEY。

    - 文件存在且非空：读取返回
    - 不存在或为空：生成 Fernet key，写入文件（0600），返回
    """
    key_path = get_secret_key_path(data_dir)
    key_path.parent.mkdir(parents=True, exist_ok=True)

    if key_path.exists():
        existing = key_path.read_text(encoding="utf-8").strip()
        if existing:
            return existing

    new_key = Fernet.generate_key().decode("utf-8")
    key_path.write_text(new_key, encoding="utf-8")
    try:
        os.chmod(key_path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        # Windows 上 chmod 语义不同，best-effort
        pass

    logger.success(f"[SecretKey] Generated persistent SECRET_KEY at {key_path}")
    return new_key


def is_placeholder(secret_key: str | None) -> bool:
    """判断 SECRET_KEY 是否为空或占位符。"""
    return not secret_key or secret_key == DEFAULT_PLACEHOLDER
