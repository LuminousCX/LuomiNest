"""Sherpa-ONNX TTS Provider - 完全离线的神经网络 TTS 引擎.

使用 vits-melo-tts-zh_en 模型，支持中英文，纯 CPU 推理，无需网络连接.
参考: Open-LLM-VTuber 的 sherpa_onnx_tts.py 实现.
"""

import asyncio
import io
import os
from pathlib import Path

import soundfile as sf
from loguru import logger

from app.runtime.provider.base import TTSProvider


# 模型目录（相对于 backend 根目录）
_DEFAULT_MODEL_DIR = Path(__file__).resolve().parents[4] / "models" / "tts" / "vits-melo-tts-zh_en"


class SherpaOnnxTTSProvider(TTSProvider):
    """Sherpa-ONNX 离线 TTS Provider（单例）."""

    provider_name = "sherpa-onnx"
    _instance = None
    _tts_engine = None

    DEFAULT_VOICES = {
        "zh": "zh-female",
        "en": "en-female",
    }

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, model_dir: str | Path | None = None, num_threads: int = 2, speed: float = 1.0):
        if self._tts_engine is not None:
            return
        import sherpa_onnx

        model_dir = Path(model_dir) if model_dir else _DEFAULT_MODEL_DIR
        self._model_dir = model_dir
        self._speed = speed
        self._num_threads = num_threads

        model_path = model_dir / "model.onnx"
        if not model_path.exists():
            raise FileNotFoundError(
                f"Sherpa-ONNX TTS model not found: {model_path}. "
                f"Please download vits-melo-tts-zh_en from "
                f"https://github.com/k2-fsa/sherpa-onnx/releases/tag/tts-models"
            )

        tts_config = sherpa_onnx.OfflineTtsConfig(
            model=sherpa_onnx.OfflineTtsModelConfig(
                vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                    model=str(model_path),
                    lexicon=str(model_dir / "lexicon.txt"),
                    tokens=str(model_dir / "tokens.txt"),
                ),
                provider="cpu",
                num_threads=num_threads,
                debug=False,
            ),
            rule_fsts=",".join([
                str(model_dir / "number.fst"),
                str(model_dir / "phone.fst"),
                str(model_dir / "date.fst"),
                str(model_dir / "new_heteronym.fst"),
            ]),
            max_num_sentences=2,
        )

        if not tts_config.validate():
            raise ValueError("Sherpa-ONNX TTS config validation failed")

        self._tts_engine = sherpa_onnx.OfflineTts(tts_config)
        self._sample_rate = self._tts_engine.sample_rate
        logger.info(
            f"[SherpaOnnxTTS] Initialized: model={model_path.name}, "
            f"sample_rate={self._sample_rate}, threads={num_threads}"
        )

    async def synthesize(self, text: str, voice: str = "default") -> bytes:
        if not text.strip():
            return b""

        # sherpa-onnx 的 generate 是同步 CPU 密集操作，用 to_thread 避免阻塞事件循环
        audio_samples = await asyncio.to_thread(self._generate_sync, text)

        buffer = io.BytesIO()
        sf.write(buffer, audio_samples, samplerate=self._sample_rate, subtype="PCM_16", format="WAV")
        buffer.seek(0)
        return buffer.read()

    def _generate_sync(self, text: str) -> list[float]:
        audio = self._tts_engine.generate(text, sid=0, speed=self._speed)
        if len(audio.samples) == 0:
            raise RuntimeError("Sherpa-ONNX TTS generated empty audio")
        return audio.samples
