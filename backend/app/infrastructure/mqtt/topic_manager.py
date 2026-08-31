"""LuomiNest MQTT Topic 规范管理。

统一 topic 前缀为 ``luominest``（项目品牌，与固件 app_mqtt.c 的
``luominest/p4/status`` 及 docker 健康检查 ``luominest/health`` 对齐）。

规范（docs/architecture/firmware.md 设计稿的落地版本）：

============================================  ========  =======================
Topic                                          方向      说明
============================================  ========  =======================
luominest/device/{device_id}/status            设备上报  设备状态（JSON）
luominest/device/{device_id}/command           后端下发  控制命令（JSON）
luominest/device/{device_id}/audio             设备上报  音频流分片
luominest/device/{device_id}/location          设备上报  位置信息
luominest/chat/{device_id}/message             双向      终端聊天文本
luominest/{device_id}/status                   设备上报  固件直连简写形式
                                                        （如 luominest/p4/status）
============================================  ========  =======================

兼容性：同时订阅旧前缀 ``luominestai`` 下的 device 通配，覆盖历史部署。
"""
from __future__ import annotations

# 统一 topic 前缀（项目品牌 LuomiNest）
TOPIC_PREFIX = "luominest"

# 旧版前缀（历史部署兼容，仅订阅不发布）
_LEGACY_TOPIC_PREFIX = "luominestai"


# ── 构造器 ──────────────────────────────────────────────────────────────────

def device_status_topic(device_id: str) -> str:
    return f"{TOPIC_PREFIX}/device/{device_id}/status"


def device_command_topic(device_id: str) -> str:
    return f"{TOPIC_PREFIX}/device/{device_id}/command"


def device_audio_topic(device_id: str) -> str:
    return f"{TOPIC_PREFIX}/device/{device_id}/audio"


def device_location_topic(device_id: str) -> str:
    return f"{TOPIC_PREFIX}/device/{device_id}/location"


def chat_message_topic(device_id: str) -> str:
    return f"{TOPIC_PREFIX}/chat/{device_id}/message"


def firmware_status_topic(device_id: str) -> str:
    """固件直连简写形式（luominest/{device_id}/status，如 luominest/p4/status）。"""
    return f"{TOPIC_PREFIX}/{device_id}/status"


# ── 订阅模式（通配） ────────────────────────────────────────────────────────

def inbound_subscription_patterns() -> list[str]:
    """返回后端需要订阅的全部入站 topic 通配模式。

    覆盖三类来源：
    1. 规范 device 段形式：luominest/device/{id}/status|audio|location
    2. 固件直连简写形式：luominest/{id}/status（ESP32-P4 等）
    3. 终端聊天文本：luominest/chat/{id}/message
    4. 旧前缀兼容：luominestai/device/{id}/status|audio|location
    """
    return [
        f"{TOPIC_PREFIX}/device/+/status",
        f"{TOPIC_PREFIX}/device/+/audio",
        f"{TOPIC_PREFIX}/device/+/location",
        # 固件直连简写形式（两段式，如 luominest/p4/status）
        f"{TOPIC_PREFIX}/+/status",
        # 终端聊天文本（路由到主 Agent）
        f"{TOPIC_PREFIX}/chat/+/message",
        # 旧前缀兼容（仅订阅）
        f"{_LEGACY_TOPIC_PREFIX}/device/+/status",
        f"{_LEGACY_TOPIC_PREFIX}/device/+/audio",
        f"{_LEGACY_TOPIC_PREFIX}/device/+/location",
    ]


# ── 解析 ────────────────────────────────────────────────────────────────────

def extract_device_id(topic: str) -> str:
    """从 topic 中解析 device_id。

    支持的形式：
    - luominest/device/{id}/status  → id
    - luominestai/device/{id}/audio → id
    - luominest/{id}/status         → id（固件直连简写）
    - luominest/chat/{id}/message   → id

    无法解析时返回 "unknown"。
    """
    parts = [p for p in topic.split("/") if p]
    for prefix in (TOPIC_PREFIX, _LEGACY_TOPIC_PREFIX):
        if parts and parts[0] != prefix:
            continue
        rest = parts[1:]
        if not rest:
            continue
        if rest[0] == "device" or rest[0] == "chat":
            # {prefix}/device|chat/{id}/...
            if len(rest) >= 2:
                return rest[1]
        else:
            # {prefix}/{id}/...（固件直连简写）
            return rest[0]
    return "unknown"


def classify_topic(topic: str) -> str:
    """判断 topic 的消息类别。

    返回值：status / audio / location / chat / command / unknown
    """
    if topic.endswith("/status"):
        return "status"
    if topic.endswith("/audio"):
        return "audio"
    if topic.endswith("/location"):
        return "location"
    if "/chat/" in topic and topic.endswith("/message"):
        return "chat"
    if topic.endswith("/command"):
        return "command"
    return "unknown"
