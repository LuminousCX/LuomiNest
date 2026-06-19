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
