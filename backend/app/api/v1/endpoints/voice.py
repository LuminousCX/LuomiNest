"""TTS / STT 语音域端点。

自 app/api/v1/endpoints/chat.py 结构拆分而来：路由 path/method/tags/响应
逐字不变，router 沿用 prefix="/chat"、tags=["chat"]，最终 URL 与原先完全一致。
"""
from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from loguru import logger

from app.core.hardware import detect_compute_device

router = APIRouter(prefix="/chat", tags=["chat"])


class TTSRequest(BaseModel):
    text: str = Field(..., max_length=2000)
    voice: str = Field(default="default")
    engine: str = Field(default="auto")
    model: str = Field(default="")
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    apiKey: str = Field(default="", max_length=500)
    baseUrl: str = Field(default="", pattern=r"^$|^https?://.*")

    @field_validator("baseUrl")
    @classmethod
    def _validate_base_url(cls, v: str) -> str:
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("baseUrl 必须是有效的 HTTP/HTTPS URL")
        return v


@router.post("/tts/synthesize")
async def tts_synthesize(request: TTSRequest):
    if not request.text.strip():
        return JSONResponse({"error": "文本内容不能为空"}, status_code=400)

    from fastapi.responses import Response
    from app.utils.tts_text_filter import filter_tts_text
    # 触发 TTS 引擎注册（import 包即注册）
    import app.runtime.provider.tts  # noqa: F401
    from app.runtime.provider.tts.tts_registry import LuminousChenXiTTSRegistry

    # 后端兜底过滤：清理 markdown/emoji/特殊符号
    clean_text = filter_tts_text(request.text)
    if not clean_text:
        return JSONResponse({"error": "过滤后文本为空，无需合成"}, status_code=400)

    # 构建引擎配置 kwargs（仅传递非空值，避免覆盖引擎默认值）
    config: dict = {}
    if request.model:
        config["model"] = request.model
    if request.speed and request.speed != 1.0:
        config["speed"] = request.speed
    if request.apiKey:
        config["apiKey"] = request.apiKey
    if request.baseUrl:
        config["baseUrl"] = request.baseUrl
    if request.voice and request.voice != "default":
        config["voice"] = request.voice

    # 通过 Registry 解析引擎，支持自动降级
    try:
        provider, used_engine = LuminousChenXiTTSRegistry.resolve(request.engine, **config)
    except RuntimeError as e:
        logger.error(f"[API] TTS: no engine available: {e}")
        return JSONResponse({"error": str(e)}, status_code=503)

    try:
        audio_bytes = await provider.synthesize(clean_text, request.voice)
        logger.info(f"[API] TTS synthesized by [{used_engine}]: {clean_text[:60]}...")
        return Response(
            content=audio_bytes,
            media_type="audio/wav",
            headers={"Content-Disposition": "inline"},
        )
    except Exception as e:
        logger.error(f"[API] TTS: engine [{used_engine}] failed: {e}")
        return JSONResponse({"error": f"语音合成失败：{e}"}, status_code=500)


@router.get("/tts/engines")
async def tts_engines():
    """Report available TTS engines, device info, and avatar voice bindings."""
    # 触发 TTS 引擎注册
    import app.runtime.provider.tts  # noqa: F401
    from app.runtime.provider.tts.tts_registry import LuminousChenXiTTSRegistry

    # 引擎元数据：显示名称、分类、是否需要 API Key、是否在线
    engine_meta = {
        "edge-tts": {"name": "Edge TTS (在线，免费)", "category": "cloud-free", "needs_api_key": False, "online": True},
        "sherpa-onnx": {"name": "Sherpa-ONNX TTS (离线神经网络)", "category": "local", "needs_api_key": False, "online": False},
        "local": {"name": "本地 TTS (pyttsx3, CPU)", "category": "local", "needs_api_key": False, "online": False},
        "gemini": {"name": "Gemini TTS (Google，免费层)", "category": "cloud-paid", "needs_api_key": True, "online": True},
        "minimax": {"name": "MiniMax TTS (高质量)", "category": "cloud-paid", "needs_api_key": True, "online": True},
        "siliconflow": {"name": "SiliconFlow TTS (CosyVoice2 云端)", "category": "cloud-paid", "needs_api_key": True, "online": True},
        "fish-audio": {"name": "Fish Audio TTS (多语言)", "category": "cloud-paid", "needs_api_key": True, "online": True},
    }

    engines: list[dict] = []
    for engine_id in LuminousChenXiTTSRegistry.list_engines():
        provider_class = LuminousChenXiTTSRegistry.get(engine_id)
        available = LuminousChenXiTTSRegistry.is_available(engine_id)
        meta = engine_meta.get(engine_id, {"name": engine_id, "category": "unknown", "needs_api_key": False, "online": False})

        engine_info: dict = {
            "id": engine_id,
            "name": meta["name"],
            "category": meta["category"],
            "needs_api_key": meta["needs_api_key"],
            "online": meta["online"],
            "available": available,
        }

        # 附加引擎特定信息（default_voices / voices / lang_map）
        if available and provider_class is not None:
            default_voices = getattr(provider_class, "DEFAULT_VOICES", None)
            if default_voices:
                engine_info["default_voices"] = default_voices

            # 本地引擎枚举系统语音列表
            if engine_id == "local":
                try:
                    provider = provider_class()
                    engine_info["voices"] = provider.list_voices()
                    engine_info["lang_map"] = provider.get_lang_map()
                except Exception as lv_err:
                    logger.debug(f"[API] TTS local voice enumeration failed: {lv_err}")

        engines.append(engine_info)

    device = detect_compute_device()

    # Avatar voice bindings (model_id -> voice/lang)
    from app.services.avatar_manager import LUOMINEST_AVATAR_BINDINGS
    bindings = {
        mid: {
            "model_id": b.model_id,
            "voice": b.voice,
            "voice_lang": b.voice_lang,
            "default_expression": b.default_expression,
        }
        for mid, b in LUOMINEST_AVATAR_BINDINGS.items()
    }

    return {
        "error": None,
        "data": {
            "engines": engines,
            "device": device,
            "avatar_bindings": bindings,
        },
    }


# ---------------------------------------------------------------------------
# STT (Speech-to-Text) endpoints
# ---------------------------------------------------------------------------

def _get_stt_provider(engine_id: str | None = None):
    """根据引擎 ID 获取 STT Provider，支持自动降级.

    Args:
        engine_id: 用户指定的引擎 ID，None 时按优先级自动选择

    Returns:
        (provider, engine_id) 元组

    Raises:
        RuntimeError: 所有引擎都不可用
    """
    # 触发 STT 引擎注册（import 包即注册）
    import app.runtime.provider.stt  # noqa: F401
    from app.runtime.provider.stt.stt_registry import LuomiNestSTTRegistry

    # 通过注册表解析引擎，支持自动降级（降级顺序见 STT_FALLBACK_ORDER）
    return LuomiNestSTTRegistry.resolve(engine_id)


@router.post("/stt/transcribe")
async def stt_transcribe(
    audio: "UploadFile" = File(...),
    engine: str = Form(default="auto"),
    language: str = Form(default="auto"),
):
    """语音识别接口 - 接收音频文件，返回识别文本.

    Args:
        audio: 音频文件（wav/mp3/webm/ogg 等）
        engine: STT 引擎 ID（sherpa-onnx / funasr / faster-whisper / auto）
        language: 识别语言（auto/zh/en/ja/ko 等）

    Returns:
        {"error": None, "data": {"text": "...", "engine": "sherpa-onnx"}}
    """
    audio_data = await audio.read()
    if not audio_data:
        return JSONResponse({"error": "音频文件为空"}, status_code=400)

    # 获取音频格式（从文件扩展名推断）
    format_hint = "wav"
    if audio.filename:
        ext = audio.filename.rsplit(".", 1)[-1].lower() if "." in audio.filename else ""
        if ext:
            format_hint = ext

    try:
        provider, used_engine = _get_stt_provider(engine)
    except RuntimeError as e:
        return JSONResponse({"error": str(e)}, status_code=503)

    try:
        text = await provider.transcribe(audio_data, format=format_hint)
        logger.info(f"[API] STT transcribed by [{used_engine}]: {text[:80]}...")
        return {
            "error": None,
            "data": {
                "text": text,
                "engine": used_engine,
            },
        }
    except Exception as e:
        logger.error(f"[API] STT transcribe failed: {e}")
        return JSONResponse({"error": f"语音识别失败：{e}"}, status_code=500)


@router.get("/stt/engines")
async def stt_engines():
    """报告可用的 STT 引擎列表."""
    from app.runtime.provider.stt.stt_registry import STT_FALLBACK_ORDER

    engines: list[dict] = []

    # Sherpa-ONNX STT
    try:
        from app.runtime.provider.stt.sherpa_onnx_stt import SherpaOnnxSTTProvider
        sherpa_available = SherpaOnnxSTTProvider.is_available()
        sherpa_model_ready = SherpaOnnxSTTProvider.is_model_ready() if sherpa_available else False
        engines.append({
            "id": "sherpa-onnx",
            "name": "Sherpa-ONNX (离线, SenseVoice)",
            "online": False,
            "available": sherpa_available,
            "model_ready": sherpa_model_ready,
            "languages": ["zh", "en", "ja", "ko", "yue", "auto"],
            "description": "基于 ONNX 的离线语音识别，默认使用 SenseVoice 模型，支持中英日韩粤",
            "model_types": ["sense_voice", "paraformer", "whisper"],
        })
    except ImportError:
        engines.append({
            "id": "sherpa-onnx",
            "name": "Sherpa-ONNX (离线, SenseVoice)",
            "online": False,
            "available": False,
        })

    # FunASR STT
    try:
        from app.runtime.provider.stt.funasr_stt import FunASRSTTProvider
        funasr_available = FunASRSTTProvider.is_available()
        engines.append({
            "id": "funasr",
            "name": "FunASR (离线, 阿里达摩院)",
            "online": False,
            "available": funasr_available,
            "model_ready": funasr_available,
            "languages": ["zh", "en", "auto"],
            "description": "阿里达摩院 FunASR，默认使用 SenseVoiceSmall，中文识别效果优秀",
            "models": FunASRSTTProvider.SUPPORTED_MODELS,
        })
    except ImportError:
        engines.append({
            "id": "funasr",
            "name": "FunASR (离线, 阿里达摩院)",
            "online": False,
            "available": False,
        })

    # Faster Whisper STT
    try:
        from app.runtime.provider.stt.faster_whisper_stt import FasterWhisperSTTProvider, MODEL_SIZES as FW_MODEL_SIZES
        fw_available = FasterWhisperSTTProvider.is_available()
        engines.append({
            "id": "faster-whisper",
            "name": "Faster Whisper (离线, CTranslate2 加速)",
            "online": False,
            "available": fw_available,
            "model_ready": fw_available,
            "languages": ["zh", "en", "ja", "ko", "fr", "de", "es", "auto"],
            "description": "基于 CTranslate2 的 Whisper 加速版，比原版快 4 倍以上",
            "model_sizes": list(FW_MODEL_SIZES.keys()),
        })
    except ImportError:
        engines.append({
            "id": "faster-whisper",
            "name": "Faster Whisper (离线, CTranslate2 加速)",
            "online": False,
            "available": False,
        })

    return {
        "error": None,
        "data": {
            "engines": engines,
            "fallback_order": STT_FALLBACK_ORDER,
            "device": detect_compute_device(),
        },
    }
