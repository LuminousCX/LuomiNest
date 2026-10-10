"""系统 locale 探测模块（纯探测，无管理员权限，进程内一次性缓存）.

用途：语音栈（TTS 默认音色 / STT 识别语言 / 前端初始语言）跟随用户系统语言，
但绝不改变用户已保存的显式配置 —— 本模块只做"读系统当前 UI 语言"这一件事。

探测链（首个成功者生效，全部失败回落 "zh-CN"）：
1. Windows：ctypes 调 kernel32 的用户 UI 语言接口（当前用户态，无需管理员权限）
2. locale.getdefaultlocale()（stdlib，Python 3.12 起弃用但仍可用，警告已抑制）
3. 环境变量 LC_ALL / LANG（常见于 Linux/macOS/容器）
4. 兜底 "zh-CN"（产品默认语言）

输出统一为 BCP47 规范形（语言小写 + 区域大写，如 "zh-CN"、"en-US"）。
"""

import ctypes
import functools
import locale
import os
import re
import warnings

# 产品默认语言（与前端 DEFAULT_LOCALE 一致）
_DEFAULT_LOCALE = "zh-CN"

# locale 形如 "zh_CN.UTF-8" / "en-US" / "ja_JP"：语言部分 + 可选区域部分
_BCP47_RE = re.compile(r"^([A-Za-z]{2,3})(?:[-_]([A-Za-z]{2}|\d{3}))?.*$")

# LOCALE_NAME_MAX_LENGTH（Windows SDK 定义）
_LOCALE_NAME_MAX_LENGTH = 85

# LANGID → 完整 locale 的常见映射（GetUserDefaultUILanguage 回退路径用）
_LANGID_TO_LOCALE: dict[int, str] = {
    0x0804: "zh-CN",
    0x0404: "zh-TW",
    0x0C04: "zh-HK",
    0x1004: "zh-SG",
    0x0409: "en-US",
    0x0809: "en-GB",
    0x0411: "ja-JP",
    0x0412: "ko-KR",
}

# 主语言 ID（LANGID 低 10 位）→ 语言代码（无区域时的最后回退）
_PRIMARY_LANG_TO_CODE: dict[int, str] = {
    0x0004: "zh",
    0x0009: "en",
    0x0011: "ja",
    0x0012: "ko",
}


def _normalize_bcp47(raw: str | None) -> str | None:
    """把各种来源的 locale 字符串规范化为 BCP47 形（"zh_CN.UTF-8" → "zh-CN"）.

    无法识别时返回 None（由调用方继续走回退链）。
    """
    if not raw or not isinstance(raw, str):
        return None
    # 去掉 codeset 后缀（"zh_CN.UTF-8" → "zh_CN"）
    candidate = raw.strip().split(".", 1)[0]
    match = _BCP47_RE.match(candidate)
    if not match:
        return None
    lang, region = match.group(1), match.group(2)
    if region:
        return f"{lang.lower()}-{region.upper()}"
    return lang.lower()


def _detect_via_windows_api() -> str | None:
    """Windows：ctypes 调 kernel32 用户 UI 语言接口（非 Windows 返回 None）.

    首选 GetUserDefaultLocaleName（直接返回 "zh-CN" 形式，Vista+）；
    失败回退 GetUserDefaultUILanguage 的 LANGID 手工映射。
    两个接口都是当前用户态调用，无需管理员权限。
    """
    if os.name != "nt":
        return None
    try:
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        buf = ctypes.create_unicode_buffer(_LOCALE_NAME_MAX_LENGTH)
        if kernel32.GetUserDefaultLocaleName(buf, _LOCALE_NAME_MAX_LENGTH) > 0 and buf.value:
            return buf.value
    except Exception:
        pass

    # 回退：LANGID（低 10 位主语言 + 高 6 位子语言）→ 常见 locale 映射
    try:
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        lang_id = int(kernel32.GetUserDefaultUILanguage()) & 0xFFFF
        mapped = _LANGID_TO_LOCALE.get(lang_id)
        if mapped:
            return mapped
        return _PRIMARY_LANG_TO_CODE.get(lang_id & 0x03FF)
    except Exception:
        return None


def _detect_via_defaultlocale() -> str | None:
    """stdlib locale.getdefaultlocale()（3.12+ 弃用，仅作回退，警告抑制）."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        lang, _encoding = locale.getdefaultlocale()
    return lang or None


def _detect_via_env() -> str | None:
    """环境变量回退：LC_ALL 优先于 LANG（POSIX 惯例）."""
    return os.environ.get("LC_ALL") or os.environ.get("LANG") or None


@functools.lru_cache(maxsize=1)
def detect_system_locale() -> str:
    """探测系统 locale，进程内缓存（结果在进程生命周期内不变）.

    Returns:
        BCP47 规范形字符串（如 "zh-CN" / "en-US"）；全部探测失败时 "zh-CN"。
    """
    for probe in (
        _detect_via_windows_api,
        _detect_via_defaultlocale,
        _detect_via_env,
    ):
        try:
            normalized = _normalize_bcp47(probe())
        except Exception:
            continue
        if normalized:
            return normalized
    return _DEFAULT_LOCALE


def system_lang_key(locale_str: str | None = None) -> str:
    """把 locale 映射到语音栈支持的语言键 {"zh", "en", "ja", "ko", "yue"}.

    Args:
        locale_str: BCP47/locale 字符串；None 时自动探测系统 locale。

    Returns:
        "zh" / "en" / "ja" / "ko" / "yue"；无法识别时回落 "zh"（产品默认语言）。
    """
    if not locale_str:
        locale_str = detect_system_locale()
    normalized = _normalize_bcp47(locale_str) or ""
    key = normalized.lower()
    # 繁中区域优先映射粤语键（zh-TW/zh-HK），其余中文统一 zh
    if key.startswith(("zh-tw", "zh-hk")):
        return "yue"
    for supported in ("zh", "en", "ja", "ko"):
        if key.startswith(supported):
            return supported
    return "zh"
