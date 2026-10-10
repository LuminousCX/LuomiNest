"""system_locale 模块单测.

覆盖：BCP47 规范化、system_lang_key 映射逻辑、探测回退链、lru_cache 缓存行为。
全部通过 monkeypatch 注入探测结果，不依赖真机 locale 值做精确断言。
"""

import pytest

import app.core.system_locale as system_locale_module
from app.core.system_locale import detect_system_locale, system_lang_key


@pytest.fixture(autouse=True)
def _clear_locale_cache():
    """每个用例前后清空 lru_cache，避免跨用例污染。"""
    detect_system_locale.cache_clear()
    yield
    detect_system_locale.cache_clear()


# ---------------------------------------------------------------------------
# BCP47 规范化
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("zh-CN", "zh-CN"),
        ("zh_CN", "zh-CN"),
        ("zh_CN.UTF-8", "zh-CN"),
        ("en-us", "en-US"),
        ("en_US", "en-US"),
        ("ja_JP", "ja-JP"),
        ("ko-KR", "ko-KR"),
        ("C", None),
        ("", None),
        (None, None),
        ("12345", None),
    ],
)
def test_normalize_bcp47(raw, expected):
    assert system_locale_module._normalize_bcp47(raw) == expected


# ---------------------------------------------------------------------------
# system_lang_key 映射
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("locale_str", "expected"),
    [
        ("zh-CN", "zh"),
        ("zh-SG", "zh"),
        ("zh-TW", "yue"),
        ("zh-HK", "yue"),
        ("zh", "zh"),
        ("en-US", "en"),
        ("en-GB", "en"),
        ("en", "en"),
        ("ja-JP", "ja"),
        ("ko-KR", "ko"),
        ("fr-FR", "zh"),
        ("de-DE", "zh"),
        ("es-MX", "zh"),
        ("", "zh"),
        (None, "zh"),
        ("garbage!!!", "zh"),
    ],
)
def test_system_lang_key_mapping(locale_str, expected):
    assert system_lang_key(locale_str) == expected


def test_system_lang_key_uses_detect_when_none(monkeypatch):
    """locale_str=None 时走系统探测路径（而非恒等于 zh）。"""
    monkeypatch.setattr(
        system_locale_module, "_detect_via_windows_api", lambda: "ja-JP"
    )
    monkeypatch.setattr(system_locale_module, "_detect_via_defaultlocale", lambda: None)
    monkeypatch.setattr(system_locale_module, "_detect_via_env", lambda: None)
    assert system_lang_key() == "ja"


# ---------------------------------------------------------------------------
# 探测回退链（monkeypatch 注入，不依赖真机）
# ---------------------------------------------------------------------------


def test_detect_prefers_windows_api(monkeypatch):
    monkeypatch.setattr(
        system_locale_module, "_detect_via_windows_api", lambda: "en-US"
    )
    monkeypatch.setattr(system_locale_module, "_detect_via_defaultlocale", lambda: "zh_CN")
    monkeypatch.setattr(system_locale_module, "_detect_via_env", lambda: "zh_CN.UTF-8")
    assert detect_system_locale() == "en-US"


def test_detect_falls_back_to_defaultlocale(monkeypatch):
    monkeypatch.setattr(system_locale_module, "_detect_via_windows_api", lambda: None)
    monkeypatch.setattr(
        system_locale_module, "_detect_via_defaultlocale", lambda: "ja_JP"
    )
    monkeypatch.setattr(system_locale_module, "_detect_via_env", lambda: "zh_CN.UTF-8")
    assert detect_system_locale() == "ja-JP"


def test_detect_falls_back_to_env(monkeypatch):
    monkeypatch.setattr(system_locale_module, "_detect_via_windows_api", lambda: None)
    monkeypatch.setattr(system_locale_module, "_detect_via_defaultlocale", lambda: None)
    monkeypatch.setattr(system_locale_module, "_detect_via_env", lambda: "zh_CN.UTF-8")
    assert detect_system_locale() == "zh-CN"


def test_detect_env_lc_all_wins_over_lang(monkeypatch):
    monkeypatch.setattr(system_locale_module, "_detect_via_windows_api", lambda: None)
    monkeypatch.setattr(system_locale_module, "_detect_via_defaultlocale", lambda: None)
    monkeypatch.setattr(
        system_locale_module,
        "_detect_via_env",
        lambda: system_locale_module.os.environ.get("LC_ALL")
        or system_locale_module.os.environ.get("LANG")
        or None,
    )
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    monkeypatch.setenv("LC_ALL", "ko_KR.UTF-8")
    assert detect_system_locale() == "ko-KR"


def test_detect_probe_raises_skips_to_next(monkeypatch):
    """探测函数抛异常时跳过该层继续回退（而非整体失败）。"""

    def _boom():
        raise RuntimeError("probe exploded")

    monkeypatch.setattr(system_locale_module, "_detect_via_windows_api", _boom)
    monkeypatch.setattr(
        system_locale_module, "_detect_via_defaultlocale", lambda: "en_GB"
    )
    monkeypatch.setattr(system_locale_module, "_detect_via_env", lambda: None)
    assert detect_system_locale() == "en-GB"


def test_detect_all_fail_returns_default(monkeypatch):
    monkeypatch.setattr(system_locale_module, "_detect_via_windows_api", lambda: None)
    monkeypatch.setattr(system_locale_module, "_detect_via_defaultlocale", lambda: None)
    monkeypatch.setattr(system_locale_module, "_detect_via_env", lambda: None)
    assert detect_system_locale() == "zh-CN"


def test_detect_unrecognizable_probe_falls_through(monkeypatch):
    """探测结果无法规范化（如 "C"）时继续走下一层。"""
    monkeypatch.setattr(system_locale_module, "_detect_via_windows_api", lambda: "C")
    monkeypatch.setattr(system_locale_module, "_detect_via_defaultlocale", lambda: None)
    monkeypatch.setattr(system_locale_module, "_detect_via_env", lambda: "en_US")
    assert detect_system_locale() == "en-US"


# ---------------------------------------------------------------------------
# 缓存行为：探测只执行一次
# ---------------------------------------------------------------------------


def test_detect_is_cached(monkeypatch):
    calls = {"count": 0}

    def _counting_windows_probe():
        calls["count"] += 1
        return "en-US"

    monkeypatch.setattr(
        system_locale_module, "_detect_via_windows_api", _counting_windows_probe
    )
    monkeypatch.setattr(system_locale_module, "_detect_via_defaultlocale", lambda: None)
    monkeypatch.setattr(system_locale_module, "_detect_via_env", lambda: None)

    assert detect_system_locale() == "en-US"
    assert detect_system_locale() == "en-US"
    assert detect_system_locale() == "en-US"
    assert calls["count"] == 1  # 二、三次调用命中缓存，探测函数不再执行


def test_cache_clear_reprobes(monkeypatch):
    monkeypatch.setattr(
        system_locale_module, "_detect_via_windows_api", lambda: "en-US"
    )
    assert detect_system_locale() == "en-US"

    # 清缓存 + 换探测结果 → 重新探测
    monkeypatch.setattr(
        system_locale_module, "_detect_via_windows_api", lambda: "ja-JP"
    )
    detect_system_locale.cache_clear()
    assert detect_system_locale() == "ja-JP"


# ---------------------------------------------------------------------------
# Windows API 回退路径的 LANGID 映射（纯表查询，不发真实调用）
# ---------------------------------------------------------------------------


def test_langid_table_covers_core_locales():
    assert system_locale_module._LANGID_TO_LOCALE[0x0804] == "zh-CN"
    assert system_locale_module._LANGID_TO_LOCALE[0x0409] == "en-US"
    assert system_locale_module._LANGID_TO_LOCALE[0x0411] == "ja-JP"
    assert system_locale_module._PRIMARY_LANG_TO_CODE[0x0004] == "zh"
