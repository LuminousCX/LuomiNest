import os
import sys
from functools import lru_cache

from loguru import logger
from pydantic_settings import BaseSettings

from app.core.hardware import get_hardware_profile

from app.security.crypto.secret_key_manager import is_placeholder, load_or_create_secret_key


class Settings(BaseSettings):
    APP_NAME: str = "LuomiNest"
    APP_VERSION: str = "0.7.6"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    # 空字符串表示运行时根据 DATA_DIR 自动计算（见 get_settings）
    DATABASE_URL: str = ""
    REDIS_URL: str = "redis://localhost:6379/0"
    MQTT_BROKER_HOST: str = "localhost"
    MQTT_BROKER_PORT: int = 1883
    MQTT_USERNAME: str = ""
    MQTT_PASSWORD: str = ""

    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    LLM_DEFAULT_PROVIDER: str = "openai"
    LLM_FALLBACK_CHAIN: str = "openai,ollama"
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = ""
    ANTHROPIC_API_KEY: str = ""
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LLM_DEFAULT_MODEL: str = ""
    LLM_DEFAULT_TEMPERATURE: float = 0.7
    LLM_DEFAULT_MAX_TOKENS: int = 4096
    LLM_DEFAULT_TOP_P: float = 0.9
    LLM_MAX_CONCURRENT_REQUESTS: int = 0  # 0 表示根据硬件自动计算

    # LLM 上下文压缩配置
    LLM_COMPRESS_ENABLED: bool = False
    LLM_COMPRESSION_THRESHOLD: float = 0.82
    LLM_SUMMARY_MODEL: str = ""
    LLM_SUMMARY_PROVIDER: str = ""
    LLM_SUMMARY_MAX_TOKENS: int = 512
    LLM_CONTEXT_WINDOW_SIZE: int = 0  # 0 表示自动从 provider 获取

    LIVE2D_MODEL_PATH: str = "./models/live2d"
    VRM_MODEL_PATH: str = "./models/vrm"

    DATA_DIR: str = "./data"
    UPLOAD_DIR: str = "./data/uploads"
    AVATAR_DIR: str = "./data/avatars"
    PLUGIN_DIR: str = "./plugins"
    SKILL_DIR: str = "./skills"

    GITHUB_TOKEN: str = ""
    EXTERNAL_PARSE_API_URL: str = ""
    FILE_MAX_SIZE: int = 100 * 1024 * 1024

    TTS_PROXY: str = ""

    # Agent 集群调用配置
    APP_SELF_BASE_URL: str = "http://localhost:8000"
    A2A_SERVERS: list[dict] = []  # 每项: {name, url, enabled, api_key}
    A2A_TIMEOUT_SECONDS: int = 60
    A2A_MAX_DEPTH: int = 3

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    s = Settings()

    # 将 DATA_DIR 解析为绝对路径（PyInstaller 兼容）
    # frozen 模式下相对路径以 exe 所在目录为基准，避免工作目录不可控
    if getattr(sys, "frozen", False) and not os.path.isabs(s.DATA_DIR):
        s.DATA_DIR = os.path.join(os.path.dirname(sys.executable), s.DATA_DIR)
    s.DATA_DIR = os.path.abspath(s.DATA_DIR)
    os.makedirs(s.DATA_DIR, exist_ok=True)

    # 若未显式配置 DATABASE_URL，则基于 DATA_DIR 自动生成 SQLite 路径
    if not s.DATABASE_URL:
        db_path = os.path.join(s.DATA_DIR, "luominest.db")
        # Windows 反斜杠转换为正斜杠以兼容 SQLAlchemy URL 解析
        s.DATABASE_URL = f"sqlite+aiosqlite:///{db_path.replace(os.sep, '/')}"

    # LLM_MAX_CONCURRENT_REQUESTS: 0 表示自动计算
    if s.LLM_MAX_CONCURRENT_REQUESTS <= 0:
        profile = get_hardware_profile()
        s.LLM_MAX_CONCURRENT_REQUESTS = max(2, profile.cpu_count // 2)
        logger.info(f"[Config] LLM_MAX_CONCURRENT_REQUESTS auto-tuned to {s.LLM_MAX_CONCURRENT_REQUESTS} (CPU={profile.cpu_count})")
    if s.LLM_MAX_CONCURRENT_REQUESTS < 1:
        logger.warning(f"LLM_MAX_CONCURRENT_REQUESTS={s.LLM_MAX_CONCURRENT_REQUESTS} is invalid, clamping to 1")
        s.LLM_MAX_CONCURRENT_REQUESTS = 1
    if is_placeholder(s.SECRET_KEY):
        s.SECRET_KEY = load_or_create_secret_key(s.DATA_DIR)
        logger.success("[Config] SECRET_KEY loaded from persistent store")
    return s


settings = get_settings()
