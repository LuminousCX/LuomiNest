"""Sherpa-ONNX TTS Provider - 完全离线的神经网络 TTS 引擎.

使用 vits-melo-tts-zh_en 模型，支持中英文，纯 CPU 推理，无需网络连接.
模型文件较大（约 162MB），首次使用时自动从 GitHub Releases 下载.
参考: Open-LLM-VTuber 的 sherpa_onnx_tts.py 实现.
"""

import asyncio
import io
import os
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path

import httpx
import soundfile as sf
from loguru import logger

from app.runtime.provider.engine_capabilities import EngineCapabilities
from app.runtime.provider.tts.ports import TTSProvider


def _resolve_model_dir() -> Path:
    # 解析 vits-melo-tts-zh_en 模型目录（按优先级）：
    # 1. LUOMINEST_TTS_MODEL_DIR 环境变量（绝对路径覆盖，运维/测试用）
    # 2. 打包态：sys.executable 同级（内置模型，只读），仅在目录存在时使用
    # 3. 打包态回退：settings.DATA_DIR / "models" / "tts" / "vits-melo-tts-zh_en"（可写，用于自动下载）
    # 4. 开发态：__file__ 在 backend/app/runtime/provider/tts/，parents[4] = backend/
    env_dir = os.environ.get("LUOMINEST_TTS_MODEL_DIR")
    if env_dir:
        return Path(env_dir)
    if getattr(sys, "frozen", False):
        builtin_dir = Path(sys.executable).parent / "models" / "tts" / "vits-melo-tts-zh_en"
        if builtin_dir.exists():
            return builtin_dir
        # 打包态未内置 TTS 模型（精简安装），下载到用户数据目录避免写入只读的 Program Files
        from app.core.config import settings
        return Path(settings.DATA_DIR) / "models" / "tts" / "vits-melo-tts-zh_en"
    return Path(__file__).resolve().parents[4] / "models" / "tts" / "vits-melo-tts-zh_en"


_DEFAULT_MODEL_DIR = _resolve_model_dir()

# 模型下载地址（sherpa-onnx GitHub Releases）
_MODEL_DOWNLOAD_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/"
    "tts-models/vits-melo-tts-zh_en.tar.bz2"
)

# 下载超时（秒），162MB 在慢网络下可能需要较长时间
_DOWNLOAD_TIMEOUT = 600

# 下载重试次数
_MAX_RETRIES = 3


async def _download_model(target_dir: Path) -> None:
    """自动下载并解压 vits-melo-tts-zh_en 模型.

    Args:
        target_dir: 模型目标目录（解压后应包含 model.onnx 等文件）
    """
    target_dir.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"[SherpaOnnxTTS] 开始下载模型: {_MODEL_DOWNLOAD_URL}")
    logger.info(f"[SherpaOnnxTTS] 目标目录: {target_dir}")
    logger.info(f"[SherpaOnnxTTS] 模型约 162MB，请耐心等待...")

    last_error: Exception | None = None

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            await _download_and_extract_once(target_dir)
            logger.info(f"[SherpaOnnxTTS] 模型下载完成（第 {attempt} 次尝试）")
            return
        except Exception as e:
            last_error = e
            logger.warning(f"[SherpaOnnxTTS] 下载失败（第 {attempt}/{_MAX_RETRIES} 次）: {e}")
            if attempt < _MAX_RETRIES:
                logger.info(f"[SherpaOnnxTTS] 等待 3 秒后重试...")
                await asyncio.sleep(3)

    raise RuntimeError(
        f"模型自动下载失败（已重试 {_MAX_RETRIES} 次）: {last_error}. "
        f"请手动下载 {_MODEL_DOWNLOAD_URL} 并解压到 {target_dir}"
    )


async def _download_and_extract_once(target_dir: Path) -> None:
    """执行一次下载+解压流程."""
    with tempfile.TemporaryDirectory(prefix="sherpa_tts_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        archive_path = tmp_path / "vits-melo-tts-zh_en.tar.bz2"

        # 流式下载，显示进度
        # 统一超时治理（应急修复 B3）：模块级 600s 硬编码 → Settings.TTS_DOWNLOAD_TIMEOUT
        from app.core.config import settings as _settings

        async with httpx.AsyncClient(timeout=_settings.TTS_DOWNLOAD_TIMEOUT, follow_redirects=True) as client:
            async with client.stream("GET", _MODEL_DOWNLOAD_URL) as resp:
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
                                    f"[SherpaOnnxTTS] 下载进度: {pct}% "
                                    f"({downloaded // 1048576}MB / {total // 1048576}MB)"
                                )

        logger.info(f"[SherpaOnnxTTS] 下载完成，开始解压...")

        # 解压 tar.bz2
        with tarfile.open(archive_path, "r:bz2") as tar:
            tar.extractall(path=tmp_path)

        # 解压后的目录名是 vits-melo-tts-zh_en
        extracted_dir = tmp_path / "vits-melo-tts-zh_en"
        if not extracted_dir.exists():
            # 尝试查找解压后的目录
            extracted_dirs = [d for d in tmp_path.iterdir() if d.is_dir() and d.name != ""]
            if extracted_dirs:
                extracted_dir = extracted_dirs[0]
            else:
                raise RuntimeError("解压后未找到模型目录")

        # 移动到目标目录
        if target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.move(str(extracted_dir), str(target_dir))

        # 验证关键文件
        model_onnx = target_dir / "model.onnx"
        if not model_onnx.exists():
            raise FileNotFoundError(f"解压后未找到 model.onnx: {model_onnx}")

        logger.info(f"[SherpaOnnxTTS] 解压完成: {target_dir}")


class SherpaOnnxTTSProvider(TTSProvider):
    """Sherpa-ONNX 离线 TTS Provider（单例）.

    首次使用时自动下载模型（约 162MB），后续直接加载.
    模型下载延迟到首次 async 调用时执行，避免在 __init__ 中阻塞事件循环.
    """

    provider_name = "sherpa-onnx"
    _instance = None
    _tts_engine = None

    DEFAULT_VOICES = {
        "zh": "zh-female",
        "en": "en-female",
    }

    # 引擎能力声明（G1/G2 治理）
    CAPABILITIES = EngineCapabilities(
        engine_id="sherpa-onnx",
        name="Sherpa-ONNX TTS（离线神经网络）",
        kind="local",
        category="local",
        needs_api_key=False,
        online=False,
        languages=("zh", "en"),
        voices=[
            {"value": "zh-female", "label": "中文女声", "langs": ["zh"]},
            {"value": "en-female", "label": "英文女声", "langs": ["en"]},
        ],
        default_voice="zh-female",
        supports_speed=True,
        description="vits-melo-tts-zh_en 离线模型（约 162MB，首次使用自动下载），中英双语，纯 CPU 推理",
    )

    @classmethod
    def is_available(cls) -> bool:
        """检查 sherpa-onnx 是否已安装."""
        try:
            import sherpa_onnx  # noqa: F401
            return True
        except ImportError:
            return False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, model_dir: str | Path | None = None, num_threads: int = 0, speed: float = 1.0, **kwargs):
        if self._tts_engine is not None:
            return
        import sherpa_onnx

        model_dir = Path(model_dir) if model_dir else _DEFAULT_MODEL_DIR
        self._model_dir = model_dir
        self._speed = speed
        # num_threads 自适应：0 表示自动计算
        if num_threads <= 0:
            self._num_threads = min(4, os.cpu_count() or 2)
        else:
            self._num_threads = num_threads
        self._engine_ready = False

        # 模型已就绪时直接加载引擎；否则延迟到首次 async 调用
        # 注意传 self._num_threads（自适应后 >0），原始 num_threads=0 会导致 validate 失败
        model_path = model_dir / "model.onnx"
        if model_path.exists():
            self._load_engine(sherpa_onnx, model_dir, model_path, self._num_threads)
        else:
            logger.info(
                f"[SherpaOnnxTTS] 模型未找到，将在首次调用时自动下载"
            )

    def _load_engine(self, sherpa_onnx, model_dir: Path, model_path: Path, num_threads: int) -> None:
        """加载 TTS 引擎（同步，需要模型文件已就绪）."""
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
        self._engine_ready = True
        logger.info(
            f"[SherpaOnnxTTS] Initialized: model={model_path.name}, "
            f"sample_rate={self._sample_rate}, threads={self._num_threads}"
        )

    async def _ensure_engine_ready(self) -> None:
        """确保模型已下载且引擎已加载."""
        if self._engine_ready:
            return
        import sherpa_onnx

        model_path = self._model_dir / "model.onnx"
        if not model_path.exists():
            logger.info(f"[SherpaOnnxTTS] 模型未找到，开始自动下载...")
            await _download_model(self._model_dir)

        self._load_engine(sherpa_onnx, self._model_dir, model_path, self._num_threads)

    async def synthesize(self, text: str, voice: str = "default") -> bytes:
        if not text.strip():
            return b""

        # 确保引擎已就绪（首次调用时可能触发模型下载）
        await self._ensure_engine_ready()

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
