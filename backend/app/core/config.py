import secrets
import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    APP_NAME: str = "LuomiNest"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    DATABASE_URL: str = "sqlite+aiosqlite:///./luominest.db"
    REDIS_URL: str = "redis://localhost:6379/0"
    MQTT_BROKER_HOST: str = "localhost"
    MQTT_BROKER_PORT: int = 1883
    MQTT_USERNAME: str = ""
    MQTT_PASSWORD: str = ""

    SECRET_KEY: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    LLM_DEFAULT_PROVIDER: str = "openai"
    LLM_FALLBACK_CHAIN: str = "openai,ollama"
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = ""
    ANTHROPIC_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    LIVE2D_MODEL_PATH: str = "./models/live2d"
    VRM_MODEL_PATH: str = "./models/vrm"

    DATA_DIR: str = "./data"
    UPLOAD_DIR: str = "./data/uploads"
    AVATAR_DIR: str = "./data/avatars"
    PLUGIN_DIR: str = "./plugins"
    SKILL_DIR: str = "./skills"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.SECRET_KEY:
            if self.ENVIRONMENT == "production":
                raise ValueError("生产环境必须设置 SECRET_KEY 环境变量")
            self.SECRET_KEY = secrets.token_urlsafe(32)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
