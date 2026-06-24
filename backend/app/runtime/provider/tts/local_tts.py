"""Local TTS Provider - 使用 pyttsx3 系统语音合成（离线兜底方案）.

通过 subprocess 隔离 pyttsx3，避免 SAPI5 的 COM 事件循环与 asyncio 冲突
导致事件循环卡死。参考: super-agent-party 的 systemtts 实现.
"""

import asyncio
import os
import sys
import tempfile

from loguru import logger

from app.runtime.provider.base import TTSProvider


# Voice selection keywords grouped by language.
_VOICE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "zh": ("chinese", "huihui", "kangkang", "yaoyao", "hanhan", "zh-cn"),
    "ja": ("japanese", "ja-jp", "haruka", "ayumi", "naoki"),
    "en": ("english", "en-us", "zira", "david", "mark"),
}


# 内联 worker 脚本：在独立进程中运行 pyttsx3，避免 COM 事件循环冲突
_WORKER_SCRIPT = r"""
import sys
import pyttsx3

text = sys.argv[1]
out_path = sys.argv[2]
voice_hint = sys.argv[3] if len(sys.argv) > 3 else "default"
keywords = %r

engine = pyttsx3.init()
voices = engine.getProperty("voices")

voice_id_by_lang = {}
for v in voices:
    name = v.name.lower()
    for lang, kws in keywords.items():
        if lang in voice_id_by_lang:
            continue
        if any(kw in name for kw in kws):
            voice_id_by_lang[lang] = v.id
            break

resolved = None
if voice_hint and voice_hint != "default":
    if voice_hint in voice_id_by_lang:
        resolved = voice_id_by_lang[voice_hint]
    else:
        for v in voices:
            if v.id == voice_hint:
                resolved = voice_hint
                break
if not resolved:
    resolved = voice_id_by_lang.get("zh") or (voices[0].id if voices else None)

if resolved:
    engine.setProperty("voice", resolved)
engine.setProperty("rate", 170)
engine.save_to_file(text, out_path)
engine.runAndWait()
""" % _VOICE_KEYWORDS


class LocalTTSProvider(TTSProvider):
    """本地 pyttsx3 TTS Provider（通过 subprocess 隔离运行）."""

    provider_name = "local"

    @classmethod
    def is_available(cls) -> bool:
        """检查 pyttsx3 是否已安装."""
        try:
            import pyttsx3  # noqa: F401
            return True
        except ImportError:
            return False

    def __init__(self, **kwargs):
        self._all_voices: list[dict] = []
        self._voice_id_by_lang: dict[str, str] = {}
        self._initialized = False

    def _init_voices(self):
        """枚举系统语音（在主进程中执行，仅用于列表展示）."""
        if self._initialized:
            return
        try:
            import pyttsx3
            engine = pyttsx3.init()
            voices = engine.getProperty("voices")
            for v in voices:
                name = v.name.lower()
                self._all_voices.append({"id": v.id, "name": v.name})
                for lang, keywords in _VOICE_KEYWORDS.items():
                    if lang in self._voice_id_by_lang:
                        continue
                    if any(kw in name for kw in keywords):
                        self._voice_id_by_lang[lang] = v.id
                        break
            logger.info(
                f"[LocalTTS] Enumerated {len(voices)} voices, "
                f"lang map={self._voice_id_by_lang}"
            )
        except Exception as e:
            logger.warning(f"[LocalTTS] Voice enumeration failed: {e}")
        finally:
            self._initialized = True

    async def synthesize(self, text: str, voice: str = "default") -> bytes:
        if not text.strip():
            return b""

        # 用 subprocess 隔离 pyttsx3，避免 SAPI5 COM 事件循环卡死 asyncio
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            python_exe = sys.executable
            proc = await asyncio.create_subprocess_exec(
                python_exe, "-c", _WORKER_SCRIPT, text, tmp_path, voice,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15.0)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                raise RuntimeError("Local TTS subprocess timed out (15s)")

            if proc.returncode != 0:
                err_msg = stderr.decode("utf-8", errors="replace") if stderr else "unknown"
                raise RuntimeError(f"Local TTS subprocess failed: {err_msg}")

            if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
                raise RuntimeError("Local TTS produced empty audio file")

            with open(tmp_path, "rb") as f:
                return f.read()
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def list_voices(self) -> list[dict]:
        if not self._all_voices:
            self._init_voices()
        return list(self._all_voices)

    def get_lang_map(self) -> dict[str, str]:
        if not self._voice_id_by_lang:
            self._init_voices()
        return dict(self._voice_id_by_lang)
