import io
import edge_tts
from app.runtime.provider.base import TTSProvider


class EdgeTTSProvider(TTSProvider):
    provider_name = "edge-tts"

    DEFAULT_VOICES = {
        "zh": "zh-CN-XiaoxiaoNeural",
        "en": "en-US-JennyNeural",
    }

    async def synthesize(self, text: str, voice: str = "default") -> bytes:
        if voice == "default" or not voice:
            voice = self.DEFAULT_VOICES.get("zh", "zh-CN-XiaoxiaoNeural")

        communicate = edge_tts.Communicate(text, voice)
        buffer = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                buffer.write(chunk["data"])
        buffer.seek(0)
        return buffer.read()
