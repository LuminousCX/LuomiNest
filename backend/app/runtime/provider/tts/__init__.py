"""TTS Provider 包 - 导出所有语音合成引擎并注册到 Registry.

每个引擎的导入独立 try/except，缺失可选依赖时仅跳过该引擎的注册，
不影响其他引擎和整体 TTS 功能的可用性.
"""

from loguru import logger
from app.runtime.provider.tts.tts_registry import LuminousChenXiTTSRegistry

# === 本地引擎（依赖可选包） ===

try:
    from app.runtime.provider.tts.sherpa_onnx_tts import SherpaOnnxTTSProvider
    LuminousChenXiTTSRegistry.register("sherpa-onnx", SherpaOnnxTTSProvider)
except ImportError as e:
    logger.debug(f"[TTS] SherpaOnnxTTSProvider not registered (dependency missing): {e}")

try:
    from app.runtime.provider.tts.local_tts import LocalTTSProvider
    LuminousChenXiTTSRegistry.register("local", LocalTTSProvider)
except ImportError as e:
    logger.debug(f"[TTS] LocalTTSProvider not registered (dependency missing): {e}")

try:
    from app.runtime.provider.tts.edge_tts import EdgeTTSProvider
    LuminousChenXiTTSRegistry.register("edge-tts", EdgeTTSProvider)
except ImportError as e:
    logger.debug(f"[TTS] EdgeTTSProvider not registered (dependency missing): {e}")

# === 云端引擎（仅依赖 httpx，始终可用） ===

try:
    from app.runtime.provider.tts.gemini_tts import GeminiTTSProvider
    LuminousChenXiTTSRegistry.register("gemini", GeminiTTSProvider)
except ImportError as e:
    logger.debug(f"[TTS] GeminiTTSProvider not registered: {e}")

try:
    from app.runtime.provider.tts.minimax_tts import MiniMaxTTSProvider
    LuminousChenXiTTSRegistry.register("minimax", MiniMaxTTSProvider)
except ImportError as e:
    logger.debug(f"[TTS] MiniMaxTTSProvider not registered: {e}")

try:
    from app.runtime.provider.tts.siliconflow_tts import SiliconFlowTTSProvider
    LuminousChenXiTTSRegistry.register("siliconflow", SiliconFlowTTSProvider)
except ImportError as e:
    logger.debug(f"[TTS] SiliconFlowTTSProvider not registered: {e}")

try:
    from app.runtime.provider.tts.fish_audio_tts import FishAudioTTSProvider
    LuminousChenXiTTSRegistry.register("fish-audio", FishAudioTTSProvider)
except ImportError as e:
    logger.debug(f"[TTS] FishAudioTTSProvider not registered: {e}")


__all__ = [
    "LuminousChenXiTTSRegistry",
]
