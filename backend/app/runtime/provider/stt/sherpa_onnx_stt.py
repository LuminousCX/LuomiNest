"""Sherpa-ONNX STT Provider - 离线语音识别引擎.

使用 sherpa-onnx 的 OfflineRecognizer，支持 SenseVoice / Paraformer / Whisper 等多种模型.
默认使用 SenseVoice 模型（中英日韩粤多语言），纯 CPU 推理，无需网络连接.
模型文件首次使用时自动从 GitHub Releases 下载，也可手动放置到 backend/models/stt/ 目录.
参考: Open-LLM-VTuber 的 sherpa_onnx_asr.py 实现.
"""

import asyncio
import io
import re
import shutil
import tarfile
import tempfile
from pathlib import Path

import httpx
import numpy as np
import soundfile as sf
from loguru import logger

from app.runtime.provider.base import STTProvider


# 模型根目录（backend/models/stt/）
_MODEL_ROOT = Path(__file__).resolve().parents[4] / "models" / "stt"

# SenseVoice 模型目录
_SENSE_VOICE_DIR = _MODEL_ROOT / "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17"

# SenseVoice 模型下载地址
_SENSE_VOICE_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/"
    "asr-models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17.tar.bz2"
)

# 下载超时（秒），模型约 220MB
_DOWNLOAD_TIMEOUT = 600

# 下载重试次数
_MAX_RETRIES = 3

# 采样率
_SAMPLE_RATE = 16000


def _download_sense_voice_model(target_dir: Path) -> None:
    """自动下载并解压 SenseVoice 模型（同步版本）.

    Args:
        target_dir: 模型目标目录
    """
    target_dir.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"[SherpaOnnxSTT] 开始下载 SenseVoice 模型: {_SENSE_VOICE_URL}")
    logger.info(f"[SherpaOnnxSTT] 目标目录: {target_dir}")
    logger.info(f"[SherpaOnnxSTT] 模型约 220MB，请耐心等待...")

    last_error: Exception | None = None

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            _download_and_extract_once(target_dir)
            logger.info(f"[SherpaOnnxSTT] 模型下载完成（第 {attempt} 次尝试）")
            return
        except Exception as e:
            last_error = e
            logger.warning(f"[SherpaOnnxSTT] 下载失败（第 {attempt}/{_MAX_RETRIES} 次）: {e}")
            if attempt < _MAX_RETRIES:
                logger.info(f"[SherpaOnnxSTT] 等待 3 秒后重试...")
                import time
                time.sleep(3)

    raise RuntimeError(
        f"模型自动下载失败（已重试 {_MAX_RETRIES} 次）: {last_error}. "
        f"请手动下载 {_SENSE_VOICE_URL} 并解压到 {target_dir}"
    )


def _download_and_extract_once(target_dir: Path) -> None:
    """执行一次下载+解压流程."""
    with tempfile.TemporaryDirectory(prefix="sherpa_stt_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        archive_path = tmp_path / "sense-voice.tar.bz2"

        with httpx.Client(timeout=_DOWNLOAD_TIMEOUT, follow_redirects=True) as client:
            with client.stream("GET", _SENSE_VOICE_URL) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("content-length", 0))
                downloaded = 0
                last_log_pct = 0

                with open(archive_path, "wb") as f:
                    for chunk in resp.iter_bytes(chunk_size=65536):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            pct = int(downloaded * 100 / total)
                            if pct >= last_log_pct + 10:
                                last_log_pct = pct
                                logger.info(
                                    f"[SherpaOnnxSTT] 下载进度: {pct}% "
                                    f"({downloaded // 1048576}MB / {total // 1048576}MB)"
                                )

        logger.info(f"[SherpaOnnxSTT] 下载完成，开始解压...")

        with tarfile.open(archive_path, "r:bz2") as tar:
            tar.extractall(path=tmp_path)

        # 解压后的目录名
        extracted_dir = tmp_path / target_dir.name
        if not extracted_dir.exists():
            extracted_dirs = [d for d in tmp_path.iterdir() if d.is_dir() and d.name != ""]
            if extracted_dirs:
                extracted_dir = extracted_dirs[0]
            else:
                raise RuntimeError("解压后未找到模型目录")

        if target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.move(str(extracted_dir), str(target_dir))

        model_onnx = target_dir / "model.int8.onnx"
        if not model_onnx.exists():
            # 也检查 model.onnx
            model_onnx = target_dir / "model.onnx"
            if not model_onnx.exists():
                raise FileNotFoundError(f"解压后未找到模型文件: {target_dir}")

        logger.info(f"[SherpaOnnxSTT] 解压完成: {target_dir}")


def _clean_sense_voice_text(text: str) -> str:
    """去除 SenseVoice 输出的标签（如 <|zh|><|NEUTRAL|><|Speech|>）."""
    text = re.sub(r"<\|.*?\|>", "", text)
    text = re.sub(r"< \|.*?\| >", "", text)
    return text.strip()


class SherpaOnnxSTTProvider(STTProvider):
    """Sherpa-ONNX 离线 STT Provider（单例）.

    默认使用 SenseVoice 模型，支持中英日韩粤多语言识别.
    首次使用时自动下载模型（约 220MB），后续直接加载.
    """

    provider_name = "sherpa-onnx"
    _instance = None
    _recognizer = None

    # 支持的模型类型
    SUPPORTED_MODEL_TYPES = ("sense_voice", "paraformer", "whisper")

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        model_type: str = "sense_voice",
        model_dir: str | Path | None = None,
        language: str = "auto",
        num_threads: int = 2,
        use_itn: bool = True,
    ):
        if self._recognizer is not None:
            return

        import sherpa_onnx

        self._model_type = model_type
        self._language = language
        self._use_itn = use_itn

        if model_type == "sense_voice":
            self._init_sense_voice(sherpa_onnx, model_dir, num_threads)
        elif model_type == "paraformer":
            self._init_paraformer(sherpa_onnx, model_dir, num_threads)
        elif model_type == "whisper":
            self._init_whisper(sherpa_onnx, model_dir, num_threads)
        else:
            raise ValueError(
                f"不支持的模型类型: {model_type}，支持: {self.SUPPORTED_MODEL_TYPES}"
            )

        logger.info(
            f"[SherpaOnnxSTT] Initialized: model_type={model_type}, "
            f"language={language}, threads={num_threads}"
        )

    def _init_sense_voice(self, sherpa_onnx, model_dir, num_threads: int):
        """初始化 SenseVoice 模型."""
        model_dir = Path(model_dir) if model_dir else _SENSE_VOICE_DIR
        self._model_dir = model_dir

        # 查找模型文件（优先 int8 量化版）
        model_path = model_dir / "model.int8.onnx"
        if not model_path.exists():
            model_path = model_dir / "model.onnx"
        if not model_path.exists():
            logger.info(f"[SherpaOnnxSTT] SenseVoice 模型未找到，开始自动下载...")
            _download_sense_voice_model(model_dir)
            model_path = model_dir / "model.int8.onnx"
            if not model_path.exists():
                model_path = model_dir / "model.onnx"

        tokens_path = model_dir / "tokens.txt"
        if not tokens_path.exists():
            raise FileNotFoundError(f"tokens.txt 未找到: {tokens_path}")

        recognizer_config = sherpa_onnx.OfflineRecognizerConfig(
            model=sherpa_onnx.OfflineRecognizerModelConfig(
                sense_voice=sherpa_onnx.OfflineSenseVoiceModelConfig(
                    model=str(model_path),
                    language=self._language,
                    use_itn=self._use_itn,
                ),
                tokens=str(tokens_path),
                num_threads=num_threads,
                provider="cpu",
                debug=False,
            )
        )

        if not recognizer_config.validate():
            raise ValueError("Sherpa-ONNX STT (SenseVoice) config validation failed")

        self._recognizer = sherpa_onnx.OfflineRecognizer(recognizer_config)

    def _init_paraformer(self, sherpa_onnx, model_dir, num_threads: int):
        """初始化 Paraformer 模型."""
        model_dir = Path(model_dir) if model_dir else _MODEL_ROOT / "sherpa-onnx-paraformer"
        self._model_dir = model_dir

        model_path = model_dir / "model.int8.onnx"
        if not model_path.exists():
            model_path = model_dir / "model.onnx"
        if not model_path.exists():
            raise FileNotFoundError(
                f"Paraformer 模型未找到: {model_path}. "
                f"请手动下载 sherpa-onnx-paraformer 模型并放置到 {model_dir}"
            )

        tokens_path = model_dir / "tokens.txt"
        if not tokens_path.exists():
            raise FileNotFoundError(f"tokens.txt 未找到: {tokens_path}")

        recognizer_config = sherpa_onnx.OfflineRecognizerConfig(
            model=sherpa_onnx.OfflineRecognizerModelConfig(
                paraformer=sherpa_onnx.OfflineParaformerModelConfig(
                    model=str(model_path),
                ),
                tokens=str(tokens_path),
                num_threads=num_threads,
                provider="cpu",
                debug=False,
            )
        )

        if not recognizer_config.validate():
            raise ValueError("Sherpa-ONNX STT (Paraformer) config validation failed")

        self._recognizer = sherpa_onnx.OfflineRecognizer(recognizer_config)

    def _init_whisper(self, sherpa_onnx, model_dir, num_threads: int):
        """初始化 Whisper 模型."""
        model_dir = Path(model_dir) if model_dir else _MODEL_ROOT / "sherpa-onnx-whisper"
        self._model_dir = model_dir

        encoder_path = model_dir / "tiny-encoder.onnx"
        decoder_path = model_dir / "tiny-decoder.onnx"
        if not encoder_path.exists() or not decoder_path.exists():
            raise FileNotFoundError(
                f"Whisper 模型未找到: {model_dir}. "
                f"请手动下载 sherpa-onnx-whisper 模型并放置到 {model_dir}"
            )

        tokens_path = model_dir / "tiny-tokens.txt"
        if not tokens_path.exists():
            raise FileNotFoundError(f"tokens.txt 未找到: {tokens_path}")

        recognizer_config = sherpa_onnx.OfflineRecognizerConfig(
            model=sherpa_onnx.OfflineRecognizerModelConfig(
                whisper=sherpa_onnx.OfflineWhisperModelConfig(
                    encoder=str(encoder_path),
                    decoder=str(decoder_path),
                    language=self._language if self._language != "auto" else "en",
                    task="transcribe",
                ),
                tokens=str(tokens_path),
                num_threads=num_threads,
                provider="cpu",
                debug=False,
            )
        )

        if not recognizer_config.validate():
            raise ValueError("Sherpa-ONNX STT (Whisper) config validation failed")

        self._recognizer = sherpa_onnx.OfflineRecognizer(recognizer_config)

    async def transcribe(self, audio_data: bytes, format: str = "wav") -> str:
        if not audio_data:
            return ""

        # 解码音频为 numpy 数组
        audio_np = await asyncio.to_thread(self._decode_audio, audio_data, format)

        # 识别
        text = await asyncio.to_thread(self._recognize_sync, audio_np)

        # SenseVoice 输出带标签，需要清理
        if self._model_type == "sense_voice":
            text = _clean_sense_voice_text(text)

        return text

    def _decode_audio(self, audio_data: bytes, format: str) -> np.ndarray:
        """将音频 bytes 解码为 16kHz 单声道 numpy 数组."""
        buffer = io.BytesIO(audio_data)
        audio_np, sr = sf.read(buffer, dtype="float32")

        # 如果是多声道，取第一声道
        if audio_np.ndim > 1:
            audio_np = audio_np[:, 0]

        # 重采样到 16kHz（如果需要）
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

    def _recognize_sync(self, audio: np.ndarray) -> str:
        """同步识别音频."""
        stream = self._recognizer.create_stream()
        stream.accept_waveform(_SAMPLE_RATE, audio)
        self._recognizer.decode_streams([stream])
        return stream.result.text

    @classmethod
    def is_available(cls) -> bool:
        """检查 sherpa-onnx 是否已安装."""
        try:
            import sherpa_onnx  # noqa: F401
            return True
        except ImportError:
            return False

    @classmethod
    def is_model_ready(cls) -> bool:
        """检查模型文件是否已就位."""
        model_path = _SENSE_VOICE_DIR / "model.int8.onnx"
        if not model_path.exists():
            model_path = _SENSE_VOICE_DIR / "model.onnx"
        tokens_path = _SENSE_VOICE_DIR / "tokens.txt"
        return model_path.exists() and tokens_path.exists()
