"""Gemini TTS Provider - 通过 Google Generative Language REST API 调用 Gemini TTS.

使用 httpx 直接调用 REST API，无需安装 google-genai SDK.
返回 PCM 24kHz 16-bit 单声道数据，包装为 WAV 格式.
"""

import base64
import io
import wave

import httpx
from loguru import logger

from app.runtime.provider.engine_capabilities import EngineCapabilities
from app.runtime.provider.tts.ports import TTSProvider


# Gemini TTS 预置音色（30 种）
GEMINI_TTS_VOICES = [
    "Leda", "Puck", "Charon", "Aoede", "Fenrir", "Kore",
    "Orus", "Zephyr", "Sulochan", "Algenib", "Achernar", "Aldebaran",
    "Bellatrix", "Castor", "Pollux", "Rasalgethi", "Vindemiatrix",
    "Zubenelgenubi", "Autonoe", "Callirrhoe", "Despina", "Erinome",
    "Laomedeia", "Pasithee", "Polyxena", "Spica", "Tarqeq",
    "Thalassa", "Naiad", "Sao",
]


class GeminiTTSProvider(TTSProvider):
    """Gemini TTS Provider（通过 REST API 调用，无需 SDK）."""

    provider_name = "gemini"

    DEFAULT_VOICES = {
        "zh": "Leda",
        "en": "Puck",
    }

    DEFAULT_MODEL = "gemini-2.5-flash-preview-tts"
    DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    # 引擎能力声明（G1/G2 治理）：Gemini TTS 音色多语言，均可合成 zh/en/ja
    CAPABILITIES = EngineCapabilities(
        engine_id="gemini",
        name="Gemini TTS（Google·免费层）",
        kind="cloud",
        category="cloud-paid",
        needs_api_key=True,
        online=True,
        languages=("zh", "en", "ja"),
        voices=[{"value": v, "label": v, "langs": ["zh", "en", "ja"]} for v in GEMINI_TTS_VOICES[:15]],
        default_voice="Leda",
        models=["gemini-2.5-flash-preview-tts"],
        default_model="gemini-2.5-flash-preview-tts",
        description="Google Gemini TTS，30 种预置音色，多语言合成，需 API Key",
    )

    @classmethod
    def is_available(cls) -> bool:
        """httpx 是项目核心依赖，始终可用."""
        return True

    def __init__(self, **kwargs):
        self.api_key = kwargs.get("apiKey", "")
        if not self.api_key:
            raise ValueError("Gemini TTS 需要 apiKey 配置")

        self.model = kwargs.get("model") or self.DEFAULT_MODEL
        self.voice = kwargs.get("voice") or "Leda"
        self.base_url = (kwargs.get("baseUrl") or self.DEFAULT_BASE_URL).rstrip("/")

    async def synthesize(self, text: str, voice: str = "default") -> bytes:
        if voice == "default" or not voice:
            voice = self.voice
        elif voice in self.DEFAULT_VOICES:
            voice = self.DEFAULT_VOICES[voice]

        url = f"{self.base_url}/models/{self.model}:generateContent"

        payload = {
            "contents": [{"parts": [{"text": text}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {
                            "voiceName": voice,
                        },
                    },
                },
            },
        }

        params = {"key": self.api_key}

        # 统一超时治理（应急修复 B3）：硬编码 → Settings.TTS_HTTP_TIMEOUT
        from app.core.config import settings as _settings

        async with httpx.AsyncClient(timeout=_settings.TTS_HTTP_TIMEOUT) as client:
            response = await client.post(url, json=payload, params=params)
            response.raise_for_status()
            result = response.json()

        # 提取 base64 编码的 PCM 数据
        try:
            candidates = result.get("candidates", [])
            if not candidates:
                raise RuntimeError("Gemini TTS 返回空响应")

            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts:
                raise RuntimeError("Gemini TTS 返回无音频内容")

            inline_data = parts[0].get("inlineData") or parts[0].get("inline_data")
            if not inline_data:
                raise RuntimeError("Gemini TTS 返回无 inlineData")

            pcm_b64 = inline_data.get("data", "")
            if not pcm_b64:
                raise RuntimeError("Gemini TTS 返回空音频数据")

        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Gemini TTS 响应解析失败: {e}")

        # 解码 base64 PCM 并包装为 WAV
        pcm_bytes = base64.b64decode(pcm_b64)
        wav_bytes = self._pcm_to_wav(pcm_bytes)

        logger.info(f"[GeminiTTS] synthesized: {text[:60]}... (voice={voice})")
        return wav_bytes

    @staticmethod
    def _pcm_to_wav(pcm: bytes, channels: int = 1, sample_width: int = 2, framerate: int = 24000) -> bytes:
        """将原始 PCM 数据包装为 WAV 格式."""
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(framerate)
            wf.writeframes(pcm)
        buffer.seek(0)
        return buffer.read()
