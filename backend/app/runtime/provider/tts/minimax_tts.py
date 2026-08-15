"""MiniMax TTS Provider - 通过 MiniMax T2A v2 API 调用语音合成.

使用 httpx 调用 REST API，返回 hex 编码的音频数据.
支持语速、音量、音调调节，默认输出 MP3 格式.
"""

import httpx
from loguru import logger

from app.runtime.provider.engine_capabilities import EngineCapabilities
from app.runtime.provider.tts.ports import TTSProvider


# MiniMax 预置音色
MINIMAX_TTS_VOICES = [
    {"id": "English_Graceful_Lady", "name": "English Graceful Lady (英文优雅女声)"},
    {"id": "English_Trustworth_Man", "name": "English Trustworth Man (英文可靠男声)"},
    {"id": "Chinese_Gentle_Lady", "name": "Chinese Gentle Lady (中文温柔女声)"},
    {"id": "Chinese_Serene_Man", "name": "Chinese Serene Man (中文沉稳男声)"},
    {"id": "Chinese_Expressive_Girl", "name": "Chinese Expressive Girl (中文活泼女孩)"},
    {"id": "Chinese_Fresh_Girl", "name": "Chinese Fresh Girl (中文清新女声)"},
    {"id": "Chinese_Smooth_Sister", "name": "Chinese Smooth Sister (中文流畅姐姐)"},
    {"id": "Chinese_Warm_Sister", "name": "Chinese Warm Sister (中文温暖姐姐)"},
    {"id": "Japanese_Calm_Woman", "name": "Japanese Calm Woman (日文冷静女声)"},
    {"intelligent": "intelligent", "name": "Intelligent (智能音色，需配合 model)"},
]


class MiniMaxTTSProvider(TTSProvider):
    """MiniMax TTS Provider（通过 REST API 调用）."""

    provider_name = "minimax"

    DEFAULT_VOICES = {
        "zh": "Chinese_Gentle_Lady",
        "en": "English_Graceful_Lady",
    }

    DEFAULT_MODEL = "speech-2.8-hd"
    DEFAULT_BASE_URL = "https://api.minimax.io/v1/t2a_v2"

    # 引擎能力声明（G1/G2 治理）
    CAPABILITIES = EngineCapabilities(
        engine_id="minimax",
        name="MiniMax TTS（高质量）",
        kind="cloud",
        category="cloud-paid",
        needs_api_key=True,
        online=True,
        languages=("zh", "en", "ja"),
        voices=[
            {"value": "English_Graceful_Lady", "label": "English Graceful Lady（英文优雅女声）", "langs": ["en"]},
            {"value": "English_Trustworth_Man", "label": "English Trustworth Man（英文可靠男声）", "langs": ["en"]},
            {"value": "Chinese_Gentle_Lady", "label": "Chinese Gentle Lady（中文温柔女声）", "langs": ["zh"]},
            {"value": "Chinese_Serene_Man", "label": "Chinese Serene Man（中文沉稳男声）", "langs": ["zh"]},
            {"value": "Chinese_Expressive_Girl", "label": "Chinese Expressive Girl（中文活泼女孩）", "langs": ["zh"]},
            {"value": "Chinese_Fresh_Girl", "label": "Chinese Fresh Girl（中文清新女声）", "langs": ["zh"]},
            {"value": "Japanese_Calm_Woman", "label": "Japanese Calm Woman（日文冷静女声）", "langs": ["ja"]},
        ],
        default_voice="Chinese_Gentle_Lady",
        models=["speech-2.8-hd"],
        default_model="speech-2.8-hd",
        description="MiniMax T2A v2，高质量云语音，支持语速/音量/音调调节",
    )

    @classmethod
    def is_available(cls) -> bool:
        """httpx 是项目核心依赖，始终可用."""
        return True

    def __init__(self, **kwargs):
        self.api_key = kwargs.get("apiKey", "")
        if not self.api_key:
            raise ValueError("MiniMax TTS 需要 apiKey 配置")

        self.model = kwargs.get("model") or self.DEFAULT_MODEL
        self.voice = kwargs.get("voice") or "English_Graceful_Lady"
        self.speed = float(kwargs.get("speed", 1.0))
        self.vol = float(kwargs.get("vol", 1.0))
        self.pitch = int(kwargs.get("pitch", 0))
        self.base_url = kwargs.get("baseUrl") or self.DEFAULT_BASE_URL

    async def synthesize(self, text: str, voice: str = "default") -> bytes:
        if voice == "default" or not voice:
            voice = self.voice
        elif voice in self.DEFAULT_VOICES:
            voice = self.DEFAULT_VOICES[voice]

        payload = {
            "model": self.model,
            "text": text,
            "stream": False,
            "voice_setting": {
                "voice_id": voice,
                "speed": self.speed,
                "vol": self.vol,
                "pitch": self.pitch,
            },
            "audio_setting": {
                "sample_rate": 32000,
                "bitrate": 128000,
                "format": "mp3",
                "channel": 1,
            },
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        # 统一超时治理（应急修复 B3）：硬编码 → Settings.TTS_HTTP_TIMEOUT
        from app.core.config import settings as _settings

        async with httpx.AsyncClient(timeout=_settings.TTS_HTTP_TIMEOUT) as client:
            response = await client.post(self.base_url, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()

        # 检查状态码
        base_resp = result.get("base_resp", {})
        status_code = base_resp.get("status_code", -1)
        if status_code != 0:
            status_msg = base_resp.get("status_msg", "unknown error")
            raise RuntimeError(f"MiniMax TTS API 错误 (code {status_code}): {status_msg}")

        # MiniMax 返回 hex 编码的音频数据（不是 base64）
        hex_audio = result.get("data", {}).get("audio", "")
        if not hex_audio:
            raise RuntimeError("MiniMax TTS 返回空音频数据")

        audio_bytes = bytes.fromhex(hex_audio)

        logger.info(f"[MiniMaxTTS] synthesized: {text[:60]}... (voice={voice})")
        return audio_bytes
