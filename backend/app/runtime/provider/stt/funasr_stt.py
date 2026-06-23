"""FunASR STT Provider - 阿里达摩院语音识别引擎.

使用 funasr.AutoModel，支持 SenseVoice / Paraformer 等多种模型.
默认使用 SenseVoiceSmall 模型，中文识别效果优秀，支持情感识别.
模型首次使用时自动从 ModelScope 下载，也可手动放置到 backend/models/stt/ 目录.
参考: Open-LLM-VTuber 的 fun_asr.py 实现.
"""

import asyncio
import io
import re
from pathlib import Path

import numpy as np
import soundfile as sf
from loguru import logger

from app.runtime.provider.base import STTProvider


# 模型根目录（backend/models/stt/）
_MODEL_ROOT = Path(__file__).resolve().parents[4] / "models" / "stt"

# 采样率
_SAMPLE_RATE = 16000

# 模型别名到完整 ModelScope ID 的映射
MODEL_ALIAS_TO_FULL_ID = {
    "paraformer-zh": "iic/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
    "paraformer-zh-spk": "iic/speech_paraformer-large-vad-punc-spk_asr_nat-zh-cn",
    "paraformer-zh-online": "iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-online",
    "paraformer-en": "iic/speech_paraformer-large-vad-punc_asr_nat-en-16k-common-vocab10020",
    "conformer-en": "iic/speech_conformer_asr-en-16k-vocab4199-pytorch",
    "ct-punc": "iic/punc_ct-transformer_cn-en-common-vocab471067-large",
    "fsmn-vad": "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch",
    "fa-zh": "iic/speech_timestamp_prediction-v1-16k-offline",
    "SenseVoiceSmall": "iic/SenseVoiceSmall",
    "iic/SenseVoiceSmall": "iic/SenseVoiceSmall",
}


def _resolve_model_id(model_name: str) -> str:
    """将模型别名解析为完整的 ModelScope ID."""
    return MODEL_ALIAS_TO_FULL_ID.get(model_name, model_name)


def _clean_sense_voice_text(text: str) -> str:
    """去除 SenseVoice 输出的标签（如 <|zh|><|NEUTRAL|><|Speech|>）."""
    text = re.sub(r"<\|.*?\|>", "", text)
    text = re.sub(r"< \|.*?\| >", "", text)
    return text.strip()


class FunASRSTTProvider(STTProvider):
    """FunASR STT Provider（单例）.

    使用阿里达摩院 FunASR，默认加载 SenseVoiceSmall 模型.
    支持中英日韩多语言识别，中文效果优秀.
    模型首次使用时自动从 ModelScope 下载.
    """

    provider_name = "funasr"
    _instance = None
    _model = None
    _current_model_name = None

    # 支持的模型
    SUPPORTED_MODELS = list(MODEL_ALIAS_TO_FULL_ID.keys())

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        model_name: str = "iic/SenseVoiceSmall",
        language: str = "auto",
        vad_model: str | None = "fsmn-vad",
        punc_model: str | None = "ct-punc",
        ncpu: int | None = None,
        device: str = "cpu",
        use_itn: bool = True,
        disable_update: bool = True,
    ):
        # 如果模型已加载且名称没变，跳过
        if self._model is not None and self._current_model_name == model_name:
            return

        from funasr import AutoModel

        self._language = language
        self._use_itn = use_itn
        self._current_model_name = model_name

        # 解析模型 ID
        final_model = _resolve_model_id(model_name)
        final_vad = _resolve_model_id(vad_model) if vad_model else None
        final_punc = _resolve_model_id(punc_model) if punc_model else None

        logger.info(
            f"[FunASRSTT] Loading model: {final_model}, "
            f"vad={final_vad}, punc={final_punc}, device={device}"
        )

        self._model = AutoModel(
            model=final_model,
            vad_model=final_vad,
            punc_model=final_punc,
            ncpu=ncpu,
            hub="modelscope",
            device=device,
            disable_update=disable_update,
        )

        logger.info(
            f"[FunASRSTT] Initialized: model={model_name}, "
            f"language={language}, use_itn={use_itn}"
        )

    async def transcribe(self, audio_data: bytes, format: str = "wav") -> str:
        if not audio_data:
            return ""

        # 解码音频
        audio_np = await asyncio.to_thread(self._decode_audio, audio_data, format)

        # 识别
        text = await asyncio.to_thread(self._transcribe_sync, audio_np)

        return text

    def _decode_audio(self, audio_data: bytes, format: str) -> np.ndarray:
        """将音频 bytes 解码为 16kHz 单声道 numpy 数组."""
        buffer = io.BytesIO(audio_data)
        audio_np, sr = sf.read(buffer, dtype="float32")

        if audio_np.ndim > 1:
            audio_np = audio_np[:, 0]

        if sr != _SAMPLE_RATE:
            audio_np = self._resample(audio_np, sr, _SAMPLE_RATE)

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

    def _transcribe_sync(self, audio: np.ndarray) -> str:
        """同步识别音频."""
        import torch

        audio_tensor = torch.tensor(audio, dtype=torch.float32)

        res = self._model.generate(
            input=audio_tensor,
            batch_size_s=300,
            use_itn=self._use_itn,
            language=self._language,
        )

        if not res:
            return ""

        full_text = res[0]["text"]

        # 去除 SenseVoice 输出的标签
        full_text = _clean_sense_voice_text(full_text)

        return full_text

    @classmethod
    def is_available(cls) -> bool:
        """检查 funasr 是否已安装."""
        try:
            import funasr  # noqa: F401
            return True
        except ImportError:
            return False

    @classmethod
    def is_model_ready(cls) -> bool:
        """检查模型文件是否已就位（FunASR 通过 ModelScope 管理缓存，无法简单检测）."""
        # FunASR 模型缓存在用户目录下，首次使用时会自动下载
        # 这里返回 True，让 is_available 判断即可
        return cls.is_available()
