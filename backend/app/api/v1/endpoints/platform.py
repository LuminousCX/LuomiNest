import uuid
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, ConfigDict
from loguru import logger

from app.core.utils import utc_now, require_value, ok
from app.core.exceptions import NotFoundError, LuomiNestError, ValidationError
from app.api.v1.deps import get_platforms_store, get_conversation_store
from app.runtime.platform.registry import (
    PlatformStatus,
    list_adapter_types,
    get_adapter_type,
    create_instance,
    get_instance,
    list_instances,
    remove_instance,
    start_instance,
    stop_instance,
)
from app.runtime.platform.platform_logger import platform_logger
import app.runtime.platform.adapters


router = APIRouter(prefix="/platforms", tags=["platforms"])


class PlatformTypeResponse(BaseModel):
    name: str
    display_name: str = Field(alias="displayName")
    description: str
    icon: str
    category: str
    config_template: dict = Field(alias="configTemplate", default_factory=dict)
    config_metadata: dict = Field(alias="configMetadata", default_factory=dict)
    support_streaming: bool = Field(alias="supportStreaming", default=False)
    support_proactive: bool = Field(alias="supportProactive", default=True)

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class PlatformInstanceCreate(BaseModel):
    adapter_type: str = Field(alias="adapterType")
    name: str
    config: dict = Field(default_factory=dict)
    enable: bool = True

    model_config = ConfigDict(populate_by_name=True)


class PlatformInstanceUpdate(BaseModel):
    name: str | None = None
    config: dict | None = None
    enable: bool | None = None

    model_config = ConfigDict(populate_by_name=True)


class PlatformInstanceResponse(BaseModel):
    id: str
    adapter_type: str = Field(alias="adapterType")
    name: str
    config: dict = Field(default_factory=dict)
    status: str
    enable: bool = True
    message_count: int = Field(alias="messageCount", default=0)
    last_sync: str = Field(alias="lastSync", default="")
    error_message: str = Field(alias="errorMessage", default="")
    icon: str = "Globe"
    category: str = "general"
    display_name: str = Field(alias="displayName", default="")
    created_at: str = Field(alias="createdAt", default="")
    updated_at: str = Field(alias="updatedAt", default="")
    model_config_data: dict = Field(alias="modelConfig", default_factory=dict)

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class PlatformConversationResponse(BaseModel):
    id: str
    platform_instance_id: str = Field(alias="platformInstanceId")
    platform_name: str = Field(alias="platformName")
    title: str
    preview: str
    time: str
    message_count: int = Field(alias="messageCount", default=0)

    model_config = ConfigDict(populate_by_name=True)


class PlatformMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    timestamp: str = ""
    sender_name: str = ""
    is_group: bool = False
    image_urls: list[str] = Field(default_factory=list)
    model: str = ""
    provider: str = ""

    model_config = ConfigDict(populate_by_name=True)


class PlatformModelConfigUpdate(BaseModel):
    provider: str | None = None
    model: str | None = None
    system_prompt: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=128_000)
    color: str | None = None
    avatar: str | None = None

    model_config = ConfigDict(populate_by_name=True)


def _instance_to_response(inst) -> PlatformInstanceResponse:
    at = get_adapter_type(inst.adapter_type)
    return PlatformInstanceResponse(
        id=inst.instance_id,
        adapter_type=inst.adapter_type,
        name=inst.name,
        config=inst.config,
        status=inst.status.value if isinstance(inst.status, PlatformStatus) else inst.status,
        enable=inst.config.get("enable", True),
        message_count=inst.message_count,
        last_sync=inst.last_sync,
        error_message=inst.error_message,
        icon=at.icon if at else "Globe",
        category=at.category if at else "general",
        display_name=at.display_name if at else inst.adapter_type,
        created_at=inst.created_at,
        updated_at=inst.updated_at,
        model_config_data=inst.config.get("model_config", {}) or {},
    )


def _load_persisted_instances():
    # lifespan 调用（非路由），无法 Depends 注入，经容器取同一门面单例
    from app.core.container import container
    platforms_store = container.platforms_store
    for inst_data in platforms_store.values():
        inst_id = inst_data.get("id", "")
        adapter_type = inst_data.get("adapter_type", "")
        name = inst_data.get("name", "")
        config = inst_data.get("config", {})
        if not inst_id or not adapter_type:
            continue
        try:
            create_instance(
                instance_id=inst_id,
                adapter_type=adapter_type,
                name=name,
                config=config,
                created_at=inst_data.get("created_at", ""),
                updated_at=inst_data.get("updated_at", ""),
                message_count=inst_data.get("message_count", 0),
                last_sync=inst_data.get("last_sync", ""),
            )
            if inst_data.get("enable", True):
                inst = get_instance(inst_id)
                if inst:
                    inst.status = PlatformStatus.STOPPED
        except ValueError as e:
            logger.warning(f"[PlatformAPI] Failed to load instance {inst_id}: {e}")


@router.get("/types", response_model=list[PlatformTypeResponse])
async def get_platform_types():
    logger.info("[API] GET /platforms/types - Listing platform adapter types")
    types = list_adapter_types()
    return [
        PlatformTypeResponse(
            name=t.name,
            display_name=t.display_name,
            description=t.description,
            icon=t.icon,
            category=t.category,
            config_template=t.config_template,
            config_metadata=t.config_metadata,
            support_streaming=t.support_streaming,
            support_proactive=t.support_proactive,
        )
        for t in types
    ]


@router.get("/instances", response_model=list[PlatformInstanceResponse])
async def list_platform_instances():
    logger.info("[API] GET /platforms/instances - Listing platform instances")
    instances = list_instances()
    return [_instance_to_response(inst) for inst in instances]


@router.post("/instances", response_model=PlatformInstanceResponse)
async def create_platform_instance(
    request: PlatformInstanceCreate,
    platforms_store=Depends(get_platforms_store),
):
    logger.info(f"[API] POST /platforms/instances - Creating: adapter_type={request.adapter_type}, name={request.name}")
    at = get_adapter_type(request.adapter_type)
    if not at:
        raise NotFoundError(f"Adapter type '{request.adapter_type}' not found")

    instance_id = str(uuid.uuid4())
    now = utc_now()

    config = {**request.config, "enable": request.enable}

    inst = create_instance(
        instance_id=instance_id,
        adapter_type=request.adapter_type,
        name=request.name,
        config=config,
        created_at=now,
        updated_at=now,
    )

    await platforms_store.set_async(instance_id, {
        "id": instance_id,
        "adapter_type": request.adapter_type,
        "name": request.name,
        "config": config,
        "enable": request.enable,
        "message_count": 0,
        "last_sync": "",
        "created_at": now,
        "updated_at": now,
    })

    if request.enable:
        await start_instance(instance_id)
        await platforms_store.update_async(instance_id, {
            "status": inst.status.value,
            "last_sync": utc_now(),
        })

    logger.success(f"[API] POST /platforms/instances - Created: id={instance_id}")
    return _instance_to_response(inst)


@router.get("/instances/{instance_id}", response_model=PlatformInstanceResponse)
async def get_platform_instance(instance_id: str):
    logger.info(f"[API] GET /platforms/instances/{instance_id}")
    inst = require_value(get_instance(instance_id), "Platform instance", instance_id)
    return _instance_to_response(inst)


@router.patch("/instances/{instance_id}", response_model=PlatformInstanceResponse)
async def update_platform_instance(
    instance_id: str,
    request: PlatformInstanceUpdate,
    platforms_store=Depends(get_platforms_store),
):
    logger.info(f"[API] PATCH /platforms/instances/{instance_id}")
    inst = require_value(get_instance(instance_id), "Platform instance", instance_id)

    update_data = request.model_dump(exclude_unset=True, by_alias=False)
    now = utc_now()

    if "name" in update_data and update_data["name"] is not None:
        inst.name = update_data["name"]
    if "config" in update_data and update_data["config"] is not None:
        merged = {**inst.config, **update_data["config"]}
        inst.config = merged
    if "enable" in update_data and update_data["enable"] is not None:
        inst.config["enable"] = update_data["enable"]
        if update_data["enable"] and inst.status != PlatformStatus.RUNNING:
            await start_instance(instance_id)
        elif not update_data["enable"] and inst.status == PlatformStatus.RUNNING:
            await stop_instance(instance_id)

    inst.updated_at = now

    persist_data = await platforms_store.get_async(instance_id, {})
    persist_data.update({
        "name": inst.name,
        "config": inst.config,
        "enable": inst.config.get("enable", True),
        "updated_at": now,
        "status": inst.status.value,
    })
    await platforms_store.set_async(instance_id, persist_data)

    logger.success(f"[API] PATCH /platforms/instances/{instance_id} - Updated")
    return _instance_to_response(inst)


@router.delete("/instances/{instance_id}")
async def delete_platform_instance(
    instance_id: str,
    platforms_store=Depends(get_platforms_store),
):
    logger.info(f"[API] DELETE /platforms/instances/{instance_id}")
    inst = require_value(get_instance(instance_id), "Platform instance", instance_id)

    if inst.status == PlatformStatus.RUNNING:
        await stop_instance(instance_id)

    remove_instance(instance_id)
    await platforms_store.delete_async(instance_id)
    logger.success(f"[API] DELETE /platforms/instances/{instance_id} - Deleted")
    return ok({"deleted": True})


@router.post("/instances/{instance_id}/start", response_model=PlatformInstanceResponse)
async def start_platform_instance(
    instance_id: str,
    platforms_store=Depends(get_platforms_store),
):
    logger.info(f"[API] POST /platforms/instances/{instance_id}/start")
    inst = require_value(get_instance(instance_id), "Platform instance", instance_id)

    success = await start_instance(instance_id)
    if not success:
        raise LuomiNestError(
            f"Failed to start instance: {inst.error_message}",
            code="PLATFORM_START_FAILED",
            status_code=500,
        )

    now = utc_now()
    inst.last_sync = now
    await platforms_store.update_async(instance_id, {
        "status": PlatformStatus.RUNNING.value,
        "last_sync": now,
    })

    return _instance_to_response(inst)


@router.post("/instances/{instance_id}/stop", response_model=PlatformInstanceResponse)
async def stop_platform_instance(
    instance_id: str,
    platforms_store=Depends(get_platforms_store),
):
    logger.info(f"[API] POST /platforms/instances/{instance_id}/stop")
    inst = require_value(get_instance(instance_id), "Platform instance", instance_id)

    await stop_instance(instance_id)
    await platforms_store.update_async(instance_id, {
        "status": PlatformStatus.STOPPED.value,
    })

    return _instance_to_response(inst)


@router.get("/instances/{instance_id}/conversations", response_model=list[PlatformConversationResponse])
async def get_platform_conversations(
    instance_id: str,
    conversation_store=Depends(get_conversation_store),
):
    logger.info(f"[API] GET /platforms/instances/{instance_id}/conversations")
    inst = require_value(get_instance(instance_id), "Platform instance", instance_id)

    from app.runtime.platform.session import list_platform_sessions

    sessions = list_platform_sessions(instance_id)
    result = []
    for s in sessions:
        conv_id = s.get("conversation_id", "")
        if not conv_id:
            continue
        conv = await conversation_store.get_async(conv_id)
        if not conv:
            continue

        messages = conv.get("messages", [])
        preview = ""
        for m in reversed(messages):
            content = m.get("content", "")
            if isinstance(content, list):
                text_parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
                preview = text_parts[0] if text_parts else ""
            else:
                preview = str(content)
            if preview:
                break

        result.append(PlatformConversationResponse(
            id=conv_id,
            platform_instance_id=instance_id,
            platform_name=s.get("platform_name", inst.name),
            title=conv.get("title", ""),
            preview=preview[:100],
            time=conv.get("updated_at", conv.get("created_at", "")),
            message_count=len(messages),
        ))

    result.sort(key=lambda c: c.time, reverse=True)
    return result


class NewConversationRequest(BaseModel):
    session_id: str | None = None

    model_config = ConfigDict(populate_by_name=True)


@router.post("/instances/{instance_id}/conversations/new")
async def create_new_platform_conversation(instance_id: str, request: NewConversationRequest | None = None):
    """为平台实例创建全新对话（对应 /new 命令）。

    如果提供 session_id，则为该会话创建新对话；否则使用通用 session_id。
    """
    logger.info(f"[API] POST /platforms/instances/{instance_id}/conversations/new")
    inst = require_value(get_instance(instance_id), "Platform instance", instance_id)

    from app.runtime.platform.session import create_new_conversation

    session_id = (request.session_id if request and request.session_id else None) or f"default-{instance_id[:8]}"

    try:
        result = await create_new_conversation(instance_id, session_id)
    except Exception as e:
        # 服务端日志保留完整异常信息用于诊断；对外只暴露固定错误消息，避免泄漏内部细节
        logger.error(f"[API] Failed to create new conversation: {e}", exc_info=True)
        raise LuomiNestError(
            "Failed to create new conversation",
            code="CONVERSATION_CREATE_FAILED",
            status_code=500,
        ) from e

    return ok({
        "id": result["id"],
        "title": result["title"],
        "created_at": result["created_at"],
    })


@router.get("/instances/{instance_id}/conversations/{conversation_id}/messages")
async def get_platform_conversation_messages(
    instance_id: str,
    conversation_id: str,
    conversation_store=Depends(get_conversation_store),
):
    """获取平台实例下指定对话的详细消息列表（含图片消息）。"""
    logger.info(f"[API] GET /platforms/instances/{instance_id}/conversations/{conversation_id}/messages")
    inst = require_value(get_instance(instance_id), "Platform instance", instance_id)

    conv = await conversation_store.get_async(conversation_id)
    if not conv:
        raise NotFoundError(f"Conversation {conversation_id} not found")

    conv_platform = conv.get("platform", {}) or {}
    if conv_platform.get("instance_id") != instance_id:
        raise NotFoundError(f"Conversation {conversation_id} does not belong to instance {instance_id}")

    messages = []
    for msg in conv.get("messages", []):
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if isinstance(content, list):
            text_parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
            image_parts = [p.get("image_url", {}).get("url", "") for p in content if isinstance(p, dict) and p.get("type") == "image_url"]
            content_text = "\n".join(text_parts)
            image_urls = [u for u in image_parts if u]
        else:
            content_text = str(content)
            image_urls = msg.get("image_urls", []) or []

        platform_info = msg.get("platform", {}) or {}
        messages.append(PlatformMessageResponse(
            id=msg.get("id", ""),
            role=role,
            content=content_text,
            timestamp=msg.get("timestamp", msg.get("created_at", "")),
            sender_name=platform_info.get("sender_name", ""),
            is_group=platform_info.get("is_group", False),
            image_urls=image_urls,
            model=msg.get("model", ""),
            provider=msg.get("provider", ""),
        ))

    return {
        "error": None,
        "data": {
            "conversation_id": conversation_id,
            "title": conv.get("title", ""),
            "instance_id": instance_id,
            "platform_name": conv_platform.get("platform_name", inst.name),
            "sender_name": conv_platform.get("sender_name", ""),
            "is_group": conv_platform.get("is_group", False),
            "messages": [m.model_dump(by_alias=True) for m in messages],
            "message_count": len(messages),
        },
    }


@router.get("/instances/{instance_id}/model_config")
async def get_platform_model_config(instance_id: str):
    """获取平台实例的模型配置（含主 Agent 默认值回退信息）。"""
    logger.info(f"[API] GET /platforms/instances/{instance_id}/model_config")
    inst = require_value(get_instance(instance_id), "Platform instance", instance_id)

    from app.runtime.platform.main_agent_config import (
        load_luominest_main_agent_config,
        resolve_main_agent_provider_model,
    )
    from app.runtime.provider.llm.adapter import llm_adapter

    main_config = load_luominest_main_agent_config()
    main_provider, main_model = resolve_main_agent_provider_model()

    main_provider_name = main_provider
    main_supports_vision = False
    try:
        provider_inst = llm_adapter.get_provider(main_provider)
        main_provider_name = getattr(provider_inst, "display_name", None) or main_provider
        main_supports_vision = provider_inst.supports_multimodal(main_model)
    except Exception as e:
        logger.warning(f"[PlatformAPI] Failed to resolve main provider info: {e}")

    inst_cfg = inst.config.get("model_config", {}) or {}
    instance_provider = inst_cfg.get("provider", "")
    instance_model = inst_cfg.get("model", "")

    instance_provider_name = instance_provider
    instance_supports_vision = False
    is_overridden = bool(instance_provider or instance_model)
    if is_overridden:
        try:
            provider_inst = llm_adapter.get_provider(instance_provider or main_provider)
            instance_provider_name = getattr(provider_inst, "display_name", None) or (instance_provider or main_provider)
            instance_supports_vision = provider_inst.supports_multimodal(instance_model or main_model)
        except Exception as e:
            logger.warning(f"[PlatformAPI] Failed to resolve instance provider info: {e}")

    return {
        "error": None,
        "data": {
            "instance_id": instance_id,
            "is_overridden": is_overridden,
            "instance_config": {
                "provider": instance_provider,
                "model": instance_model,
                "system_prompt": inst_cfg.get("system_prompt", ""),
                "temperature": inst_cfg.get("temperature"),
                "max_tokens": inst_cfg.get("max_tokens"),
            },
            "main_agent": {
                "provider": main_provider,
                "provider_name": main_provider_name,
                "model": main_model,
                "supports_multimodal": main_supports_vision,
                "system_prompt": main_config.get("system_prompt", ""),
                "temperature": main_config.get("temperature", 0.7),
                "max_tokens": main_config.get("max_tokens", 4096),
            },
            "effective": {
                "provider": instance_provider or main_provider,
                "provider_name": instance_provider_name if is_overridden else main_provider_name,
                "model": instance_model or main_model,
                "supports_multimodal": instance_supports_vision if is_overridden else main_supports_vision,
            },
            "category": inst.adapter_type,
        },
    }


@router.patch("/instances/{instance_id}/model_config")
async def update_platform_model_config(
    instance_id: str,
    request: PlatformModelConfigUpdate,
    platforms_store=Depends(get_platforms_store),
):
    """更新平台实例的模型配置（空值表示继承主 Agent）。"""
    logger.info(f"[API] PATCH /platforms/instances/{instance_id}/model_config")
    inst = require_value(get_instance(instance_id), "Platform instance", instance_id)

    model_cfg = inst.config.get("model_config", {}) or {}
    updates = request.model_dump(exclude_unset=True)

    for key, val in updates.items():
        if val is None:
            model_cfg.pop(key, None)
        else:
            model_cfg[key] = val

    inst.config["model_config"] = model_cfg
    inst.updated_at = utc_now()

    persist_data = await platforms_store.get_async(instance_id, {})
    persist_data.setdefault("config", {})
    persist_data["config"]["model_config"] = model_cfg
    persist_data["updated_at"] = inst.updated_at
    await platforms_store.set_async(instance_id, persist_data)

    platform_logger.log(
        instance_id, "info", "model_config_updated",
        f"模型配置已更新: {model_cfg}",
        adapter_type=inst.adapter_type,
        details={"model_config": model_cfg, "is_overridden": bool(model_cfg.get("provider") or model_cfg.get("model"))},
    )

    return ok({"updated": True, "model_config": model_cfg})


class PlatformLogResponse(BaseModel):
    entries: list[dict]
    total: int

    model_config = ConfigDict(populate_by_name=True)


@router.get("/instances/{instance_id}/logs")
async def get_platform_instance_logs(
    instance_id: str,
    level: str | None = None,
    event: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    logger.info(f"[API] GET /platforms/instances/{instance_id}/logs")
    inst = require_value(get_instance(instance_id), "Platform instance", instance_id)

    result = platform_logger.get_logs(
        instance_id=instance_id,
        level=level,
        event=event,
        limit=min(limit, 500),
        offset=offset,
    )
    return ok(result)


@router.get("/logs")
async def get_all_platform_logs(
    level: str | None = None,
    event: str | None = None,
    limit: int = 200,
    offset: int = 0,
):
    logger.info("[API] GET /platforms/logs - Getting all platform logs")
    result = platform_logger.get_all_logs(
        level=level,
        event=event,
        limit=min(limit, 500),
        offset=offset,
    )
    return ok(result)


@router.delete("/instances/{instance_id}/logs")
async def clear_platform_instance_logs(instance_id: str):
    logger.info(f"[API] DELETE /platforms/instances/{instance_id}/logs")
    inst = require_value(get_instance(instance_id), "Platform instance", instance_id)

    success = platform_logger.clear_logs(instance_id)
    return ok({"cleared": success})


@router.get("/logs/summary")
async def get_platform_logs_summary():
    logger.info("[API] GET /platforms/logs/summary")
    summary = platform_logger.get_summary()
    return ok(summary)


@router.get("/stats")
async def get_platform_stats():
    logger.info("[API] GET /platforms/stats - Getting platform statistics")
    instances = list_instances()
    total = len(instances)
    active = sum(1 for i in instances if i.status == PlatformStatus.RUNNING)
    total_messages = sum(i.message_count for i in instances)
    return ok({
            "totalPlatforms": total,
            "activeConnections": active,
            "totalMessages": total_messages,
        })


@router.get("/instances/{instance_id}/webhook")
async def platform_webhook_verify(
    instance_id: str,
    msg_signature: str | None = None,
    signature: str | None = None,
    timestamp: str | None = None,
    nonce: str | None = None,
    echostr: str | None = None,
):
    """平台 Webhook URL 验证（企业微信/公众号 GET 请求）。"""
    from fastapi import Request
    from fastapi.responses import PlainTextResponse

    inst = require_value(get_instance(instance_id), "Platform instance", instance_id)
    if not inst.adapter:
        raise NotFoundError(f"Platform instance {instance_id} not found")

    adapter = inst.adapter
    sig = msg_signature or signature or ""

    if hasattr(adapter, "verify_url"):
        result = await adapter.verify_url(sig, timestamp or "", nonce or "", echostr or "")
        if result is not None:
            return PlainTextResponse(content=result)
        return PlainTextResponse(content="signature mismatch", status_code=403)

    return PlainTextResponse(content=echostr or "")


@router.post("/instances/{instance_id}/webhook")
async def platform_webhook_receive(instance_id: str, request: dict):
    """平台 Webhook 消息接收（QQ官方/企业微信/公众号 POST 请求）。

    请求体由 FastAPI 解析为 dict（JSON）或由调用方传入 XML 解析后的 dict。
    对于企业微信/公众号的 XML 格式，前端代理层需先转换为 JSON 或直接调用适配器。
    """
    inst = require_value(get_instance(instance_id), "Platform instance", instance_id)
    if not inst.adapter:
        raise NotFoundError(f"Platform instance {instance_id} not found")

    adapter = inst.adapter
    adapter_type = inst.adapter_type

    try:
        if adapter_type == "qq_official" and hasattr(adapter, "handle_webhook"):
            await adapter.handle_webhook(request)
            return ok({"received": True})

        if adapter_type == "wechat_work" and hasattr(adapter, "handle_webhook"):
            body = request.get("body", "")
            if not body:
                return ok({"received": True, "note": "empty body"})
            msg_signature = request.get("msg_signature", "")
            timestamp = request.get("timestamp", "")
            nonce = request.get("nonce", "")
            await adapter.handle_webhook(msg_signature, timestamp, nonce, body)
            return ok({"received": True})

        if adapter_type == "wechat_mp" and hasattr(adapter, "handle_webhook"):
            body = request.get("body", "")
            if not body:
                return ok({"received": True, "note": "empty body"})
            signature = request.get("signature", "")
            timestamp = request.get("timestamp", "")
            nonce = request.get("nonce", "")
            reply = await adapter.handle_webhook(signature, timestamp, nonce, body)
            from fastapi.responses import PlainTextResponse
            return PlainTextResponse(content=reply or "")

        return ok({"received": True, "note": "adapter does not support webhook"})
    except Exception as e:
        logger.error(f"[API] Webhook handling failed for {instance_id}: {e}")
        raise LuomiNestError(f"Webhook handling failed: {e}", code="PLATFORM_WEBHOOK_FAILED", status_code=500)


@router.post("/instances/{instance_id}/send")
async def send_platform_message(
    instance_id: str,
    target: str = "",
    content: str = "",
):
    """主动向平台发送消息（主 Agent 主动推送场景）。"""
    from app.services.platform_router import send_platform_response
    from app.runtime.platform.base import PlatformResponse

    inst = require_value(get_instance(instance_id), "Platform instance", instance_id)

    if not target or not content:
        raise ValidationError("target and content are required")

    response = PlatformResponse(content=content, message_type="text")
    success = await send_platform_response(instance_id, target, response)
    return ok({"sent": success})


@router.get("/instances/{instance_id}/sessions")
async def list_platform_sessions(instance_id: str):
    """列出平台实例的所有会话映射。"""
    from app.runtime.platform.session import list_platform_sessions as list_sessions

    inst = get_instance(instance_id)
    if not inst:
        raise NotFoundError(f"Platform instance {instance_id} not found")

    sessions = list_sessions(instance_id)
    return ok(sessions)


@router.get("/main_agent")
async def get_main_agent_info():
    """获取主 Agent 的 LLM 配置信息（供前端平台管理页面展示）。

    返回字段：
    - provider: 主 Agent 使用的供应商 ID
    - provider_name: 供应商显示名称
    - model: 主 Agent 使用的模型 ID
    - supports_multimodal: 当前模型是否支持图片识别
    - system_prompt: 主 Agent 系统提示词
    - temperature / max_tokens: 生成参数
    """
    from app.runtime.platform.main_agent_config import (
        load_luominest_main_agent_config,
        resolve_main_agent_provider_model,
    )
    from app.runtime.provider.llm.adapter import llm_adapter

    config = load_luominest_main_agent_config()
    provider, model = resolve_main_agent_provider_model()

    provider_name = provider
    supports_multimodal = False
    try:
        provider_inst = llm_adapter.get_provider(provider)
        provider_name = getattr(provider_inst, "display_name", None) or provider
        supports_multimodal = provider_inst.supports_multimodal(model)
    except Exception as e:
        logger.warning(f"[PlatformAPI] Failed to resolve provider info: {e}")

    return {
        "error": None,
        "data": {
            "provider": provider,
            "provider_name": provider_name,
            "model": model,
            "supports_multimodal": supports_multimodal,
            "system_prompt": config.get("system_prompt", ""),
            "temperature": config.get("temperature", 0.7),
            "max_tokens": config.get("max_tokens", 4096),
            "color": config.get("color", ""),
            "avatar": config.get("avatar"),
        },
    }


@router.patch("/main_agent")
async def update_main_agent_info(request: PlatformModelConfigUpdate):
    """更新主 Agent 的 LLM 配置（系统提示词、温度、最大 tokens、provider、model）。

    前端可在此切换主 Agent 使用的供应商/模型，平台消息路由会自动复用新配置。
    """
    from app.runtime.platform.main_agent_config import (
        load_luominest_main_agent_config,
        save_luominest_main_agent_config,
    )

    current = load_luominest_main_agent_config()
    updated_fields: list[str] = []

    # Pydantic 已做类型转换和范围校验，直接遍历已设置字段
    update_data = request.model_dump(exclude_unset=True)
    for key in ("provider", "model", "system_prompt", "temperature", "max_tokens", "color", "avatar"):
        if key in update_data and update_data[key] is not None:
            new_val = update_data[key]
            if current.get(key) != new_val:
                current[key] = new_val
                updated_fields.append(key)

    if not updated_fields:
        return ok({"updated": False, "note": "no changes"})

    try:
        save_luominest_main_agent_config(current)
        logger.info(f"[PlatformAPI] Main agent config updated: {updated_fields}")
    except Exception as e:
        raise LuomiNestError(
            f"Failed to persist main agent config: {e}",
            code="MAIN_AGENT_CONFIG_PERSIST_FAILED",
            status_code=500,
        )

    return ok({"updated": True, "fields": updated_fields})
