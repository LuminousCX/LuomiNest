from functools import lru_cache

from loguru import logger
from pydantic_settings import BaseSettings

from app.security.crypto.secret_key_manager import is_placeholder, load_or_create_secret_key


class Settings(BaseSettings):
    APP_NAME: str = "LuomiNest"
    APP_VERSION: str = "0.7.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    DATABASE_URL: str = "sqlite+aiosqlite:///./luominest.db"
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
    LLM_MAX_CONCURRENT_REQUESTS: int = 3

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
    if s.LLM_MAX_CONCURRENT_REQUESTS < 1:
        logger.warning(f"LLM_MAX_CONCURRENT_REQUESTS={s.LLM_MAX_CONCURRENT_REQUESTS} is invalid, clamping to 1")
        s.LLM_MAX_CONCURRENT_REQUESTS = 1
    if is_placeholder(s.SECRET_KEY):
        s.SECRET_KEY = load_or_create_secret_key(s.DATA_DIR)
        logger.success("[Config] SECRET_KEY loaded from persistent store")
    return s


settings = get_settings()
