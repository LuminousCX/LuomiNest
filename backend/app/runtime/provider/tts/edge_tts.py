import io
import os
import edge_tts
from app.runtime.provider.base import TTSProvider


class EdgeTTSProvider(TTSProvider):
    provider_name = "edge-tts"

    DEFAULT_VOICES = {
        "zh": "zh-CN-XiaoxiaoNeural",
        "en": "en-US-JennyNeural",
        "ja": "ja-JP-NanamiNeural",
    }

    def __init__(self, proxy: str | None = None):
        self.proxy = proxy or os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or None

    async def synthesize(self, text: str, voice: str = "default") -> bytes:
        if voice == "default" or not voice:
            voice = self.DEFAULT_VOICES.get("zh", "zh-CN-XiaoxiaoNeural")
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
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    buffer.write(chunk["data"])
        except Exception as e:
            raise RuntimeError(
                f"Failed during TTS streaming (voice={voice}, text_len={len(text)}): {e}"
            ) from e

        buffer.seek(0)
        return buffer.read()
