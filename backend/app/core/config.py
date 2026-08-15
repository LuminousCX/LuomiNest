import os
import sys
from functools import lru_cache

from loguru import logger
from pydantic_settings import BaseSettings

from app.core.hardware import get_hardware_profile

from app.security.crypto.secret_key_manager import is_placeholder, load_or_create_secret_key

from app import __version__


class Settings(BaseSettings):
    APP_NAME: str = "LuomiNest"
    APP_VERSION: str = __version__
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
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120  # 2小时

    # 认证模式: "local"（本地单用户，向后兼容）或 "jwt"（多用户远程访问）
    AUTH_MODE: str = "local"
    # JWT 签名密钥，留空则首次启动自动生成
    JWT_SECRET_KEY: str = ""
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30  # 30天
    ALLOW_REGISTRATION: bool = True  # 是否允许新用户注册

    # 内部服务认证 Token（用于 Java 后端等可信内部调用，留空则禁用内部认证）
    INTERNAL_AUTH_TOKEN: str = ""

    # 是否启用 API 文档（/docs, /redoc），生产环境建议关闭
    API_DOCS_ENABLED: bool = False

    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]

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
    LLM_COMPRESSION_THRESHOLD: float = 0.70
    LLM_SUMMARY_MODEL: str = ""
    LLM_SUMMARY_PROVIDER: str = ""
    LLM_SUMMARY_MAX_TOKENS: int = 512
    LLM_CONTEXT_WINDOW_SIZE: int = 0  # 0 表示自动从 provider 获取
    LLM_CONTEXT_STRATEGY: str = "truncate"  # "truncate"（截断）或 "summarize"（LLM 摘要）

    # 上下文压缩预算配置
    LLM_CONTEXT_BUDGET_RATIO: float = 0.35  # 历史消息预算占上下文窗口的比例
    LLM_SUMMARY_TARGET_RATIO: float = 0.40  # 摘要占历史预算的比例（与 compression_ratio 同步）
    LLM_COMPRESSION_RATIO: int = 40  # UI 侧摘要保留百分比（1-90，推荐 40-50）
    LLM_SUMMARY_MAX_LENGTH: int = 2000  # 摘要最大字符数
    LLM_ANTI_DRIFT_ENABLED: bool = True  # 防漂移开关

    LIVE2D_MODEL_PATH: str = "./models/live2d"
    VRM_MODEL_PATH: str = "./models/vrm"

    DATA_DIR: str = "./data"
    UPLOAD_DIR: str = "./data/uploads"
    AVATAR_DIR: str = "./data/avatars"
    PLUGIN_DIR: str = "./plugins"
    SKILL_DIR: str = "./skills"

    # 运行模式标志（由 get_settings() 在运行时设置，不可通过环境变量直接覆盖）
    # - IS_FROZEN:         PyInstaller 打包模式（exe 在 _internal/ 下，资源只读）
    # - DEV_MODE:          开发模式（!IS_FROZEN），从源码运行
    # - DATA_DIR_INJECTED: Electron 注入了 LUOMINEST_DATA_DIR 环境变量
    # 这三个字段用于其他模块判断应该从何处加载内置资源、把数据写入哪里。
    IS_FROZEN: bool = False
    DEV_MODE: bool = True
    DATA_DIR_INJECTED: bool = False

    GITHUB_TOKEN: str = ""

    # 插件市场远程注册表发布源配置
    # 用户可在前端切换发布源，用于解决不同地区访问 GitHub Raw / CDN 的速度差异。
    # 每个源包含 id/name/type/baseUrl/urlPattern/enabled 字段。
    # urlPattern 支持两种模式：
    #   - raw:   {baseUrl}/{owner}/{repo}/{branch}/{path}
    #   - gh:    {baseUrl}/{owner}/{repo}@{branch}/{path} (jsdelivr style)
    REGISTRY_SOURCES: list[dict] = [
        {
            "id": "github-raw",
            "name": "GitHub Raw（官方）",
            "type": "github",
            "baseUrl": "https://raw.githubusercontent.com",
            "urlPattern": "raw",
            "enabled": True,
        },
        {
            "id": "jsdelivr",
            "name": "jsDelivr CDN",
            "type": "cdn",
            "baseUrl": "https://cdn.jsdelivr.net/gh",
            "urlPattern": "gh",
            "enabled": True,
        },
        {
            "id": "gcore-jsdelivr",
            "name": "jsDelivr Gcore（国内加速）",
            "type": "cdn",
            "baseUrl": "https://gcore.jsdelivr.net/gh",
            "urlPattern": "gh",
            "enabled": True,
        },
        {
            "id": "custom-cdn",
            "name": "自定义发布源（开发者）",
            "type": "custom",
            "baseUrl": "",
            "urlPattern": "raw",
            "enabled": False,
        },
    ]
    # 默认活跃发布源 ID（用户切换后持久化到 JsonStore，启动时覆盖此默认值）
    REGISTRY_ACTIVE_SOURCE_ID: str = "github-raw"
    # 远程索引仓库信息（用于构造各发布源 URL）
    REGISTRY_REPO_OWNER: str = "luminous-ChenXi"
    REGISTRY_REPO_NAME: str = "LuomiNest-cxp-registry"
    REGISTRY_INDEX_PATH: str = "index.json"
    REGISTRY_BRANCH: str = "main"

    EXTERNAL_PARSE_API_URL: str = ""
    FILE_MAX_SIZE: int = 100 * 1024 * 1024

    TTS_PROXY: str = ""

    # TTS 统一超时治理（应急修复 B3 / voice-model-market.md G7）：
    # 各引擎散落的 30/60/600 超时常量统一收敛到 Settings，env 可覆盖
    TTS_HTTP_TIMEOUT: float = 60.0          # 云端 TTS HTTP 合成超时（edge/gemini/minimax/siliconflow/fish-audio）
    TTS_DOWNLOAD_TIMEOUT: float = 600.0     # 模型下载超时（sherpa-onnx 大模型慢网络）
    TTS_LOCAL_PROC_TIMEOUT: float = 120.0   # 本地推理/子进程超时（pyttsx3 worker/sherpa 合成）

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
    # 优先级：环境变量 LUOMINEST_DATA_DIR > frozen 模式 exe 目录 > 默认相对路径
    # Electron 桌面端通过 LUOMINEST_DATA_DIR 传入用户数据目录，确保打包后数据
    # 写入 userData/ 而非安装目录（Program Files 可能无写权限）
    env_data_dir = os.environ.get("LUOMINEST_DATA_DIR", "").strip()
    if env_data_dir:
        s.DATA_DIR = os.path.abspath(env_data_dir)
    elif getattr(sys, "frozen", False) and not os.path.isabs(s.DATA_DIR):
        s.DATA_DIR = os.path.join(os.path.dirname(sys.executable), s.DATA_DIR)
        s.DATA_DIR = os.path.abspath(s.DATA_DIR)
    else:
        s.DATA_DIR = os.path.abspath(s.DATA_DIR)
    os.makedirs(s.DATA_DIR, exist_ok=True)

    # 区分"运行时数据目录由 Electron 注入"与"真正的 PyInstaller 打包模式"：
    # - env_data_dir_set: Electron 启动后端时总会注入 LUOMINEST_DATA_DIR，无论 dev 还是 release
    # - is_frozen:        PyInstaller exe 真正打包模式（sys.frozen=True），_internal/ 资源只读
    # 只有 is_frozen 时才需要把 UPLOAD_DIR/AVATAR_DIR/PLUGIN_DIR/SKILL_DIR 重定向到
    # DATA_DIR 下，因为此时 CWD（exe 目录的 _internal/）不可写。
    # dev 模式下即使 Electron 注入了 env_data_dir，仍保留相对路径（backend/plugins、
    # backend/skills），让开发者直接修改源码即时生效。
    env_data_dir_set = bool(env_data_dir)
    is_frozen = getattr(sys, "frozen", False)
    if is_frozen:
        if not os.path.isabs(s.UPLOAD_DIR):
            s.UPLOAD_DIR = os.path.join(s.DATA_DIR, "uploads")
        if not os.path.isabs(s.AVATAR_DIR):
            s.AVATAR_DIR = os.path.join(s.DATA_DIR, "avatars")
        if not os.path.isabs(s.PLUGIN_DIR):
            s.PLUGIN_DIR = os.path.join(s.DATA_DIR, "plugins")
        if not os.path.isabs(s.SKILL_DIR):
            s.SKILL_DIR = os.path.join(s.DATA_DIR, "skills")

        # Electron 桌面端渲染进程从 file:// 加载页面，Origin 为 null，
        # 必须追加到 CORS 白名单否则所有 API 调用被浏览器拦截
        for extra_origin in ["null", "file://"]:
            if extra_origin not in s.CORS_ORIGINS:
                s.CORS_ORIGINS.append(extra_origin)
    else:
        # dev 模式：所有相对路径基于 CWD（通常为 backend/）解析为绝对路径，
        # 让 settings.PLUGIN_DIR / settings.SKILL_DIR / settings.UPLOAD_DIR 始终为绝对路径
        # 便于日志展示与跨模块一致引用。
        for attr in ("UPLOAD_DIR", "AVATAR_DIR", "PLUGIN_DIR", "SKILL_DIR"):
            val = getattr(s, attr)
            if not os.path.isabs(val):
                setattr(s, attr, os.path.abspath(val))

    # 统一确保数据/插件/技能等目录存在（frozen 与 dev 分支均已解析为绝对路径）
    for d in [s.UPLOAD_DIR, s.AVATAR_DIR, s.PLUGIN_DIR, s.SKILL_DIR]:
        os.makedirs(d, exist_ok=True)

    # 暴露运行模式标志（Settings 字段，非环境变量），供 install_service、app_factory 等模块使用：
    # - IS_FROZEN:  是否为 PyInstaller 打包模式（sys.frozen）
    # - DEV_MODE:   是否为开发模式（!IS_FROZEN）
    s.IS_FROZEN = is_frozen
    s.DEV_MODE = not is_frozen
    s.DATA_DIR_INJECTED = env_data_dir_set

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
    # LLM_CONTEXT_STRATEGY 验证
    _valid_strategies = {"truncate", "summarize"}
    if s.LLM_CONTEXT_STRATEGY not in _valid_strategies:
        logger.warning(
            f"LLM_CONTEXT_STRATEGY={s.LLM_CONTEXT_STRATEGY} is invalid, "
            f"must be one of {_valid_strategies}. Falling back to 'truncate'"
        )
        s.LLM_CONTEXT_STRATEGY = "truncate"
    if is_placeholder(s.SECRET_KEY):
        if s.ENVIRONMENT == "production":
            logger.warning(
                "[Config] SECRET_KEY 未显式配置（生产环境）— 已自动生成机器绑定密钥并持久化。"
                "集群部署或跨机迁移前必须显式设置 SECRET_KEY，否则已加密数据将无法解密"
            )
        s.SECRET_KEY = load_or_create_secret_key(s.DATA_DIR)
        logger.success("[Config] SECRET_KEY loaded from persistent store")
    return s


settings = get_settings()
