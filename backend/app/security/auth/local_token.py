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


# 认证热路径缓存（审计 B5-5）：中间件每请求调用 load_auth_token，
# 原实现无条件 read_text 是纯 IO 浪费；按 stat().st_mtime_ns 缓存文件内容，
# 运行期轮换 token（外部改写文件）自动生效。
_token_cache: dict[str, tuple[int, str]] = {}  # token 文件路径 -> (mtime_ns, token)


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
    path_key = str(token_path)
    try:
        mtime_ns = token_path.stat().st_mtime_ns
    except OSError:
        return None
    cached = _token_cache.get(path_key)
    if cached is not None and cached[0] == mtime_ns:
        return cached[1]
    try:
        token = token_path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if token:
        _token_cache[path_key] = (mtime_ns, token)
    return token


def generate_and_save_token(data_dir: str) -> str:
    """生成随机令牌并持久化到文件。

    P0-4（链路 E）：LUOMINEST_AUTH_TOKEN 已显式注入时直接返回注入值、不再落盘——
    headless 容器里生成的 token 文件宿主机取不回，注入的 env 是唯一可信凭据来源，
    同时避免在容器可写层再留一份多余凭据副本。
    """
    env_token = os.environ.get(TOKEN_ENV_VAR, "").strip()
    if env_token:
        logger.info(f"[Auth] {TOKEN_ENV_VAR} already injected, skip token file generation")
        return env_token

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


# ── 部署形态相关（链路 E 容器化 P0-4 / 05 报告 §6 双形态开关）──


def validate_headless_auth_ready() -> None:
    """headless 形态启动强校验：认证凭据来源三选一，否则拒绝启动。

    桌面形态首启自动生成 token 落盘、Electron 再从文件取回；无头容器没有这条
    回传通道——若放任自动生成，服务会"活着但全 API 401"（Fail-Closed 的
    副作用），比启动失败更难排查。故 headless 下必须显式提供凭据来源：

      1. env 注入 LUOMINEST_AUTH_TOKEN（容器编排推荐方式）
      2. 数据卷内已有 auth_token 文件（随卷迁移的存量实例）
      3. AUTH_MODE=jwt 且 JWT_SECRET_KEY 显式配置（留空的 jwt 密钥会在首次
         签发时走机器指纹自动生成，容器重建即作废，不算合格来源）

    安全红线：本函数只做"凭据来源存在性"校验，不提供任何无认证旁路；
    LUOMINEST_NO_AUTH 在任何形态下都不会豁免认证（既有加固保持）。
    desktop 形态直接放行（行为与历史版本一致，token 缺失时走自动生成）。
    """
    from app.core.config import settings

    if settings.DEPLOYMENT_MODE != "headless":
        return
    if load_auth_token():
        return
    if settings.AUTH_MODE == "jwt" and settings.JWT_SECRET_KEY.strip():
        return
    raise RuntimeError(
        "[Auth] DEPLOYMENT_MODE=headless but no auth credential source available. "
        f"Provide one of: (1) env {TOKEN_ENV_VAR}; "
        "(2) token file at DATA_DIR/config/auth_token (volume); "
        "(3) AUTH_MODE=jwt + explicit JWT_SECRET_KEY. "
        "Refusing to start (fail-closed)."
    )


def ensure_boot_auth_token(*, no_auth: bool = False) -> str | None:
    """后端启动期确保认证凭据就绪，返回 local 模式 token（jwt 模式/无来源时为 None）。

    - headless：先过 validate_headless_auth_ready 强校验；且绝不落盘生成
      token（容器内生成的文件宿主机取不回）
    - desktop：保持历史行为——env > 已有文件 > 自动生成落盘
    - LUOMINEST_NO_AUTH 任何形态都不豁免认证（既有加固），仅影响日志文案
    """
    from app.core.config import settings

    validate_headless_auth_ready()

    auth_token = load_auth_token()
    if auth_token:
        return auth_token

    if settings.DEPLOYMENT_MODE == "headless":
        # 强校验已通过但 env/文件 token 都没有 → 唯一来源是 jwt+显式密钥，
        # local token 在 jwt 模式非必需；容器内落盘的 token 谁也取不回，不生成
        logger.info("[Auth] headless mode uses JWT auth, skip local token file generation")
        return None

    auth_token = generate_and_save_token(settings.DATA_DIR)
    if no_auth:
        logger.info("[Auth] LUOMINEST_NO_AUTH 模式: 已自动生成认证 token（不再完全无认证）")
    else:
        logger.info("[Auth] 未找到 auth token，已自动生成（dev mode）")
    return auth_token
