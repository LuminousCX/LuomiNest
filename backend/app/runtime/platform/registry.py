import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from loguru import logger

from app.runtime.platform.base import BasePlatformAdapter
from app.runtime.platform.platform_logger import platform_logger


class PlatformStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class PlatformAdapterType:
    name: str
    display_name: str
    description: str
    adapter_cls: type[BasePlatformAdapter]
    config_template: dict[str, Any] = field(default_factory=dict)
    config_metadata: dict[str, Any] = field(default_factory=dict)
    icon: str = "Globe"
    category: str = "general"
    support_streaming: bool = False
    support_proactive: bool = True


@dataclass
class PlatformInstance:
    instance_id: str
    adapter_type: str
    name: str
    config: dict[str, Any]
    status: PlatformStatus = PlatformStatus.PENDING
    adapter: BasePlatformAdapter | None = None
    message_count: int = 0
    last_sync: str = ""
    error_message: str = ""
    created_at: str = ""
    updated_at: str = ""


_adapter_types: dict[str, PlatformAdapterType] = {}
_instances: dict[str, PlatformInstance] = {}
_instance_tasks: dict[str, asyncio.Task] = {}


def register_adapter_type(
    name: str,
    display_name: str,
    description: str,
    adapter_cls: type[BasePlatformAdapter],
    config_template: dict[str, Any] | None = None,
    config_metadata: dict[str, Any] | None = None,
    icon: str = "Globe",
    category: str = "general",
    support_streaming: bool = False,
    support_proactive: bool = True,
) -> None:
    if name in _adapter_types:
        logger.warning(f"[PlatformRegistry] Adapter type '{name}' already registered, overwriting")
    _adapter_types[name] = PlatformAdapterType(
        name=name,
        display_name=display_name,
        description=description,
        adapter_cls=adapter_cls,
        config_template=config_template or {},
        config_metadata=config_metadata or {},
        icon=icon,
        category=category,
        support_streaming=support_streaming,
        support_proactive=support_proactive,
    )
    logger.info(f"[PlatformRegistry] Registered adapter type: {name} ({display_name})")


def list_adapter_types() -> list[PlatformAdapterType]:
    return list(_adapter_types.values())


def get_adapter_type(name: str) -> PlatformAdapterType | None:
    return _adapter_types.get(name)


def create_instance(
    instance_id: str,
    adapter_type: str,
    name: str,
    config: dict[str, Any],
    created_at: str = "",
    updated_at: str = "",
    message_count: int = 0,
    last_sync: str = "",
) -> PlatformInstance:
    at = _adapter_types.get(adapter_type)
    if not at:
        raise ValueError(f"Unknown adapter type: {adapter_type}")

    merged_config = {**at.config_template, **config}
    adapter = at.adapter_cls()

    inst = PlatformInstance(
        instance_id=instance_id,
        adapter_type=adapter_type,
        name=name,
        config=merged_config,
        status=PlatformStatus.PENDING,
        adapter=adapter,
        message_count=message_count,
        last_sync=last_sync,
        created_at=created_at,
        updated_at=updated_at,
    )
    _instances[instance_id] = inst
    logger.info(f"[PlatformRegistry] Created instance: {instance_id} ({adapter_type}) - {name}")
    platform_logger.log(instance_id, "info", "instance_created", f"平台实例已创建: {name}", adapter_type=adapter_type)
    return inst


def get_instance(instance_id: str) -> PlatformInstance | None:
    return _instances.get(instance_id)


def list_instances() -> list[PlatformInstance]:
    return list(_instances.values())


def remove_instance(instance_id: str) -> bool:
    if instance_id not in _instances:
        return False
    inst = _instances[instance_id]
    if inst.status == PlatformStatus.RUNNING:
        logger.warning(f"[PlatformRegistry] Cannot remove running instance: {instance_id}")
        return False
    if instance_id in _instance_tasks:
        task = _instance_tasks.pop(instance_id)
        task.cancel()
    del _instances[instance_id]
    logger.info(f"[PlatformRegistry] Removed instance: {instance_id}")
    platform_logger.log(instance_id, "info", "instance_removed", f"平台实例已移除: {inst.name}", adapter_type=inst.adapter_type)
    return True


async def start_instance(instance_id: str) -> bool:
    inst = _instances.get(instance_id)
    if not inst:
        logger.error(f"[PlatformRegistry] Instance not found: {instance_id}")
        return False
    if inst.status == PlatformStatus.RUNNING:
        logger.warning(f"[PlatformRegistry] Instance already running: {instance_id}")
        return True
    if not inst.adapter:
        logger.error(f"[PlatformRegistry] Instance has no adapter: {instance_id}")
        return False

    try:
        await inst.adapter.start()
        inst.status = PlatformStatus.RUNNING
        inst.error_message = ""
        logger.success(f"[PlatformRegistry] Started instance: {instance_id} ({inst.adapter_type})")
        platform_logger.log(instance_id, "success", "instance_started", f"平台实例已启动: {inst.name}", adapter_type=inst.adapter_type, details={"status": "running"})
        return True
    except Exception as e:
        inst.status = PlatformStatus.ERROR
        inst.error_message = str(e)
        logger.error(f"[PlatformRegistry] Failed to start instance {instance_id}: {e}")
        platform_logger.log(instance_id, "error", "start_failed", f"启动失败: {e}", adapter_type=inst.adapter_type, details={"error": str(e)})
        return False


async def stop_instance(instance_id: str) -> bool:
    inst = _instances.get(instance_id)
    if not inst:
        logger.error(f"[PlatformRegistry] Instance not found: {instance_id}")
        return False
    if inst.status != PlatformStatus.RUNNING:
        inst.status = PlatformStatus.STOPPED
        return True

    try:
        if inst.adapter:
            await inst.adapter.stop()
        inst.status = PlatformStatus.STOPPED
        if instance_id in _instance_tasks:
            task = _instance_tasks.pop(instance_id)
            task.cancel()
        logger.success(f"[PlatformRegistry] Stopped instance: {instance_id}")
        platform_logger.log(instance_id, "info", "instance_stopped", f"平台实例已停止: {inst.name}", adapter_type=inst.adapter_type, details={"status": "stopped"})
        return True
    except Exception as e:
        inst.status = PlatformStatus.ERROR
        inst.error_message = str(e)
        logger.error(f"[PlatformRegistry] Failed to stop instance {instance_id}: {e}")
        platform_logger.log(instance_id, "error", "stop_failed", f"停止失败: {e}", adapter_type=inst.adapter_type, details={"error": str(e)})
        return False


def increment_message_count(instance_id: str) -> None:
    inst = _instances.get(instance_id)
    if inst:
        inst.message_count += 1


def update_last_sync(instance_id: str, last_sync: str) -> None:
    inst = _instances.get(instance_id)
    if inst:
        inst.last_sync = last_sync
