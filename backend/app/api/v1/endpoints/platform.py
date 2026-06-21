import uuid
from datetime import datetime, timezone
from fastapi import APIRouter
from pydantic import BaseModel, Field, ConfigDict
from loguru import logger

from app.infrastructure.database.json_store import platforms_store
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
    )


def _load_persisted_instances():
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


_load_persisted_instances()


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
async def create_platform_instance(request: PlatformInstanceCreate):
    logger.info(f"[API] POST /platforms/instances - Creating: adapter_type={request.adapter_type}, name={request.name}")
    at = get_adapter_type(request.adapter_type)
    if not at:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Adapter type '{request.adapter_type}' not found")

    instance_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

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
            "last_sync": datetime.now(timezone.utc).isoformat(),
        })

    logger.success(f"[API] POST /platforms/instances - Created: id={instance_id}")
    return _instance_to_response(inst)


@router.get("/instances/{instance_id}", response_model=PlatformInstanceResponse)
async def get_platform_instance(instance_id: str):
    logger.info(f"[API] GET /platforms/instances/{instance_id}")
    inst = get_instance(instance_id)
    if not inst:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Platform instance {instance_id} not found")
    return _instance_to_response(inst)


@router.patch("/instances/{instance_id}", response_model=PlatformInstanceResponse)
async def update_platform_instance(instance_id: str, request: PlatformInstanceUpdate):
    logger.info(f"[API] PATCH /platforms/instances/{instance_id}")
    inst = get_instance(instance_id)
    if not inst:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Platform instance {instance_id} not found")

    update_data = request.model_dump(exclude_unset=True, by_alias=False)
    now = datetime.now(timezone.utc).isoformat()

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
async def delete_platform_instance(instance_id: str):
    logger.info(f"[API] DELETE /platforms/instances/{instance_id}")
    inst = get_instance(instance_id)
    if not inst:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Platform instance {instance_id} not found")

    if inst.status == PlatformStatus.RUNNING:
        await stop_instance(instance_id)

    remove_instance(instance_id)
    await platforms_store.delete_async(instance_id)
    logger.success(f"[API] DELETE /platforms/instances/{instance_id} - Deleted")
    return {"error": None, "data": {"deleted": True}}


@router.post("/instances/{instance_id}/start", response_model=PlatformInstanceResponse)
async def start_platform_instance(instance_id: str):
    logger.info(f"[API] POST /platforms/instances/{instance_id}/start")
    inst = get_instance(instance_id)
    if not inst:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Platform instance {instance_id} not found")

    success = await start_instance(instance_id)
    if not success:
        from app.core.exceptions import LuomiNestError
        raise LuomiNestError(
            f"Failed to start instance: {inst.error_message}",
            code="PLATFORM_START_FAILED",
            status_code=500,
        )

    now = datetime.now(timezone.utc).isoformat()
    inst.last_sync = now
    await platforms_store.update_async(instance_id, {
        "status": PlatformStatus.RUNNING.value,
        "last_sync": now,
    })

    return _instance_to_response(inst)


@router.post("/instances/{instance_id}/stop", response_model=PlatformInstanceResponse)
async def stop_platform_instance(instance_id: str):
    logger.info(f"[API] POST /platforms/instances/{instance_id}/stop")
    inst = get_instance(instance_id)
    if not inst:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Platform instance {instance_id} not found")

    await stop_instance(instance_id)
    await platforms_store.update_async(instance_id, {
        "status": PlatformStatus.STOPPED.value,
    })

    return _instance_to_response(inst)


@router.get("/instances/{instance_id}/conversations", response_model=list[PlatformConversationResponse])
async def get_platform_conversations(instance_id: str):
    logger.info(f"[API] GET /platforms/instances/{instance_id}/conversations")
    inst = get_instance(instance_id)
    if not inst:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Platform instance {instance_id} not found")

    convs_data = (await platforms_store.get_async(instance_id, {})).get("conversations", [])
    result = []
    for c in convs_data:
        result.append(PlatformConversationResponse(
            id=c.get("id", ""),
            platform_instance_id=instance_id,
            platform_name=inst.name,
            title=c.get("title", ""),
            preview=c.get("preview", ""),
            time=c.get("time", ""),
            message_count=c.get("message_count", 0),
        ))
    return result


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
    inst = get_instance(instance_id)
    if not inst:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Platform instance {instance_id} not found")

    result = platform_logger.get_logs(
        instance_id=instance_id,
        level=level,
        event=event,
        limit=min(limit, 500),
        offset=offset,
    )
    return {"error": None, "data": result}


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
    return {"error": None, "data": result}


@router.delete("/instances/{instance_id}/logs")
async def clear_platform_instance_logs(instance_id: str):
    logger.info(f"[API] DELETE /platforms/instances/{instance_id}/logs")
    inst = get_instance(instance_id)
    if not inst:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Platform instance {instance_id} not found")

    success = platform_logger.clear_logs(instance_id)
    return {"error": None, "data": {"cleared": success}}


@router.get("/logs/summary")
async def get_platform_logs_summary():
    logger.info("[API] GET /platforms/logs/summary")
    summary = platform_logger.get_summary()
    return {"error": None, "data": summary}


@router.get("/stats")
async def get_platform_stats():
    logger.info("[API] GET /platforms/stats - Getting platform statistics")
    instances = list_instances()
    total = len(instances)
    active = sum(1 for i in instances if i.status == PlatformStatus.RUNNING)
    total_messages = sum(i.message_count for i in instances)
    return {
        "error": None,
        "data": {
            "totalPlatforms": total,
            "activeConnections": active,
            "totalMessages": total_messages,
        },
    }


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

    inst = get_instance(instance_id)
    if not inst or not inst.adapter:
        from app.core.exceptions import NotFoundError
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
    inst = get_instance(instance_id)
    if not inst or not inst.adapter:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Platform instance {instance_id} not found")

    adapter = inst.adapter
    adapter_type = inst.adapter_type

    try:
        if adapter_type == "qq_official" and hasattr(adapter, "handle_webhook"):
            await adapter.handle_webhook(request)
            return {"error": None, "data": {"received": True}}

        if adapter_type == "wechat_work" and hasattr(adapter, "handle_webhook"):
            body = request.get("body", "")
            if not body:
                return {"error": None, "data": {"received": True, "note": "empty body"}}
            msg_signature = request.get("msg_signature", "")
            timestamp = request.get("timestamp", "")
            nonce = request.get("nonce", "")
            await adapter.handle_webhook(msg_signature, timestamp, nonce, body)
            return {"error": None, "data": {"received": True}}

        if adapter_type == "wechat_mp" and hasattr(adapter, "handle_webhook"):
            body = request.get("body", "")
            if not body:
                return {"error": None, "data": {"received": True, "note": "empty body"}}
            signature = request.get("signature", "")
            timestamp = request.get("timestamp", "")
            nonce = request.get("nonce", "")
            reply = await adapter.handle_webhook(signature, timestamp, nonce, body)
            from fastapi.responses import PlainTextResponse
            return PlainTextResponse(content=reply or "")

        return {"error": None, "data": {"received": True, "note": "adapter does not support webhook"}}
    except Exception as e:
        logger.error(f"[API] Webhook handling failed for {instance_id}: {e}")
        from app.core.exceptions import LuomiNestError
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

    inst = get_instance(instance_id)
    if not inst:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Platform instance {instance_id} not found")

    if not target or not content:
        from app.core.exceptions import ValidationError
        raise ValidationError("target and content are required")

    response = PlatformResponse(content=content, message_type="text")
    success = await send_platform_response(instance_id, target, response)
    return {"error": None, "data": {"sent": success}}


@router.get("/instances/{instance_id}/sessions")
async def list_platform_sessions(instance_id: str):
    """列出平台实例的所有会话映射。"""
    from app.runtime.platform.session import list_platform_sessions as list_sessions

    inst = get_instance(instance_id)
    if not inst:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Platform instance {instance_id} not found")

    sessions = list_sessions(instance_id)
    return {"error": None, "data": sessions}


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
        },
    }


@router.patch("/main_agent")
async def update_main_agent_info(request: dict):
    """更新主 Agent 的 LLM 配置（系统提示词、温度、最大 tokens、provider、model）。

    前端可在此切换主 Agent 使用的供应商/模型，平台消息路由会自动复用新配置。
    """
    import json
    from app.runtime.platform.main_agent_config import (
        _MAIN_AGENT_CONFIG_FILE,
        _ensure_config_dir,
        load_luominest_main_agent_config,
    )

    current = load_luominest_main_agent_config()
    updated_fields: list[str] = []

    for key in ("provider", "model", "system_prompt", "temperature", "max_tokens"):
        if key in request and request[key] is not None:
            new_val = request[key]
            if key in ("temperature", "max_tokens") and new_val is not None:
                try:
                    new_val = float(new_val) if key == "temperature" else int(new_val)
                except (TypeError, ValueError):
                    continue
            if current.get(key) != new_val:
                current[key] = new_val
                updated_fields.append(key)

    if not updated_fields:
        return {"error": None, "data": {"updated": False, "note": "no changes"}}

    _ensure_config_dir()
    try:
        with open(_MAIN_AGENT_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
        logger.info(f"[PlatformAPI] Main agent config updated: {updated_fields}")
    except Exception as e:
        from app.core.exceptions import LuomiNestError
        raise LuomiNestError(
            f"Failed to persist main agent config: {e}",
            code="MAIN_AGENT_CONFIG_PERSIST_FAILED",
            status_code=500,
        )

    return {"error": None, "data": {"updated": True, "fields": updated_fields}}
