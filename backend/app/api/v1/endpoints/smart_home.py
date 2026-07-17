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


@router.get("/devices")
async def list_devices():
    """返回智能家居设备列表（适配器尚未实现，暂返回空列表）"""
    logger.info("[API] GET /smart-home/devices - Listing IoT devices")

    iot_instances = _list_iot_instances()
    logger.debug(
        f"[SmartHome] Found {len(iot_instances)} IoT platform instance(s): "
        f"{[inst.instance_id for inst in iot_instances]}"
    )

    return ok({"devices": [], "total": 0})


@router.get("/scenes")
async def list_scenes():
    """返回智能家居场景列表（适配器尚未实现，暂返回空列表）"""
    logger.info("[API] GET /smart-home/scenes - Listing scenes")
    return ok({"scenes": [], "total": 0})


@router.get("/rooms")
async def list_rooms():
    """返回智能家居房间列表（适配器尚未实现，暂返回空列表）"""
    logger.info("[API] GET /smart-home/rooms - Listing rooms")
    return ok({"rooms": [], "total": 0})


@router.get("/automations")
async def list_automations():
    """返回智能家居自动化规则列表（适配器尚未实现，暂返回空列表）"""
    logger.info("[API] GET /smart-home/automations - Listing automations")
    return ok({"automations": [], "total": 0})


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
