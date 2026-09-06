"""LuomiNest STT 适配器公共基类.

收口三个 STT 适配器（faster_whisper / funasr / sherpa_onnx）逐字相同的部分：
- 16kHz 采样率常量
- ffmpeg 风格的音频解码（soundfile 读取 + 取第一声道 + 线性插值重采样）
- transcribe 异步外层包装（空输入短路 + asyncio.to_thread 卸载同步识别）

各适配器只需实现模型加载与 `_recognize_sync`（同步识别），
懒加载场景覆盖 `_prepare`，输出后处理覆盖 `_postprocess_text`。
"""

import asyncio
import io

import numpy as np
import soundfile as sf

from app.runtime.provider.stt.ports import STTProvider


class BaseSTTProvider(STTProvider):
    """STT 适配器公共基类（在 STTProvider 端口之下扩展）."""

    # 采样率
    _SAMPLE_RATE = 16000

    async def transcribe(self, audio_data: bytes, format: str = "wav") -> str:
        if not audio_data:
            return ""

        # 识别前准备（懒加载模型等，默认无操作）
        await self._prepare()

        # 解码音频
        audio_np = await asyncio.to_thread(self._decode_audio, audio_data, format)

        # 识别
        text = await asyncio.to_thread(self._recognize_sync, audio_np)

        return self._postprocess_text(text)

    async def _prepare(self) -> None:
        """识别前准备（首次调用时可能触发模型下载/加载），默认无操作."""

    def _postprocess_text(self, text: str) -> str:
        """识别文本后处理，默认原样返回."""
        return text

    def _decode_audio(self, audio_data: bytes, format: str) -> np.ndarray:
        """将音频 bytes 解码为 16kHz 单声道 numpy 数组."""
        buffer = io.BytesIO(audio_data)
        audio_np, sr = sf.read(buffer, dtype="float32")

        # 如果是多声道，取第一声道
        if audio_np.ndim > 1:
            audio_np = audio_np[:, 0]

        # 重采样到 16kHz（如果需要）
        if sr != self._SAMPLE_RATE:
            audio_np = self._resample(audio_np, sr, self._SAMPLE_RATE)

        return audio_np

    def _resample(self, audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        """简单线性插值重采样."""
        if orig_sr == target_sr:
            return audio
        ratio = target_sr / orig_sr
        n_samples = int(len(audio) * ratio)
        indices = np.arange(n_samples) / ratio
        indices = np.clip(indices, 0, len(audio) - 1)
        return np.interp(indices, np.arange(len(audio)), audio).astype(np.float32)
