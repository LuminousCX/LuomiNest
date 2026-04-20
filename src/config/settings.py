"""LuomiNest 配置管理模块。

基于 pydantic-settings 实现统一配置管理，支持：
- 环境变量加载（.env 文件）
- 类型安全的配置项
- 敏感信息保护（日志中不打印密钥）
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal
import threading

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"
_DATA_DIR = _PROJECT_ROOT / "data"
_LOG_DIR = _PROJECT_ROOT / "logs"


class AppConfig(BaseSettings):
    """应用全局配置。

    所有配置项扁平化管理，通过环境变量前缀区分分组。
    环境变量命名规则：前缀_字段名（如 LLM_API_KEY）。
    """

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="LuomiNest", description="应用名称")
    app_version: str = Field(default="1.0.0", description="应用版本")
    debug: bool = Field(default=False, description="调试模式")
    project_root: str = Field(default=str(_PROJECT_ROOT))
    data_dir: str = Field(default=str(_DATA_DIR))
    log_dir: str = Field(default=str(_LOG_DIR))
    allowed_origins: list[str] = Field(
        default=["*"],
        alias="ALLOWED_ORIGINS",
        description="CORS 允许的来源列表",
    )

    llm_api_key: SecretStr = Field(
        default=SecretStr(""),
        alias="LLM_API_KEY",
        description="大模型 API 密钥",
    )
    llm_base_url: str = Field(
        default="https://ark.cn-beijing.volces.com/api/v3",
        alias="LLM_BASE_URL",
        description="API 基础 URL",
    )
    llm_model_id: str = Field(
        default="",
        alias="LLM_MODEL_ID",
        description="模型端点 ID",
    )
    llm_max_retries: int = Field(default=3, ge=1, le=10, alias="LLM_MAX_RETRIES")
    llm_timeout: int = Field(default=60, ge=10, le=300, alias="LLM_TIMEOUT")
    llm_expert_temperature: float = Field(default=0.5, ge=0.0, le=2.0, alias="LLM_EXPERT_TEMPERATURE")
    llm_expert_max_tokens: int = Field(default=2048, ge=1, le=8192, alias="LLM_EXPERT_MAX_TOKENS")
    llm_fast_temperature: float = Field(default=0.8, ge=0.0, le=2.0, alias="LLM_FAST_TEMPERATURE")
    llm_fast_max_tokens: int = Field(default=512, ge=1, le=4096, alias="LLM_FAST_MAX_TOKENS")
    llm_expert_top_p: float = Field(default=0.95, ge=0.0, le=1.0, alias="LLM_EXPERT_TOP_P")
    llm_fast_top_p: float = Field(default=0.9, ge=0.0, le=1.0, alias="LLM_FAST_TOP_P")
    llm_frequency_penalty: float = Field(default=0.0, ge=-2.0, le=2.0, alias="LLM_FREQUENCY_PENALTY")
    llm_presence_penalty: float = Field(default=0.0, ge=-2.0, le=2.0, alias="LLM_PRESENCE_PENALTY")

    db_type: Literal["sqlite", "json"] = Field(default="sqlite", alias="DB_DB_TYPE")
    db_sqlite_path: str = Field(
        default=str(_DATA_DIR / "luminest.db"),
        alias="DB_SQLITE_PATH",
    )

    hw_serial_port: str = Field(default="COM3", alias="HW_SERIAL_PORT")
    hw_serial_baudrate: int = Field(default=9600, alias="HW_SERIAL_BAUDRATE")
    hw_tcp_host: str = Field(default="0.0.0.0", alias="HW_TCP_HOST")
    hw_tcp_port: int = Field(default=8080, alias="HW_TCP_PORT")
    hw_max_connections: int = Field(default=10, ge=1, le=100, alias="HW_MAX_CONNECTIONS")

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", alias="LOG_LEVEL",
    )
    log_rotation: str = Field(default="10 MB", alias="LOG_ROTATION")
    log_retention: str = Field(default="30 days", alias="LOG_RETENTION")

    memory_embedding_model: str = Field(
        default="BAAI/bge-small-zh-v1.5",
        alias="MEMORY_EMBEDDING_MODEL",
        description="向量嵌入模型名称（默认中英双语）",
    )
    memory_embedding_dimension: int = Field(
        default=512,
        alias="MEMORY_EMBEDDING_DIMENSION",
        description="向量维度",
    )
    memory_recall_top_k: int = Field(
        default=10,
        alias="MEMORY_RECALL_TOP_K",
        description="默认召回数量",
    )
    memory_recall_threshold: float = Field(
        default=0.2,
        alias="MEMORY_RECALL_THRESHOLD",
        description="召回分数阈值",
    )
    memory_half_life_days: float = Field(
        default=30.0,
        alias="MEMORY_HALF_LIFE_DAYS",
        description="时间衰减半衰期（天）",
    )
    memory_mmr_lambda: float = Field(
        default=0.5,
        alias="MEMORY_MMR_LAMBDA",
        description="MMR 多样性平衡参数",
    )
    memory_rrf_k: int = Field(
        default=60,
        alias="MEMORY_RRF_K",
        description="RRF 融合常数 K",
    )
    memory_merge_similarity: float = Field(
        default=0.95,
        alias="MEMORY_MERGE_SIMILARITY",
        description="模糊合并余弦相似度阈值",
    )
    memory_auto_expire_days: int = Field(
        default=90,
        alias="MEMORY_AUTO_EXPIRE_DAYS",
        description="临时记忆自动过期天数",
    )
    memory_max_chunk_length: int = Field(
        default=500,
        alias="MEMORY_MAX_CHUNK_LENGTH",
        description="单条记忆最大字符长度",
    )


_settings: AppConfig | None = None
_settings_lock = threading.Lock()


def get_settings() -> AppConfig:
    """获取全局配置单例。

    Returns:
        AppConfig: 应用全局配置实例。
    """
    global _settings
    if _settings is None:
        with _settings_lock:
            if _settings is None:
                _settings = AppConfig()
    return _settings


def reload_settings() -> AppConfig:
    """重新加载配置（主要用于测试或运行时配置变更）。"""
    global _settings
    with _settings_lock:
        _settings = AppConfig()
    return _settings
