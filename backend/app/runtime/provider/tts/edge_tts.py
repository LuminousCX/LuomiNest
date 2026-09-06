import io
import os
import edge_tts
from app.core.constants.voice import DEFAULT_EDGE_VOICE
from app.runtime.provider.engine_capabilities import EngineCapabilities
from app.runtime.provider.tts.ports import TTSProvider


class EdgeTTSProvider(TTSProvider):
    provider_name = "edge-tts"

    DEFAULT_VOICES = {
        "zh": DEFAULT_EDGE_VOICE,
        "en": "en-US-JennyNeural",
        "ja": "ja-JP-NanamiNeural",
    }

    # 引擎能力声明（G1/G2 治理：元数据收敛为类属性，替代 voice.py/前端硬编码）
    CAPABILITIES = EngineCapabilities(
        engine_id="edge-tts",
        name="Edge TTS（在线·免费）",
        kind="cloud",
        category="cloud-free",
        needs_api_key=False,
        online=True,
        languages=("zh", "en", "ja", "ko", "yue"),
        voices=[
            {"value": DEFAULT_EDGE_VOICE, "label": "晓晓（女·温柔）", "langs": ["zh"]},
            {"value": "zh-CN-YunxiNeural", "label": "云希（男·阳光）", "langs": ["zh"]},
            {"value": "zh-CN-YunjianNeural", "label": "云健（男·沉稳）", "langs": ["zh"]},
            {"value": "zh-CN-XiaoyiNeural", "label": "晓艺（女·活泼）", "langs": ["zh"]},
            {"value": "en-US-JennyNeural", "label": "Jenny（EN·Female）", "langs": ["en"]},
            {"value": "en-US-GuyNeural", "label": "Guy（EN·Male）", "langs": ["en"]},
            {"value": "ja-JP-NanamiNeural", "label": "七海（JA·Female）", "langs": ["ja"]},
            {"value": "ja-JP-KeitaNeural", "label": "圭太（JA·Male）", "langs": ["ja"]},
        ],
        default_voice=DEFAULT_EDGE_VOICE,
        description="微软免费神经语音，多语言，开箱默认引擎",
    )

    @classmethod
    def is_available(cls) -> bool:
        """检查 edge-tts 是否已安装."""
        try:
            import edge_tts  # noqa: F401
            return True
        except ImportError:
            return False

    def __init__(self, **kwargs):
        proxy = kwargs.get("proxy") or os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or None
        self.proxy = proxy

    async def synthesize(self, text: str, voice: str = "default") -> bytes:
        import asyncio

        from app.core.config import settings

        if voice == "default" or not voice:
            voice = self.DEFAULT_VOICES.get("zh", DEFAULT_EDGE_VOICE)
        # Allow callers to pass a language code ('zh'/'ja'/'en') instead of a full voice name.
        elif voice in self.DEFAULT_VOICES:
            voice = self.DEFAULT_VOICES[voice]

        try:
            communicate = edge_tts.Communicate(text, voice, proxy=self.proxy)
        except Exception as e:
            raise RuntimeError(
                f"Failed to create Communicate (voice={voice}, text_len={len(text)}): {e}"
            ) from e

        buffer = io.BytesIO()
        try:
            # 统一超时治理（应急修复 B3）：edge_tts 库自身无超时，此处包 asyncio.wait_for 防无限挂起
            async def _drain() -> bytes:
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        buffer.write(chunk["data"])
                buffer.seek(0)
                return buffer.read()

            return await asyncio.wait_for(_drain(), timeout=settings.TTS_HTTP_TIMEOUT)
        except asyncio.TimeoutError:
            raise RuntimeError(
                f"Edge TTS 合成超时（>{settings.TTS_HTTP_TIMEOUT}s，voice={voice}），请检查网络或更换引擎"
            ) from None
        except Exception as e:
            raise RuntimeError(
                f"Failed during TTS streaming (voice={voice}, text_len={len(text)}): {e}"
            ) from e
