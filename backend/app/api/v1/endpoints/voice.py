"""TTS / STT 语音域端点。

自 app/api/v1/endpoints/chat.py 结构拆分而来：路由 path/method/tags/响应
逐字不变，router 沿用 prefix="/chat"、tags=["chat"]，最终 URL 与原先完全一致。

v0.5 P0 重构（voice-model-market.md）：
- G1/G2：engine_meta 硬编码 → EngineCapabilities（registry.list_capabilities）
- G3/G6：avatar 绑定 → voice_config_store（config_items 权威源）
- G5：TTSRequest.lang + VoiceProfileResolver 语言感知解析链
- G7：统一超时（Settings.TTS_*_TIMEOUT，各 provider 内落地）
- G8：错误响应统一走 LuomiNestError 家族 + ok()/fail() 信封
"""
from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import Response
from loguru import logger
from pydantic import BaseModel, Field, field_validator

from app.core.exceptions import (
    LangNotSupportedError,
    VoiceEngineUnavailableError,
    VoiceSynthesisError,
    VoiceTranscribeError,
)
from app.core.hardware import detect_compute_device
from app.core.utils import fail, ok
from app.runtime.provider.engine_capabilities import (
    LANGUAGE_LABELS,
    SUPPORTED_TTS_LANGUAGES,
)

router = APIRouter(prefix="/chat", tags=["chat"])

# 语音配置/画像端点（voice-model-market.md §7.4）
voice_router = APIRouter(prefix="/voice", tags=["voice"])


class TTSRequest(BaseModel):
    text: str = Field(..., max_length=2000)
    voice: str = Field(default="default")
    engine: str = Field(default="auto")
    model: str = Field(default="")
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    apiKey: str = Field(default="", max_length=500)
    baseUrl: str = Field(default="", pattern=r"^$|^https?://.*")
    # v0.5 G5：语言字段（auto/zh/en/ja/ko/yue），驱动语言感知解析链
    lang: str = Field(default="auto")
    # 皮套场景（可选）：携带 model_id 触发皮套语音绑定查询
    avatarModelId: str = Field(default="", max_length=100)

    @field_validator("baseUrl")
    @classmethod
    def _validate_base_url(cls, v: str) -> str:
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("baseUrl 必须是有效的 HTTP/HTTPS URL")
        return v

    @field_validator("lang")
    @classmethod
    def _validate_lang(cls, v: str) -> str:
        if v not in SUPPORTED_TTS_LANGUAGES:
            raise ValueError(f"lang 必须是 {'/'.join(SUPPORTED_TTS_LANGUAGES)} 之一")
        return v


@router.post("/tts/synthesize")
async def tts_synthesize(request: TTSRequest):
    if not request.text.strip():
        return fail("文本内容不能为空", err_code="TTS_EMPTY_TEXT", status_code=400)

    from app.utils.tts_text_filter import filter_tts_text

    # 触发 TTS 引擎注册（import 包即注册）
    import app.runtime.provider.tts  # noqa: F401
    from app.runtime.provider.tts.tts_registry import LuminousChenXiTTSRegistry
    from app.services.voice_profile_resolver import luominest_voice_profile_resolver

    # 后端兜底过滤：清理 markdown/emoji/特殊符号
    clean_text = filter_tts_text(request.text)
    if not clean_text:
        return fail("过滤后文本为空，无需合成", err_code="TTS_EMPTY_TEXT", status_code=400)

    # 语音画像解析（请求参数 > 皮套绑定 > 全局默认 + 语言感知，G5/G6）
    profile = luominest_voice_profile_resolver.resolve_tts(
        engine=request.engine,
        model=request.model or None,
        voice=request.voice,
        lang=request.lang,
        speed=request.speed,
        api_key=request.apiKey or None,
        base_url=request.baseUrl or None,
        avatar_model_id=request.avatarModelId or None,
        text=clean_text,
    )

    # 语言能力校验（解析链 L1/L2）：显式指定引擎且声明不支持目标语言 → LANG_NOT_SUPPORTED
    # （auto 模式由 Registry 语言过滤自动降级，不在此报错）
    if profile.engine and profile.engine != "auto" and profile.lang != "auto":
        caps = LuminousChenXiTTSRegistry.capabilities(profile.engine)
        if caps and caps.get("languages") and profile.lang not in caps["languages"]:
            raise LangNotSupportedError(
                f"当前语音引擎 {caps.get('name', profile.engine)} 不支持"
                f"{LANGUAGE_LABELS.get(profile.lang, profile.lang)}",
                lang=profile.lang,
                engine=profile.engine,
            )

    # 通过 Registry 解析引擎（含语言过滤 + 自动降级）
    try:
        provider, used_engine = LuminousChenXiTTSRegistry.resolve(
            profile.engine, lang=profile.lang, **profile.to_config_kwargs()
        )
    except RuntimeError as e:
        logger.error(f"[API] TTS: no engine available: {e}")
        raise VoiceEngineUnavailableError(str(e)) from e

    try:
        audio_bytes = await provider.synthesize(clean_text, profile.voice or "default")
        logger.info(
            f"[API] TTS synthesized by [{used_engine}] (lang={profile.lang}): {clean_text[:60]}..."
        )
        return Response(
            content=audio_bytes,
            media_type="audio/wav",
            headers={"Content-Disposition": "inline"},
        )
    except Exception as e:
        logger.error(f"[API] TTS: engine [{used_engine}] failed: {e}")
        raise VoiceSynthesisError(f"语音合成失败：{e}", engine=used_engine) from e


@router.get("/tts/engines")
async def tts_engines():
    """Report available TTS engines, device info, and avatar voice bindings.

    v0.5 G1：引擎元数据来自各 Provider 的 CAPABILITIES 类属性（替代 engine_meta 硬编码），
    含 languages/voices/voice_mode/models 等能力声明，前端按此渲染级联下拉。
    """
    # 触发 TTS 引擎注册
    import app.runtime.provider.tts  # noqa: F401
    from app.runtime.provider.tts.tts_registry import LuminousChenXiTTSRegistry
    from app.services.voice_config_store import luominest_voice_config_store

    engines: list[dict] = []
    for engine_id in LuminousChenXiTTSRegistry.list_engines():
        provider_class = LuminousChenXiTTSRegistry.get(engine_id)
        available = LuminousChenXiTTSRegistry.is_available(engine_id)
        caps = LuminousChenXiTTSRegistry.capabilities(engine_id)

        if caps is not None:
            engine_info = dict(caps)
        else:
            engine_info = {"id": engine_id, "name": engine_id, "category": "unknown"}
        engine_info["available"] = available

        # 附加引擎特定信息（default_voices 语言映射 / 本地引擎动态音色枚举）
        if available and provider_class is not None:
            default_voices = getattr(provider_class, "DEFAULT_VOICES", None)
            if default_voices:
                engine_info["default_voices"] = default_voices

            # 本地引擎枚举系统语音列表
            if engine_id == "local":
                try:
                    provider = provider_class()
                    engine_info["voices_dynamic"] = provider.list_voices()
                    engine_info["lang_map"] = provider.get_lang_map()
                except Exception as lv_err:
                    logger.debug(f"[API] TTS local voice enumeration failed: {lv_err}")

        engines.append(engine_info)

    device = detect_compute_device()

    # Avatar voice bindings (model_id -> voice/lang)，v0.5 G3：从 config_items 读取（迁移后权威源）
    bindings = luominest_voice_config_store.get_avatar_bindings()

    return ok({
        "engines": engines,
        "device": device,
        "avatar_bindings": bindings,
        "languages": [
            {"value": v, "label": LANGUAGE_LABELS[v]} for v in SUPPORTED_TTS_LANGUAGES
        ],
    })


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
        ok() 信封：{"code": 0, "data": {"text": "...", "engine": "sherpa-onnx"}}
        （保留旧 data 结构字段，error 字段由信封统一承载）
    """
    audio_data = await audio.read()
    if not audio_data:
        return fail("音频文件为空", err_code="STT_EMPTY_AUDIO", status_code=400)

    # 获取音频格式（从文件扩展名推断）
    format_hint = "wav"
    if audio.filename:
        ext = audio.filename.rsplit(".", 1)[-1].lower() if "." in audio.filename else ""
        if ext:
            format_hint = ext

    try:
        provider, used_engine = _get_stt_provider(engine)
    except RuntimeError as e:
        raise VoiceEngineUnavailableError(str(e)) from e

    try:
        text = await provider.transcribe(audio_data, format=format_hint)
        logger.info(f"[API] STT transcribed by [{used_engine}]: {text[:80]}...")
        return ok({"text": text, "engine": used_engine})
    except Exception as e:
        logger.error(f"[API] STT transcribe failed: {e}")
        raise VoiceTranscribeError(f"语音识别失败：{e}", engine=used_engine) from e


@router.get("/stt/engines")
async def stt_engines():
    """报告可用的 STT 引擎列表（v0.5 G1：capabilities 聚合，替代逐个 try-import 硬编码）."""
    import app.runtime.provider.stt  # noqa: F401
    from app.runtime.provider.stt.stt_registry import STT_FALLBACK_ORDER, LuomiNestSTTRegistry

    engines = LuomiNestSTTRegistry.list_capabilities()

    # 附加引擎特有信息（模型就绪态/模型清单，供设置页渲染）
    for info in engines:
        eid = info.get("id")
        try:
            if eid == "sherpa-onnx":
                from app.runtime.provider.stt.sherpa_onnx_stt import SherpaOnnxSTTProvider

                if info.get("available"):
                    info["model_ready"] = SherpaOnnxSTTProvider.is_model_ready()
                info["model_types"] = list(SherpaOnnxSTTProvider.SUPPORTED_MODEL_TYPES)
            elif eid == "funasr":
                from app.runtime.provider.stt.funasr_stt import FunASRSTTProvider

                info["model_ready"] = info.get("available", False)
                info["models"] = FunASRSTTProvider.SUPPORTED_MODELS
            elif eid == "faster-whisper":
                from app.runtime.provider.stt.faster_whisper_stt import (
                    MODEL_SIZES as FW_MODEL_SIZES,
                )

                info["model_ready"] = info.get("available", False)
                info["model_sizes"] = list(FW_MODEL_SIZES.keys())
        except (ImportError, AttributeError) as e:
            logger.debug(f"[API] STT engines extra info failed for [{eid}]: {e}")

    return ok({
        "engines": engines,
        "fallback_order": STT_FALLBACK_ORDER,
        "device": detect_compute_device(),
    })


# ---------------------------------------------------------------------------
# v0.5 语音配置/画像端点（voice-model-market.md §7.4）
# ---------------------------------------------------------------------------

class VoiceConfigUpdate(BaseModel):
    """PUT /voice/config 请求体（合并式更新，字段可选）."""

    tts: dict | None = None
    stt: dict | None = None
    translation: dict | None = None


class AvatarBindingUpdate(BaseModel):
    """PUT /voice/avatar-bindings/{model_id} 请求体."""

    voice: str | None = None
    voice_lang: str | None = None
    engine: str | None = None
    model: str | None = None
    default_expression: str | None = None
    expression_map: dict | None = None


@voice_router.get("/config")
async def get_voice_config():
    """读取全局语音配置（voice_config，config_items 权威源）."""
    from app.services.voice_config_store import luominest_voice_config_store

    return ok(luominest_voice_config_store.get_voice_config())


@voice_router.put("/config")
async def put_voice_config(update: VoiceConfigUpdate):
    """写入全局语音配置（合并式；语言/引擎字段校验）."""
    from app.services.voice_config_store import luominest_voice_config_store

    patch: dict = {}
    if update.tts is not None:
        tts = dict(update.tts)
        lang = tts.get("lang")
        if lang is not None and lang not in SUPPORTED_TTS_LANGUAGES:
            return fail(
                f"tts.lang 必须是 {'/'.join(SUPPORTED_TTS_LANGUAGES)} 之一",
                err_code="VOICE_CONFIG_INVALID",
                status_code=422,
            )
        patch["tts"] = tts
    if update.stt is not None:
        patch["stt"] = dict(update.stt)
    if update.translation is not None:
        patch["translation"] = dict(update.translation)

    saved = luominest_voice_config_store.save_voice_config(patch)
    return ok(saved)


@voice_router.get("/avatar-bindings")
async def get_avatar_bindings():
    """读取全部皮套音色绑定（voice.avatar_bindings.*）."""
    from app.services.voice_config_store import luominest_voice_config_store

    return ok(luominest_voice_config_store.get_avatar_bindings())


@voice_router.put("/avatar-bindings/{model_id}")
async def put_avatar_binding(model_id: str, update: AvatarBindingUpdate):
    """写入皮套音色绑定（落库，替代旧 avatar.py 直改文件）."""
    from app.services.voice_config_store import luominest_voice_config_store

    patch = update.model_dump(exclude_none=True)
    saved = luominest_voice_config_store.save_avatar_binding(model_id, patch)
    return ok(saved)
