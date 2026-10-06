"""链路 E 容器化 P0 修复的单元测试：DEPLOYMENT_MODE 双形态开关。

覆盖（05 报告 P0-2 / P0-4、§6 双形态设计）：
1. Settings 新字段默认值回归：desktop 形态下 HOST/PORT 与历史硬编码完全一致
   （127.0.0.1:18000），DEPLOYMENT_MODE 默认 desktop
2. env 通道：LUOMINEST_HOST / LUOMINEST_PORT / DEPLOYMENT_MODE 可覆盖（12-Factor III）
3. host/port 优先级链：CLI > env（Settings）> 默认值
4. auth_token 无头获取：env 注入时不落盘；headless 启动强校验三选一
   （env token / 卷内 token 文件 / AUTH_MODE=jwt+显式 JWT_SECRET_KEY），否则拒绝启动
5. Fail-Closed：headless 下 LUOMINEST_NO_AUTH 不构成凭据来源，认证照常强制
"""
import sys

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings, resolve_host_port, settings
from app.security.auth import local_token
from app.security.auth.local_token import (
    TOKEN_ENV_VAR,
    ensure_boot_auth_token,
    generate_and_save_token,
    load_auth_token,
    validate_headless_auth_ready,
)


@pytest.fixture(autouse=True)
def _desktop_defaults(monkeypatch):
    """用例默认回到 desktop 形态 + 无 env 注入，保证用例互不污染。"""
    monkeypatch.delenv(TOKEN_ENV_VAR, raising=False)
    monkeypatch.delenv("LUOMINEST_NO_AUTH", raising=False)
    monkeypatch.setattr(settings, "DEPLOYMENT_MODE", "desktop")
    local_token._token_cache.clear()
    yield
    local_token._token_cache.clear()


@pytest.fixture()
def headless(monkeypatch):
    """把进程级单例切到 headless 形态。"""
    monkeypatch.setattr(settings, "DEPLOYMENT_MODE", "headless")
    return settings


# ------------------------------------------------------------------
# 1. Settings 默认值回归（desktop 形态 == 历史硬编码行为）
# ------------------------------------------------------------------

def test_settings_desktop_defaults_unchanged(monkeypatch):
    """回归防线：不设任何 env 时，监听地址/端口与原 main.py 硬编码逐字一致。"""
    monkeypatch.delenv("LUOMINEST_HOST", raising=False)
    monkeypatch.delenv("LUOMINEST_PORT", raising=False)
    monkeypatch.delenv("DEPLOYMENT_MODE", raising=False)

    s = Settings(_env_file=None)
    assert s.HOST == "127.0.0.1"
    assert s.PORT == 18000
    assert s.DEPLOYMENT_MODE == "desktop"
    # 进程级单例（导入期生成）同样保持 desktop 默认
    assert settings.DEPLOYMENT_MODE == "desktop"


def test_settings_env_override_host_port_mode(monkeypatch):
    """P0-2：无头容器没有 CLI 入口，env 必须能覆盖监听面（含 0.0.0.0）。"""
    monkeypatch.setenv("LUOMINEST_HOST", "0.0.0.0")
    monkeypatch.setenv("LUOMINEST_PORT", "18001")
    monkeypatch.setenv("DEPLOYMENT_MODE", "headless")

    s = Settings(_env_file=None)
    assert s.HOST == "0.0.0.0"
    assert s.PORT == 18001
    assert s.DEPLOYMENT_MODE == "headless"


def test_settings_rejects_out_of_range_port(monkeypatch):
    monkeypatch.setenv("LUOMINEST_PORT", "70000")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_deployment_mode_invalid_value_falls_back_to_desktop(monkeypatch):
    """非法形态值保守回退 desktop（历史行为）并告警，与 LLM_CONTEXT_STRATEGY 同策略。"""
    monkeypatch.setenv("DEPLOYMENT_MODE", "server")
    s = get_settings.__wrapped__()
    assert s.DEPLOYMENT_MODE == "desktop"


def test_deployment_mode_normalized_case_and_space(monkeypatch):
    monkeypatch.setenv("DEPLOYMENT_MODE", "  Headless ")
    s = get_settings.__wrapped__()
    assert s.DEPLOYMENT_MODE == "headless"


# ------------------------------------------------------------------
# 2. host/port 优先级链：CLI > env（Settings）> 默认值
# ------------------------------------------------------------------

def test_resolve_host_port_defaults_from_settings():
    host, port = resolve_host_port(None, None)
    assert (host, port) == (settings.HOST, settings.PORT)


def test_resolve_host_port_cli_beats_everything():
    assert resolve_host_port("192.168.1.5", 12345) == ("192.168.1.5", 12345)


def test_resolve_host_port_env_when_cli_absent(monkeypatch):
    monkeypatch.setattr(settings, "HOST", "0.0.0.0")
    monkeypatch.setattr(settings, "PORT", 19000)
    assert resolve_host_port(None, None) == ("0.0.0.0", 19000)
    # CLI 只覆盖自己那一位
    assert resolve_host_port("127.0.0.1", None) == ("127.0.0.1", 19000)
    assert resolve_host_port(None, 18888) == ("0.0.0.0", 18888)


def test_main_parse_args_defaults_are_none(monkeypatch):
    """CLI 参数缺省为 None（由 Settings 接管默认值），传参路径不变。"""
    import main as main_module

    monkeypatch.setattr(sys, "argv", ["main.py"])
    args = main_module.parse_args()
    assert args.host is None and args.port is None

    monkeypatch.setattr(sys, "argv", ["main.py", "--host", "0.0.0.0", "--port", "1234"])
    args = main_module.parse_args()
    assert args.host == "0.0.0.0" and args.port == 1234


# ------------------------------------------------------------------
# 3. auth_token：env 注入优先且不落盘
# ------------------------------------------------------------------

def test_generate_token_skips_file_when_env_injected(tmp_path, monkeypatch):
    """P0-4：env 已注入 token 时 generate 不再写文件（容器内落盘的 token 取不回）。"""
    monkeypatch.setenv(TOKEN_ENV_VAR, "injected-token")
    data_dir = tmp_path / "data"

    token = generate_and_save_token(str(data_dir))

    assert token == "injected-token"
    assert not (data_dir / "config" / "auth_token").exists(), "env 注入后不得落盘生成第二份凭据"


def test_generate_token_writes_file_without_env(tmp_path, monkeypatch):
    """desktop 历史行为保持：无 env 注入时生成随机 token 并落盘。"""
    monkeypatch.delenv(TOKEN_ENV_VAR, raising=False)
    data_dir = tmp_path / "data"
    monkeypatch.setattr(settings, "DATA_DIR", str(data_dir))

    token = generate_and_save_token(str(data_dir))
    token_file = data_dir / "config" / "auth_token"

    assert token and len(token) >= 32
    assert token_file.read_text(encoding="utf-8") == token
    assert load_auth_token() == token


def test_load_token_env_beats_file(tmp_path, monkeypatch):
    """读取优先级保持：env > 文件。"""
    token_file = tmp_path / "config" / "auth_token"
    token_file.parent.mkdir(parents=True)
    token_file.write_text("file-token", encoding="utf-8")
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    monkeypatch.setenv(TOKEN_ENV_VAR, "env-token")

    assert load_auth_token() == "env-token"


# ------------------------------------------------------------------
# 4. headless 启动强校验（三选一，否则拒绝启动）
# ------------------------------------------------------------------

def test_headless_validation_passes_with_env_token(headless, monkeypatch):
    monkeypatch.setenv(TOKEN_ENV_VAR, "injected-token")
    assert validate_headless_auth_ready() is None


def test_headless_validation_passes_with_volume_token_file(headless, tmp_path, monkeypatch):
    """随卷迁移的存量实例：数据卷里已有 auth_token 文件即可启动。"""
    monkeypatch.delenv(TOKEN_ENV_VAR, raising=False)
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    token_file = tmp_path / "config" / "auth_token"
    token_file.parent.mkdir(parents=True)
    token_file.write_text("volume-token", encoding="utf-8")

    assert validate_headless_auth_ready() is None


def test_headless_validation_passes_with_jwt(headless, monkeypatch):
    monkeypatch.delenv(TOKEN_ENV_VAR, raising=False)
    monkeypatch.setattr(headless, "AUTH_MODE", "jwt")
    monkeypatch.setattr(headless, "JWT_SECRET_KEY", "explicit-jwt-secret")

    assert validate_headless_auth_ready() is None


def test_headless_validation_requires_explicit_jwt_secret(headless, monkeypatch):
    """jwt 密钥留空会在首次签发时走机器指纹自动生成（容器重建即作废），不算合格来源。"""
    monkeypatch.delenv(TOKEN_ENV_VAR, raising=False)
    monkeypatch.setattr(headless, "AUTH_MODE", "jwt")
    monkeypatch.setattr(headless, "JWT_SECRET_KEY", "")

    with pytest.raises(RuntimeError, match="headless"):
        validate_headless_auth_ready()


def test_headless_validation_refuses_without_any_source(headless, monkeypatch):
    monkeypatch.delenv(TOKEN_ENV_VAR, raising=False)
    monkeypatch.setattr(headless, "AUTH_MODE", "local")
    monkeypatch.setattr(headless, "JWT_SECRET_KEY", "")

    with pytest.raises(RuntimeError, match=TOKEN_ENV_VAR):
        validate_headless_auth_ready()


def test_headless_validation_ignores_whitespace_env_token(headless, monkeypatch):
    monkeypatch.setenv(TOKEN_ENV_VAR, "   ")
    with pytest.raises(RuntimeError):
        validate_headless_auth_ready()


def test_headless_no_auth_is_not_a_credential_source(headless, monkeypatch):
    """Fail-Closed 红线：LUOMINEST_NO_AUTH 在 headless 下不豁免启动校验，认证照常强制。"""
    monkeypatch.delenv(TOKEN_ENV_VAR, raising=False)
    monkeypatch.setattr(headless, "AUTH_MODE", "local")
    monkeypatch.setattr(headless, "JWT_SECRET_KEY", "")
    monkeypatch.setenv("LUOMINEST_NO_AUTH", "1")

    with pytest.raises(RuntimeError):
        validate_headless_auth_ready()


def test_desktop_validation_is_noop(monkeypatch):
    """desktop 形态不受强校验影响：无任何凭据来源也不拦（保持首启自动生成路径）。"""
    monkeypatch.delenv(TOKEN_ENV_VAR, raising=False)
    assert validate_headless_auth_ready() is None


# ------------------------------------------------------------------
# 5. 启动期凭据就绪（app_factory 委托的 ensure_boot_auth_token）
# ------------------------------------------------------------------

def test_boot_desktop_autogenerates_and_persists(tmp_path, monkeypatch):
    """desktop 无 env 无文件 → 自动生成并落盘（历史行为，Electron 靠文件取回）。"""
    monkeypatch.delenv(TOKEN_ENV_VAR, raising=False)
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))

    token = ensure_boot_auth_token()
    token_file = tmp_path / "config" / "auth_token"

    assert token
    assert token_file.read_text(encoding="utf-8") == token


def test_boot_desktop_reuses_existing_file(tmp_path, monkeypatch):
    """desktop 已有 token 文件 → 复用，不重复生成（二次启动稳定性）。"""
    monkeypatch.delenv(TOKEN_ENV_VAR, raising=False)
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    token_file = tmp_path / "config" / "auth_token"
    token_file.parent.mkdir(parents=True)
    token_file.write_text("existing-token", encoding="utf-8")

    assert ensure_boot_auth_token() == "existing-token"
    assert token_file.read_text(encoding="utf-8") == "existing-token"


def test_boot_headless_env_token_no_file(headless, tmp_path, monkeypatch):
    monkeypatch.setenv(TOKEN_ENV_VAR, "injected-token")
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))

    assert ensure_boot_auth_token() == "injected-token"
    assert not (tmp_path / "config" / "auth_token").exists()


def test_boot_headless_jwt_mode_returns_none_without_file(headless, tmp_path, monkeypatch):
    """headless + jwt 显式密钥：local token 非必需，返回 None 且绝不落盘。"""
    monkeypatch.delenv(TOKEN_ENV_VAR, raising=False)
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(headless, "AUTH_MODE", "jwt")
    monkeypatch.setattr(headless, "JWT_SECRET_KEY", "explicit-jwt-secret")

    assert ensure_boot_auth_token() is None
    assert not (tmp_path / "config" / "auth_token").exists()


def test_boot_headless_refuses_without_source(headless, tmp_path, monkeypatch):
    monkeypatch.delenv(TOKEN_ENV_VAR, raising=False)
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(headless, "AUTH_MODE", "local")
    monkeypatch.setattr(headless, "JWT_SECRET_KEY", "")

    with pytest.raises(RuntimeError):
        ensure_boot_auth_token()
    assert not (tmp_path / "config" / "auth_token").exists(), "拒绝启动时不得留下半成品凭据文件"


def test_boot_desktop_no_auth_still_generates(tmp_path, monkeypatch):
    """LUOMINEST_NO_AUTH 在 desktop 下也只影响日志文案，token 照常生成（既有加固）。"""
    monkeypatch.delenv(TOKEN_ENV_VAR, raising=False)
    monkeypatch.setenv("LUOMINEST_NO_AUTH", "true")
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))

    token = ensure_boot_auth_token(no_auth=True)
    assert token
    assert (tmp_path / "config" / "auth_token").exists()


# ------------------------------------------------------------------
# 6. 容器基线自检（防回归的环境不变量）
# ------------------------------------------------------------------

def test_token_env_var_name_stable():
    """编排/文档依赖该 env 名，属对外契约，改名即破坏容器部署基线。"""
    assert TOKEN_ENV_VAR == "LUOMINEST_AUTH_TOKEN"


def test_main_listen_exposure_warnings(monkeypatch):
    """main.py 监听告警契约：desktop loopback 静默；headless loopback 打提示；
    非 loopback 的 LAN 暴露告警两形态都在（历史行为不回退）。"""
    from loguru import logger

    import main as main_module

    warned: list[str] = []
    monkeypatch.setattr(logger, "warning", lambda msg, *a, **k: warned.append(str(msg)))
    monkeypatch.setenv("LUOMINEST_LISTEN_HOST", "placeholder")

    # desktop + loopback → 无任何告警
    monkeypatch.setattr(settings, "DEPLOYMENT_MODE", "desktop")
    main_module.warn_listen_exposure("127.0.0.1")
    assert warned == []

    # headless + loopback → 提示性告警（容器外不可达）
    monkeypatch.setattr(settings, "DEPLOYMENT_MODE", "headless")
    warned.clear()
    main_module.warn_listen_exposure("127.0.0.1")
    assert any("Headless" in w for w in warned), "headless 绑 loopback 必须提示容器外不可达"

    # headless + 0.0.0.0 → 无 loopback 提示（绑定为本意），但 LAN 暴露告警保留
    warned.clear()
    main_module.warn_listen_exposure("0.0.0.0")
    assert not any("Headless" in w for w in warned)
    assert any("非 loopback" in w for w in warned), "LAN 暴露告警不应因 headless 而消失"
