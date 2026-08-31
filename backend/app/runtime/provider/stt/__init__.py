"""STT Provider 包 - 导出所有语音识别引擎并注册到 Registry.

每个引擎的导入独立 try/except，缺失可选依赖时仅跳过该引擎的注册，
不影响其他引擎和整体 STT 功能的可用性.
"""

from loguru import logger
from app.runtime.provider.stt.stt_registry import LuomiNestSTTRegistry

try:
    from app.runtime.provider.stt.sherpa_onnx_stt import SherpaOnnxSTTProvider
    LuomiNestSTTRegistry.register("sherpa-onnx", SherpaOnnxSTTProvider)
except ImportError as e:
    logger.debug(f"[STT] SherpaOnnxSTTProvider not registered (dependency missing): {e}")

try:
    from app.runtime.provider.stt.funasr_stt import FunASRSTTProvider
    LuomiNestSTTRegistry.register("funasr", FunASRSTTProvider)
except ImportError as e:
    logger.debug(f"[STT] FunASRSTTProvider not registered (dependency missing): {e}")

try:
    from app.runtime.provider.stt.faster_whisper_stt import FasterWhisperSTTProvider
    LuomiNestSTTRegistry.register("faster-whisper", FasterWhisperSTTProvider)
except ImportError as e:
    logger.debug(f"[STT] FasterWhisperSTTProvider not registered (dependency missing): {e}")


__all__ = [
    "LuomiNestSTTRegistry",
]
