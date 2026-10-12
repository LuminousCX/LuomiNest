import os
import sys
from functools import lru_cache

from loguru import logger
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.hardware import get_hardware_profile

from app.security.crypto.secret_key_manager import is_placeholder, load_or_create_secret_key

from app import __version__


class Settings(BaseSettings):
    APP_NAME: str = "LuomiNest"
    APP_VERSION: str = __version__
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    # ── 部署形态单开关（链路 E 容器化 / 05 报告 §6 双形态设计）──
    # desktop（默认）：单人桌面形态，全部行为与历史版本完全一致
    # headless：Docker/无头容器形态——允许绑定非 loopback；认证凭据来源必须
    #   显式三选一（LUOMINEST_AUTH_TOKEN env / 数据卷 auth_token 文件 /
    #   AUTH_MODE=jwt+显式 JWT_SECRET_KEY），否则拒绝启动；认证永远强制开启
    #   （LUOMINEST_NO_AUTH 不豁免，保持既有加固）。行为差异清单见
    #   app/security/auth/local_token.py::ensure_boot_auth_token 与 main.py。
    DEPLOYMENT_MODE: str = "desktop"

    # 主 API 监听地址/端口。原 main.py argparse 硬编码 127.0.0.1:18000，收编进
    # Settings 打通 env 通道（12-Factor III；无头容器没有传 CLI 参数的入口）。
    # env 名沿项目 LUOMINEST_ 前缀惯例：LUOMINEST_HOST / LUOMINEST_PORT。
    # 刻意不接受裸 HOST/PORT——那是太多无关工具的常用变量名，误读风险大。
    # 优先级链：CLI --host/--port > 本字段（env）> 默认值，见 main.py::resolve_host_port。
    HOST: str = Field(default="127.0.0.1", validation_alias="LUOMINEST_HOST")
    PORT: int = Field(default=18000, validation_alias="LUOMINEST_PORT", ge=1, le=65535)

    # 空字符串表示运行时根据 DATA_DIR 自动计算（见 get_settings）
    DATABASE_URL: str = ""
    REDIS_URL: str = "redis://localhost:6379/0"
    MQTT_BROKER_EMBEDDED: bool = True  # W6-3：内嵌 MQTT broker（开箱即用；端口被占用时自动降级）
    MQTT_BROKER_HOST: str = "127.0.0.1"  # 内嵌 broker 监听地址与客户端默认连接地址
    MQTT_BROKER_PORT: int = 1883
    MQTT_USERNAME: str = ""
    MQTT_PASSWORD: str = ""
    # P0-4：设备遥测内存缓存（TelemetryCache）TTL——超过该秒数未上报 status 的设备数据视为过期
    TELEMETRY_CACHE_TTL: int = 600

    # P0-4：天气服务（WeatherService，provider 链 wttr.in → Open-Meteo → 兜底文案）
    WEATHER_CACHE_TTL: int = 1800      # 同城市查询 LRU 缓存时长（秒），TTL 内连查只打一次外网
    WEATHER_HTTP_TIMEOUT: float = 8.0  # 上游天气源 HTTP 超时（秒）

    # 数据备份（luominest_backup_manager 定时任务）
    BACKUP_ENABLED: bool = True
    BACKUP_INTERVAL_HOURS: int = 24

    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120  # 2小时

    # 认证模式: "local"（本地单用户，向后兼容）或 "jwt"（多用户远程访问）
    AUTH_MODE: str = "local"
    # JWT 签名密钥，留空则首次启动自动生成
    JWT_SECRET_KEY: str = ""
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30  # 30天
    ALLOW_REGISTRATION: bool = True  # 是否允许新用户注册

    # 内部服务认证 Token（供可信内部服务调用，留空则禁用内部认证）
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
    # （全局模型统一：LLM_SUMMARY_MODEL/LLM_SUMMARY_PROVIDER 已移除，
    #   上下文压缩/摘要统一走全局主模型）
    LLM_COMPRESS_ENABLED: bool = False
    LLM_COMPRESSION_THRESHOLD: float = 0.70
    LLM_SUMMARY_MAX_TOKENS: int = 512
    LLM_CONTEXT_WINDOW_SIZE: int = 0  # 0 表示自动从 provider 获取
    LLM_CONTEXT_STRATEGY: str = "truncate"  # "truncate"（截断）或 "summarize"（LLM 摘要）

    # W2 按需注入：主对话工具三级注入（常驻 core/meta + 按消息召回 + 长尾仅名称摘要）
    # "full" 为旧版全量注入回退开关（保留一个版本供排障）
    LLM_TOOL_INJECTION_MODE: str = "auto"  # "auto" | "full"
    # W7 工具面裁剪：cli/写文件/启动应用/A2A/协作委派等高权限工具默认移出注入面
    LLM_POWER_TOOLS_ENABLED: bool = False
    # W2-4 工具循环内逐轮上下文兜底裁剪（防长工具链超窗）
    LLM_CONTEXT_TRIM_ENABLED: bool = True
    LLM_CONTEXT_TRIM_THRESHOLD: float = 0.85  # 超过窗口该比例触发裁剪
    # <avatar_emotion> 表情块注入开关（平台文字渠道恒关；桌面由前端 Live2D 配置决定）
    LLM_AVATAR_EMOTION_ENABLED: bool = True

    # ── 辰汐生态打通 W2：五类标签网关 / 快慢脑寻址（分册 08 §15、分册 10 §18）──
    # 运行时值由 model_config（config_items['model_config']）同名键在启动
    # （apply_model_config_from_db）与 PATCH /models/config 时覆盖。
    # fast_brain / slow_brain = "provider_id/model_id" 字符串；
    # 空/缺省 = 快/慢脑模式关闭（不注入快脑提示词块、不注入皮套工具、
    # 不注入四段式——行为与现状完全一致，优雅降级）。
    FAST_BRAIN: str = ""
    SLOW_BRAIN: str = ""
    # 皮套工具（<tool:avatar_*/>）总开关，默认关；仅快脑可挂（分册 08 §15.2 条款 3）
    AVATAR_TOOLS_ENABLED: bool = False
    # Live2D motion 注册表（消费端 motion3 动作 ID 列表，由配置声明）；
    # 空 = 不注入皮套工具提示词，且解析侧所有 motion 调用按注册表外丢弃
    AVATAR_MOTION_REGISTRY: list[str] = []
    # 合同词→语义 ID 映射覆盖表（可选 JSON 文件路径，{"smile":"happy"} 形态）
    AVATAR_TRANSLATION_OVERRIDE: str = ""

    # ── 辰汐生态打通 W3：dispatch 派发网关第二关（分册 10 §18.3）────────
    # 阈值与动词表均为消费端配置项（§18.3 只定语义档位：先改章再调参）。
    # 长度关：task 去空白后 < N 字符 → 判空派发，丢弃；
    # 意图关：task 不含工具动词且无检索意图特征 → 丢弃（两表均为逗号分隔 CSV，
    # env 可覆盖：DISPATCH_TOOL_VERBS / DISPATCH_INTENT_MARKERS）。
    DISPATCH_TASK_MIN_CHARS: int = 6
    DISPATCH_TOOL_VERBS: str = (
        "查,搜,找,算,列,执行,跑,发,改,禁,踢,重启,监控,打开,关闭,启动,安装,下载,"
        "创建,删除,发送,设置,同步,备份,检索,浏览,截图,翻译,计算,转换,播放,停止,上传,抓取"
    )
    DISPATCH_INTENT_MARKERS: str = (
        "什么,怎么,怎样,哪些,多少,几,最新,今天,明天,现在,新闻,天气,价格,是哪,在哪,"
        "文件,网页,网址,联网,上网,资料,消息,邮件,日程,提醒,订单,快递"
    )

    # ── 辰汐生态打通 W3：权限三级 T2 信任档总开关 ──────────────────────
    # 持久化键 config_items['permission.trusted_mode']；启动时由
    # load_trusted_mode_from_db() 镜像到本运行时值（跟随 model_config 五键惯例）。
    # 开启后所有工具免弹窗直接执行（T1 高危工具也放行；黑名单硬防线仍在
    # CommandValidator，不受本开关影响）。默认 false = T0/T1 分级正常生效。
    PERMISSION_TRUSTED_MODE: bool = False


    # W6-1 对外 MCP 服务器：把陪伴安全工具白名单经 Streamable HTTP 暴露在 /mcp
    MCP_SERVER_ENABLED: bool = True
    # P0-3 传输安全：/mcp Bearer 鉴权开关（token 见 config_items: mcp_server.token，
    # 经 /api/v1/mcp/token 查看/重置）。仅限明确知晓风险时关闭。
    MCP_SERVER_AUTH: bool = True

    # 上下文压缩预算配置
    LLM_CONTEXT_BUDGET_RATIO: float = 0.35  # 历史消息预算占上下文窗口的比例
    LLM_SUMMARY_TARGET_RATIO: float = 0.40  # 摘要占历史预算的比例（与 compression_ratio 同步）
    LLM_COMPRESSION_RATIO: int = 40  # UI 侧摘要保留百分比（1-90，推荐 40-50）
    LLM_SUMMARY_MAX_LENGTH: int = 2000  # 摘要最大字符数
    LLM_ANTI_DRIFT_ENABLED: bool = True
    # 记忆注入预算（字符）：ContextBuilder 组装 <user_memory> 块的上限（审计外需求：可配）
    MEMORY_INJECTION_BUDGET: int = 4000
    # 记忆嵌入模型（P0-5）：显式覆盖记忆向量嵌入模型名；空则按
    # LLMEmbeddingProvider 兜底解析（仅 openai 系默认 text-embedding-3-small）。
    # 注意：换 embed 模型 = 换向量空间，存量向量需重嵌入（memory.vector_rebuild）
    MEMORY_EMBED_MODEL: str = ""
    # 主动关心（晨间简报）：本地记忆驱动的问候，懒生成 + 当日缓存
    PROACTIVE_CARE_ENABLED: bool = True
    PROACTIVE_BRIEFING_HOUR: int = 6  # 防漂移开关

    # 定时任务结果投递（P0-1 闭环）：任务触发后执行结果是否写回创建任务的网页会话
    # （assistant 消息，带 [定时任务] 前缀）；关闭后结果仅保留在任务记录（任务面板可查）
    SCHEDULER_RESULT_INTO_CHAT: bool = True

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

    # STT 模型下载超时（sherpa-onnx SenseVoice 模型下载，原 STT 模块内硬编码 600 秒）
    MODEL_DOWNLOAD_TIMEOUT: int = 600

    # 平台适配器 HTTP 请求超时（QQ 官方/微信公众号/企业微信 REST 调用，原各适配器内联 timeout=15）
    PLATFORM_HTTP_TIMEOUT: int = 15

    # Agent 集群调用配置
    APP_SELF_BASE_URL: str = "http://localhost:8000"
    A2A_SERVERS: list[dict] = []  # 每项: {name, url, enabled, api_key}
    A2A_TIMEOUT_SECONDS: int = 60
    A2A_MAX_DEPTH: int = 3

    # pydantic-settings v2 写法（class Config 已弃用，审计 B6-6）
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


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

    # 部署形态归一化：非法值按 desktop 处理并告警（与 LLM_CONTEXT_STRATEGY 同策略，
    # 保守回退到历史行为而非拒绝启动——desktop 即现状，认证本来就强制开启）
    _mode = (s.DEPLOYMENT_MODE or "").strip().lower()
    if _mode not in ("desktop", "headless"):
        logger.warning(
            f"DEPLOYMENT_MODE={s.DEPLOYMENT_MODE!r} is invalid, "
            f"must be 'desktop' or 'headless'. Falling back to 'desktop'"
        )
        _mode = "desktop"
    s.DEPLOYMENT_MODE = _mode

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


def resolve_host_port(cli_host: str | None, cli_port: int | None) -> tuple[str, int]:
    """解析主 API 监听地址/端口，优先级链：CLI > env（Settings 字段）> 默认值。

    P0-2（链路 E）：host/port 原本只认 main.py 的 CLI 参数，无头容器没有传参
    入口，故收编进 Settings（env: LUOMINEST_HOST / LUOMINEST_PORT）；
    CLI 显式传入时仍是最高优先级（桌面启动方式不变）。
    """
    s = settings
    host = cli_host if cli_host is not None else s.HOST
    port = cli_port if cli_port is not None else s.PORT
    return host, port


settings = get_settings()
