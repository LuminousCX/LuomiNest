"""SiliconFlow TTS Provider - 通过 SiliconFlow OpenAI 兼容 TTS API 调用语音合成.

使用 httpx 调用 REST API，返回二进制音频数据.
默认使用 CosyVoice2-0.5B 模型，支持自定义模型和音色.
"""

import httpx
from loguru import logger

from app.runtime.provider.tts.ports import TTSProvider


# SiliconFlow TTS 预置音色（CosyVoice2 系列）
SILICONFLOW_TTS_VOICES = [
    {"id": "FunAudioLLM/CosyVoice2-0.5B:alex", "name": "Alex (英文男声)"},
    {"id": "FunAudioLLM/CosyVoice2-0.5B:benjamin", "name": "Benjamin (英文男声)"},
    {"id": "FunAudioLLM/CosyVoice2-0.5B:bella", "name": "Bella (英文女声)"},
    {"id": "FunAudioLLM/CosyVoice2-0.5B:claire", "name": "Claire (英文女声)"},
    {"id": "FunAudioLLM/CosyVoice2-0.5B:david", "name": "David (英文男声)"},
    {"id": "FunAudioLLM/CosyVoice2-0.5B:diana", "name": "Diana (英文女声)"},
    {"id": "FunAudioLLM/CosyVoice2-0.5B:emily", "name": "Emily (英文女声)"},
    {"id": "FunAudioLLM/CosyVoice2-0.5B:fred", "name": "Fred (英文男声)"},
    {"id": "FunAudioLLM/CosyVoice2-0.5B:grace", "name": "Grace (英文女声)"},
    {"id": "FunAudioLLM/CosyVoice2-0.5B:henry", "name": "Henry (英文男声)"},
]


class SiliconFlowTTSProvider(TTSProvider):
    """SiliconFlow TTS Provider（OpenAI 兼容 TTS API）."""

    provider_name = "siliconflow"

    DEFAULT_VOICES = {
        "zh": "FunAudioLLM/CosyVoice2-0.5B:alex",
        "en": "FunAudioLLM/CosyVoice2-0.5B:alex",
    }

    DEFAULT_MODEL = "FunAudioLLM/CosyVoice2-0.5B"
    DEFAULT_BASE_URL = "https://api.siliconflow.cn/v1/audio/speech"

    @classmethod
    def is_available(cls) -> bool:
        """httpx 是项目核心依赖，始终可用."""
        return True

    def __init__(self, **kwargs):
        self.api_key = kwargs.get("apiKey", "")
        if not self.api_key:
            raise ValueError("SiliconFlow TTS 需要 apiKey 配置")

        self.model = kwargs.get("model") or self.DEFAULT_MODEL
        self.voice = kwargs.get("voice") or "FunAudioLLM/CosyVoice2-0.5B:alex"
        self.speed = float(kwargs.get("speed", 1.0))
        self.base_url = kwargs.get("baseUrl") or self.DEFAULT_BASE_URL

    async def synthesize(self, text: str, voice: str = "default") -> bytes:
        if voice == "default" or not voice:
            voice = self.voice
        elif voice in self.DEFAULT_VOICES:
            voice = self.DEFAULT_VOICES[voice]

        payload = {
            "input": text,
            "model": self.model,
            "voice": voice,
            "response_format": "wav",
            "sample_rate": 24000,
            "stream": False,
            "speed": self.speed,
            "gain": 0,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(self.base_url, json=payload, headers=headers)
            response.raise_for_status()

            # SiliconFlow 返回二进制音频数据
            audio_bytes = response.content

        if not audio_bytes:
            raise RuntimeError("SiliconFlow TTS 返回空音频数据")

        logger.info(f"[SiliconFlowTTS] synthesized: {text[:60]}... (voice={voice})")
        return audio_bytes
