import json
from typing import Any

from fastapi import APIRouter
from loguru import logger
from pydantic import BaseModel, Field

from app.runtime.platform.base import PlatformResponse
from app.runtime.platform.registry import get_instance, list_instances
from app.runtime.platform.platform_logger import platform_logger
from app.core.exceptions import LuomiNestError, ValidationError
from app.core.utils import ok


router = APIRouter(prefix="/smart-home", tags=["smart-home"])


# 智能家居平台适配器类型
IOT_ADAPTER_TYPES: tuple[str, ...] = ("mqtt_terminal", "home_assistant", "xiaomi_iot")

# 允许的设备控制动作
ALLOWED_ACTIONS: tuple[str, ...] = (
    "turn_on",
    "turn_off",
    "toggle",
    "set_brightness",
    "set_temperature",
)


class DeviceControlRequest(BaseModel):
    action: str = Field(description="设备控制动作")
    params: dict[str, Any] = Field(default_factory=dict, description="动作参数")


def _list_iot_instances() -> list:
    """列出所有 IoT 平台实例（mqtt_terminal / home_assistant / xiaomi_iot）"""
    return [
        inst for inst in list_instances()
        if inst.adapter_type in IOT_ADAPTER_TYPES
    ]


async def _aggregate_capability(method_name: str, item_key: str) -> tuple[list, list[str]]:
    """聚合一类 IoT 设备查询能力（list_devices / list_scenes / ...）。

    只有能力已实现的适配器（如 mqtt_terminal 的设备注册表、
    xiaomi_iot 的米家设备列表）会贡献数据；未实现的适配器
    （如 home_assistant）自动跳过并计入 unsupported 列表。

    Returns:
        (聚合条目列表, 未支持该能力的 adapter_type 列表)
    """
    items: list = []
    unsupported: list[str] = []
    for inst in _list_iot_instances():
        if not inst.adapter:
            continue
        method = getattr(inst.adapter, method_name, None)
        if method is None or not callable(method):
            unsupported.append(inst.adapter_type)
            continue
        try:
            result = await method()
            if isinstance(result, list):
                # 标注来源实例，便于前端区分多适配器设备
                for item in result:
                    if isinstance(item, dict) and "instance_id" not in item:
                        item.setdefault("instance_id", inst.instance_id)
                        item.setdefault("adapter_type", inst.adapter_type)
                items.extend(result)
        except Exception as e:
            logger.warning(
                f"[SmartHome] {inst.adapter_type}.{method_name} 查询失败 "
                f"(instance={inst.instance_id}): {e}",
                exc_info=True,
            )
    return items, unsupported


@router.get("/devices")
async def list_devices():
    """返回智能家居设备列表（聚合各 IoT 适配器：mqtt_terminal 注册表 / 米家设备等）"""
    logger.info("[API] GET /smart-home/devices - Listing IoT devices")

    devices, unsupported = await _aggregate_capability("list_devices", "devices")
    logger.debug(
        f"[SmartHome] Aggregated {len(devices)} device(s), "
        f"unsupported adapters: {unsupported}"
    )

    return ok({"devices": devices, "total": len(devices), "unsupported_adapters": unsupported})


@router.get("/scenes")
async def list_scenes():
    """返回智能家居场景列表（当前注册的适配器均未提供场景能力时返回空）"""
    logger.info("[API] GET /smart-home/scenes - Listing scenes")
    scenes, unsupported = await _aggregate_capability("list_scenes", "scenes")
    return ok({"scenes": scenes, "total": len(scenes), "unsupported_adapters": unsupported})


@router.get("/rooms")
async def list_rooms():
    """返回智能家居房间列表（当前注册的适配器均未提供房间能力时返回空）"""
    logger.info("[API] GET /smart-home/rooms - Listing rooms")
    rooms, unsupported = await _aggregate_capability("list_rooms", "rooms")
    return ok({"rooms": rooms, "total": len(rooms), "unsupported_adapters": unsupported})


@router.get("/automations")
async def list_automations():
    """返回智能家居自动化规则列表（当前注册的适配器均未提供该能力时返回空）"""
    logger.info("[API] GET /smart-home/automations - Listing automations")
    automations, unsupported = await _aggregate_capability("list_automations", "automations")
    return ok({"automations": automations, "total": len(automations), "unsupported_adapters": unsupported})


@router.post("/devices/{device_id}/control")
async def control_device(device_id: str, req: DeviceControlRequest):
    """控制智能家居设备，通过平台实例向设备发送控制命令"""
    logger.info(
        f"[API] POST /smart-home/devices/{device_id}/control - "
        f"action={req.action}, params={req.params}"
    )

    if req.action not in ALLOWED_ACTIONS:
        raise ValidationError(
            f"Invalid action '{req.action}', allowed: {', '.join(ALLOWED_ACTIONS)}"
        )

    iot_instances = _list_iot_instances()
    if not iot_instances:
        raise LuomiNestError(
            "未找到已注册的 IoT 平台实例，请先在平台管理中配置并启动智能家居适配器",
            code="SMART_HOME_NO_IOT_INSTANCE",
            status_code=404,
        )

    command_payload = {
        "device_id": device_id,
        "action": req.action,
        "params": req.params,
    }

    success = False
    last_error = ""

    for inst in iot_instances:
        if not inst.adapter:
            continue

        try:
            response = PlatformResponse(
                content=json.dumps(command_payload, ensure_ascii=False),
                message_type="json",
                extra={"command": req.action, "device_id": device_id, "params": req.params},
            )
            success = await inst.adapter.send_message(response, target=device_id)

            if success:
                platform_logger.log(
                    inst.instance_id, "info", "device_command_sent",
                    f"已向设备 {device_id} 发送 {req.action} 命令",
                    adapter_type=inst.adapter_type,
                    details=command_payload,
                )
                logger.success(
                    f"[SmartHome] Command sent via instance {inst.instance_id} "
                    f"({inst.adapter_type}): device={device_id}, action={req.action}"
                )
                break
        except Exception as e:
            last_error = str(e)
            logger.warning(
                f"[SmartHome] Instance {inst.instance_id} ({inst.adapter_type}) "
                f"failed to send command: {e}"
            )
            platform_logger.log(
                inst.instance_id, "warning", "device_command_failed",
                f"向设备 {device_id} 发送命令失败: {e}",
                adapter_type=inst.adapter_type,
                details={"error": last_error, **command_payload},
            )

    if not success:
        raise LuomiNestError(
            f"命令发送失败: {last_error or '所有 IoT 实例均未能成功发送命令'}",
            code="SMART_HOME_COMMAND_FAILED",
            status_code=500,
        )

    return ok({"success": True, "message": "命令已发送"})
