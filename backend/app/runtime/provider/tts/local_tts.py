import io
import os
import tempfile
from app.runtime.provider.base import TTSProvider


class LocalTTSProvider(TTSProvider):
    provider_name = "local"

    def __init__(self):
        self._engine = None
        self._zh_voice_id = None

    def _get_engine(self):
        if self._engine is not None:
            return self._engine

        import pyttsx3
        engine = pyttsx3.init()
        voices = engine.getProperty("voices")
        for v in voices:
            name = v.name.lower()
            if any(kw in name for kw in ("chinese", "huihui", "kangkang", "yaoyao", "hanhan")):
                self._zh_voice_id = v.id
                break
        if self._zh_voice_id:
            engine.setProperty("voice", self._zh_voice_id)
        engine.setProperty("rate", 170)
        self._engine = engine
        return engine

    async def synthesize(self, text: str, voice: str = "default") -> bytes:
        import asyncio

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            engine = await asyncio.to_thread(self._get_engine)
            await asyncio.to_thread(engine.save_to_file, text, tmp_path)
            await asyncio.to_thread(engine.runAndWait)

            with open(tmp_path, "rb") as f:
                return f.read()
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
