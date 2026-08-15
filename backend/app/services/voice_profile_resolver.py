"""VoiceProfileResolver — 语音画像解析链（voice-model-market.md §7.3/§8.2，G5 治理）。

解析优先级：请求参数 > 皮套绑定(avatar binding) > 全局默认(voice_config)
语言感知：TTSRequest.lang=auto 时按文本字符集探测（L3），指定时过滤引擎（L4）

输出 VoiceProfile → 交给 LuminousChenXiTTSRegistry.resolve(engine, lang, **config)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from app.runtime.provider.engine_capabilities import LANGUAGE_LABELS, SUPPORTED_TTS_LANGUAGES


@dataclass
class VoiceProfile:
    """解析后的语音画像（交给 Registry 实例化引擎）."""

    engine: str = "auto"
    model: str = ""
    voice: str = ""
    lang: str = "auto"
    speed: float = 1.0
    api_key: str = ""
    base_url: str = ""
    # 画像来源（审计/日志用）
    source: str = "global"  # request | avatar_binding | global

    def to_config_kwargs(self) -> dict[str, Any]:
        """转为引擎构造 kwargs（仅非空值，避免覆盖引擎默认）."""
        config: dict[str, Any] = {}
        if self.model:
            config["model"] = self.model
        if self.speed and self.speed != 1.0:
            config["speed"] = self.speed
        if self.api_key:
            config["apiKey"] = self.api_key
        if self.base_url:
            config["baseUrl"] = self.base_url
        if self.voice and self.voice != "default":
            config["voice"] = self.voice
        return config


# ---------------------------------------------------------------------------
# 语言探测（解析链 L3：lang=auto 时按文本字符集）
# ---------------------------------------------------------------------------

# 平假名 + 片假名 Unicode 区间
_KANA_RE = re.compile(r"[\u3040-\u309F\u30A0-\u30FF]")
# 谚文（韩文）
_HANGUL_RE = re.compile(r"[\uAC00-\uD7AF\u1100-\u11FF]")
# CJK 统一汉字（中日共用，需结合假名占比区分 ja）
_HAN_RE = re.compile(r"[\u4E00-\u9FFF]")
# 拉丁字母
_LATIN_RE = re.compile(r"[A-Za-z]")


def detect_lang_from_text(text: str, default: str = "zh") -> str:
    """按文本字符集探测语言（启发式，与 STT 的 language hint 无关）.

    规则：
    - 含假名 → ja（假名是日语独有标志）
    - 含谚文 → ko
    - 汉字占优（无假名/谚文）→ zh
    - 拉丁字母占优 → en
    - 空文本/无法判定 → default
    """
    if not text or not text.strip():
        return default

    if _KANA_RE.search(text):
        return "ja"
    if _HANGUL_RE.search(text):
        return "ko"

    han_count = len(_HAN_RE.findall(text))
    latin_count = len(_LATIN_RE.findall(text))
    if han_count == 0 and latin_count == 0:
        return default
    if han_count >= latin_count:
        return "zh"
    return "en"


class LuomiNestVoiceProfileResolver:
    """语音画像解析器（请求参数 > 皮套绑定 > 全局默认）."""

    def __init__(self) -> None:
        self._config_store = None

    @property
    def config_store(self):
        """懒加载 voice_config_store（避免 import 期触库）."""
        if self._config_store is None:
            from app.services.voice_config_store import luominest_voice_config_store

            self._config_store = luominest_voice_config_store
        return self._config_store

    # ------------------------------------------------------------------
    # TTS 画像解析
    # ------------------------------------------------------------------

    def resolve_tts(
        self,
        *,
        # 请求级参数（显式非空才生效）
        engine: str | None = None,
        model: str | None = None,
        voice: str | None = None,
        lang: str | None = None,
        speed: float | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        # 场景上下文
        avatar_model_id: str | None = None,
        text: str = "",
    ) -> VoiceProfile:
        """解析 TTS 画像：请求参数 > 皮套绑定 > 全局默认 + 语言感知.

        Args:
            engine/model/voice/lang/speed/api_key/base_url: 请求显式参数（非空覆盖画像）
            avatar_model_id: 皮套模型 ID（如 "llny"），触发皮套绑定查询
            text: 待合成文本（lang=auto 时探测）
        """
        global_config = self.config_store.get_voice_config()
        global_tts = global_config.get("tts") or {}

        profile = VoiceProfile(
            engine=global_tts.get("engine") or "auto",
            model=global_tts.get("model") or "",
            voice=global_tts.get("voice") or "",
            lang=global_tts.get("lang") or "auto",
            speed=float(global_tts.get("speed") or 1.0),
            source="global",
        )

        # 2) 皮套绑定（avatar 场景）
        if avatar_model_id:
            binding = self.config_store.get_avatar_binding(avatar_model_id)
            if binding:
                profile.engine = binding.get("engine") or profile.engine
                profile.voice = binding.get("voice") or profile.voice
                if binding.get("voice_lang"):
                    profile.lang = binding["voice_lang"]
                if binding.get("model"):
                    profile.model = binding["model"]
                profile.source = "avatar_binding"

        # 1) 请求显式参数（最高优先级）
        if engine:
            profile.engine = engine
        if model:
            profile.model = model
        if voice and voice != "default":
            profile.voice = voice
        if lang:
            profile.lang = lang
        if speed is not None:
            profile.speed = speed
        if api_key:
            profile.api_key = api_key
        if base_url:
            profile.base_url = base_url

        # 3) 语言感知（解析链 L3）：auto + 有文本 → 字符集探测
        if profile.lang == "auto" and text:
            profile.lang = detect_lang_from_text(text)

        # 语言合法性校验
        if profile.lang not in SUPPORTED_TTS_LANGUAGES:
            logger.warning(f"[VoiceProfileResolver] unknown lang [{profile.lang}], fallback to zh")
            profile.lang = "zh"

        logger.debug(
            f"[VoiceProfileResolver] tts profile: engine={profile.engine} "
            f"voice={profile.voice} lang={profile.lang} model={profile.model} "
            f"source={profile.source}"
        )
        return profile

    # ------------------------------------------------------------------
    # 音色语言校验（解析链 L2：音色前缀判定）
    # ------------------------------------------------------------------

    @staticmethod
    def infer_voice_lang(voice: str) -> str | None:
        """从音色名推断语言（如 ja-JP-NanamiNeural → ja；zh-female → zh）."""
        if not voice:
            return None
        prefix = voice.split("-")[0].lower()
        mapping = {
            "zh": "zh",
            "en": "en",
            "ja": "ja",
            "ko": "ko",
            "yue": "yue",
            "zh_cn": "zh",
            "en_us": "en",
            "ja_jp": "ja",
            "ko_kr": "ko",
        }
        return mapping.get(prefix)


# ── 单例 ──

luominest_voice_profile_resolver = LuomiNestVoiceProfileResolver()
