"""Sherpa-ONNX STT Provider - 离线语音识别引擎.

使用 sherpa-onnx 的 OfflineRecognizer，支持 SenseVoice / Paraformer / Whisper 等多种模型.
默认使用 SenseVoice 模型（中英日韩粤多语言），纯 CPU 推理，无需网络连接.
模型文件首次使用时自动从 GitHub Releases 下载，也可手动放置到 backend/models/stt/ 目录.
参考: Open-LLM-VTuber 的 sherpa_onnx_asr.py 实现.
"""

import asyncio
import io
import os
import re
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path

import httpx
import numpy as np
import soundfile as sf
from loguru import logger

from app.runtime.provider.stt.ports import STTProvider


def _resolve_model_root() -> Path:
    """解析 STT 模型根目录（按优先级）：
    1. LUOMINEST_STT_MODEL_DIR 环境变量（绝对路径覆盖，运维/测试用）
    2. 打包态：sys.executable 同级（内置模型，只读），仅在目录存在且非空时使用
    3. 打包态回退：settings.DATA_DIR / "models" / "stt"（用户下载目录，可写）
    4. 开发态：__file__ 在 backend/app/runtime/provider/stt/，parents[4] = backend/
    """
    env_dir = os.environ.get("LUOMINEST_STT_MODEL_DIR")
    if env_dir:
        return Path(env_dir)
    if getattr(sys, "frozen", False):
        builtin_root = Path(sys.executable).parent / "models" / "stt"
        if builtin_root.exists() and any(builtin_root.iterdir()):
            return builtin_root
        # 打包态未内置 STT 模型，下载到用户数据目录（避免写入只读的 Program Files）
        from app.core.config import settings
        return Path(settings.DATA_DIR) / "models" / "stt"
    return Path(__file__).resolve().parents[4] / "models" / "stt"


# 模型根目录（开发态：backend/models/stt/；打包态：userData/Data/backend/models/stt/）
_MODEL_ROOT = _resolve_model_root()

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


async def _download_sense_voice_model(target_dir: Path) -> None:
    """自动下载并解压 SenseVoice 模型.

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
            await _download_and_extract_once(target_dir)
            logger.info(f"[SherpaOnnxSTT] 模型下载完成（第 {attempt} 次尝试）")
            return
        except Exception as e:
            last_error = e
            logger.warning(f"[SherpaOnnxSTT] 下载失败（第 {attempt}/{_MAX_RETRIES} 次）: {e}")
            if attempt < _MAX_RETRIES:
                logger.info(f"[SherpaOnnxSTT] 等待 3 秒后重试...")
                await asyncio.sleep(3)

    raise RuntimeError(
        f"模型自动下载失败（已重试 {_MAX_RETRIES} 次）: {last_error}. "
        f"请手动下载 {_SENSE_VOICE_URL} 并解压到 {target_dir}"
    )


async def _download_and_extract_once(target_dir: Path) -> None:
    """执行一次下载+解压流程."""
    with tempfile.TemporaryDirectory(prefix="sherpa_stt_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        archive_path = tmp_path / "sense-voice.tar.bz2"

        async with httpx.AsyncClient(timeout=_DOWNLOAD_TIMEOUT, follow_redirects=True) as client:
            async with client.stream("GET", _SENSE_VOICE_URL) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("content-length", 0))
                downloaded = 0
                last_log_pct = 0

                with open(archive_path, "wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size=65536):
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
    模型采用懒加载模式，首次 transcribe() 时才真正加载到内存.
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
        num_threads: int = 0,
        use_itn: bool = True,
    ):
        # 单例：仅首次调用时保存参数
        if getattr(self, "_initialized", False):
            return
        self._initialized = True

        # num_threads 自适应：0 表示自动计算
        if num_threads <= 0:
            self._num_threads = min(4, os.cpu_count() or 2)
        else:
            self._num_threads = num_threads

        self._model_type = model_type
        self._language = language
        self._use_itn = use_itn
        self._recognizer_ready = False

        # 设置模型目录（不加载模型）
        if model_type == "sense_voice":
            self._model_dir = Path(model_dir) if model_dir else _SENSE_VOICE_DIR
        elif model_type == "paraformer":
            self._model_dir = Path(model_dir) if model_dir else _MODEL_ROOT / "sherpa-onnx-paraformer"
        elif model_type == "whisper":
            self._model_dir = Path(model_dir) if model_dir else _MODEL_ROOT / "sherpa-onnx-whisper"
        else:
            raise ValueError(
                f"不支持的模型类型: {model_type}，支持: {self.SUPPORTED_MODEL_TYPES}"
            )

        logger.info(
            f"[SherpaOnnxSTT] Initialized (lazy): model_type={model_type}, "
            f"language={language}, threads={self._num_threads}"
        )

    def _ensure_model_loaded_sync(self) -> None:
        """同步确保 recognizer 已加载（用于 _recognize_sync 等同步路径）."""
        if self._recognizer_ready:
            return
        raise RuntimeError(
            "Recognizer not loaded. Call _ensure_recognizer_ready() first."
        )

    async def _ensure_recognizer_ready(self) -> None:
        """确保 recognizer 已加载（首次调用时可能触发模型下载）."""
        if self._recognizer_ready:
            return
        import sherpa_onnx

        if self._model_type == "sense_voice":
            model_path = self._model_dir / "model.int8.onnx"
            if not model_path.exists():
                model_path = self._model_dir / "model.onnx"
            if not model_path.exists():
                logger.info(f"[SherpaOnnxSTT] SenseVoice 模型未找到，开始自动下载...")
                await _download_sense_voice_model(self._model_dir)
                model_path = self._model_dir / "model.int8.onnx"
                if not model_path.exists():
                    model_path = self._model_dir / "model.onnx"
            self._load_sense_voice_recognizer(sherpa_onnx, model_path)
        elif self._model_type == "paraformer":
            self._init_paraformer_sync(sherpa_onnx)
        elif self._model_type == "whisper":
            self._init_whisper_sync(sherpa_onnx)

    def _load_sense_voice_recognizer(self, sherpa_onnx, model_path: Path) -> None:
        """加载 SenseVoice recognizer（同步，需要模型文件已就绪）."""
        tokens_path = self._model_dir / "tokens.txt"
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
                num_threads=self._num_threads,
                provider="cpu",
                debug=False,
            )
        )

        if not recognizer_config.validate():
            raise ValueError("Sherpa-ONNX STT (SenseVoice) config validation failed")

        self._recognizer = sherpa_onnx.OfflineRecognizer(recognizer_config)
        self._recognizer_ready = True
        logger.info(
            f"[SherpaOnnxSTT] SenseVoice loaded: model={model_path.name}, "
            f"threads={self._num_threads}"
        )

    def _init_paraformer_sync(self, sherpa_onnx) -> None:
        """初始化 Paraformer 模型（懒加载路径）."""
        model_dir = self._model_dir
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
                num_threads=self._num_threads,
                provider="cpu",
                debug=False,
            )
        )

        if not recognizer_config.validate():
            raise ValueError("Sherpa-ONNX STT (Paraformer) config validation failed")

        self._recognizer = sherpa_onnx.OfflineRecognizer(recognizer_config)
        self._recognizer_ready = True
        logger.info(f"[SherpaOnnxSTT] Paraformer loaded: threads={self._num_threads}")

    def _init_whisper_sync(self, sherpa_onnx) -> None:
        """初始化 Whisper 模型（懒加载路径）."""
        model_dir = self._model_dir

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
                num_threads=self._num_threads,
                provider="cpu",
                debug=False,
            )
        )

        if not recognizer_config.validate():
            raise ValueError("Sherpa-ONNX STT (Whisper) config validation failed")

        self._recognizer = sherpa_onnx.OfflineRecognizer(recognizer_config)
        self._recognizer_ready = True
        logger.info(f"[SherpaOnnxSTT] Whisper loaded: threads={self._num_threads}")

    async def transcribe(self, audio_data: bytes, format: str = "wav") -> str:
        if not audio_data:
            return ""

        # 确保 recognizer 已就绪（首次调用时可能触发模型下载）
        await self._ensure_recognizer_ready()

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
