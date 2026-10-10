"""Faster Whisper STT Provider - 基于 CTranslate2 的 Whisper 加速版.

使用 faster-whisper 库，比原版 Whisper 快 4 倍以上，内存占用更低.
支持自动下载模型（从 HuggingFace），也可手动放置到 backend/models/stt/ 目录.
参考: Open-LLM-VTuber 的 faster_whisper_asr.py 实现.
"""

import os
from pathlib import Path

import numpy as np
from loguru import logger

from app.runtime.provider.engine_capabilities import EngineCapabilities
from app.runtime.provider.model_paths import resolve_model_dir
from app.runtime.provider.stt.base import BaseSTTProvider


# 模型根目录（开发态：backend/models/stt/；打包态：userData/Data/backend/models/stt/）
_MODEL_ROOT = resolve_model_dir(
    "stt", "LUOMINEST_STT_MODEL_DIR", require_nonempty_builtin=True
)


def _default_model_size() -> str:
    """默认模型大小（惰性求值：首次构造 provider 时才读 env / 探测硬件）.

    优先级：STT_MODEL_SIZE 环境变量覆盖 > 低端机 "base" > "medium"。
    （从 import 期读 env 改为惰性：避免测试/工具脚本在 import 时被 env 钉死，
    且低端机降级依赖 hardware 单例探测，不宜提前触发。）
    """
    env_size = os.getenv("STT_MODEL_SIZE", "").strip()
    if env_size:
        return env_size
    try:
        from app.core.hardware import is_low_end_device

        if is_low_end_device():
            return "base"
    except Exception:
        pass
    # 默认从 large-v3 (~1.5GB) 改为 medium (~500MB)，降低内存占用
    return "medium"


def _resolve_num_threads() -> int:
    """CPU 推理线程数自适应（与 sherpa-onnx 侧同一模式）.

    基准 min(4, os.cpu_count())；低端机减半（下限 1）。
    """
    threads = min(4, os.cpu_count() or 2)
    try:
        from app.core.hardware import is_low_end_device

        if is_low_end_device():
            threads = max(1, threads // 2)
    except Exception:
        pass
    return threads

# 模型大小到描述的映射
MODEL_SIZES = {
    "tiny": "tiny (~39MB, 最低精度)",
    "base": "base (~74MB, 低精度)",
    "small": "small (~244MB, 中等精度)",
    "medium": "medium (~769MB, 较高精度)",
    "large-v3": "large-v3 (~1550MB, 最高精度)",
    "distil-medium.en": "distil-medium.en (~790MB, 英文加速版)",
}


class FasterWhisperSTTProvider(BaseSTTProvider):
    """Faster Whisper STT Provider（单例）.

    基于 CTranslate2 加速的 Whisper，支持 CPU 和 GPU 推理.
    模型首次使用时自动从 HuggingFace 下载.
    """

    provider_name = "faster-whisper"
    _instance = None
    _model = None
    _current_model_size = None

    # 引擎能力声明（G1/G2 治理）
    CAPABILITIES = EngineCapabilities(
        engine_id="faster-whisper",
        name="Faster Whisper（离线·CTranslate2 加速）",
        kind="local",
        category="local",
        needs_api_key=False,
        online=False,
        languages=("zh", "en", "ja", "ko", "yue", "fr", "de", "es"),
        description="基于 CTranslate2 的 Whisper 加速版，多语言识别，模型首次使用自动从 HuggingFace 下载",
    )

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        model_size: str | None = None,
        download_root: str | Path | None = None,
        language: str | None = None,
        device: str = "auto",
        compute_type: str = "int8",
        num_threads: int | None = None,
        prompt: str | None = None,
    ):
        # 默认值惰性求值（env 覆盖 > 低端机 base > medium；线程数按硬件自适应）
        model_size = model_size or _default_model_size()
        if num_threads is None:
            num_threads = _resolve_num_threads()

        # language 是轻量运行时参数：即使模型已加载（单例早退路径）也要刷新，
        # 否则透传进来的语言会被单例吞掉
        if self._model is not None and self._current_model_size == model_size:
            self._language = language
            self._prompt = prompt
            return

        from faster_whisper import WhisperModel

        self._language = language
        self._prompt = prompt
        self._current_model_size = model_size

        # 模型下载根目录
        if download_root:
            download_root = str(download_root)
        else:
            download_root = str(_MODEL_ROOT / "faster-whisper")

        # 设备选择
        if device == "auto":
            try:
                import torch
                if torch.cuda.is_available():
                    device = "cuda"
                    compute_type = "float16"
                else:
                    device = "cpu"
            except ImportError:
                device = "cpu"

        logger.info(
            f"[FasterWhisperSTT] Loading model: {model_size}, "
            f"device={device}, compute_type={compute_type}"
        )

        self._model = WhisperModel(
            model_size,
            download_root=download_root,
            device=device,
            compute_type=compute_type,
            num_threads=num_threads if device == "cpu" else 0,
        )

        logger.info(
            f"[FasterWhisperSTT] Initialized: model={model_size}, "
            f"device={device}, language={language}"
        )

    def _recognize_sync(self, audio: np.ndarray) -> str:
        """同步识别音频."""
        lang = self._language if self._language and self._language != "auto" else None

        if self._prompt:
            segments, _info = self._model.transcribe(
                audio,
                beam_size=5,
                language=lang,
                condition_on_previous_text=False,
                initial_prompt=self._prompt,
            )
        else:
            segments, _info = self._model.transcribe(
                audio,
                beam_size=5,
                language=lang,
                condition_on_previous_text=False,
            )

        text = "".join(segment.text for segment in segments)
        return text.strip()

    @classmethod
    def is_available(cls) -> bool:
        """检查 faster-whisper 是否已安装."""
        try:
            import faster_whisper  # noqa: F401
            return True
        except ImportError:
            return False

    @classmethod
    def is_model_ready(cls) -> bool:
        """检查模型文件是否已就位（仅检查目录是否存在）."""
        model_dir = _MODEL_ROOT / "faster-whisper"
        if not model_dir.exists():
            return False
        return any(model_dir.iterdir())
