import json
from typing import Any
from loguru import logger

from app.runtime.platform.base import BasePlatformAdapter, PlatformMessage, PlatformResponse
from app.runtime.platform.registry import register_adapter_type
from app.infrastructure.mqtt import mqtt_client


class MQTTTerminalAdapter(BasePlatformAdapter):
    platform_name = "mqtt_terminal"

    TOPIC_STATUS = "luominestai/device/{device_id}/status"
    TOPIC_COMMAND = "luominestai/device/{device_id}/command"
    TOPIC_AUDIO = "luominestai/device/{device_id}/audio"
    TOPIC_LOCATION = "luominestai/device/{device_id}/location"

    def __init__(self) -> None:
        super().__init__()
        self._subscribed_devices: set[str] = set()

    async def start(self) -> None:
        if mqtt_client:
            await mqtt_client.subscribe("luominestai/device/+/status")
            await mqtt_client.subscribe("luominestai/device/+/audio")
            await mqtt_client.subscribe("luominestai/device/+/location")
        logger.info(f"[{self.platform_name}] MQTT Terminal adapter started")

    async def send_message(self, response: PlatformResponse, target: str) -> bool:
        if not mqtt_client:
            return False
        topic = self.TOPIC_COMMAND.format(device_id=target)
        payload = {
            "type": response.message_type,
            "content": response.content,
            **(response.extra or {}),
        }
        await mqtt_client.publish(topic, json.dumps(payload), qos=1)
        return True

    async def handle_event(self, event: dict[str, Any]) -> PlatformMessage | None:
        topic = event.get("topic", "")
        payload = event.get("payload", {})

        if "/status" in topic:
            device_id = self._extract_device_id(topic)
            return PlatformMessage(
                platform=self.platform_name,
                user_id=device_id,
                content=json.dumps(payload),
                raw=payload,
            )
        elif "/audio" in topic:
            device_id = self._extract_device_id(topic)
            return PlatformMessage(
                platform=self.platform_name,
                user_id=device_id,
                content=f"[AUDIO] {len(payload.get('data', b''))} bytes",
                raw=payload,
            )
        return None

    def _extract_device_id(self, topic: str) -> str:
        parts = topic.split("/")
        for i, part in enumerate(parts):
            if part == "device" and i + 1 < len(parts):
                return parts[i + 1]
        return "unknown"


class WebSocketPlatformAdapter(BasePlatformAdapter):
    platform_name = "websocket"

    def __init__(self) -> None:
        super().__init__()
        self._connections: dict[str, Any] = {}

    async def send_message(self, response: PlatformResponse, target: str) -> bool:
        conn = self._connections.get(target)
        if conn and hasattr(conn, 'send_json'):
            await conn.send_json({"type": "message", "data": {"content": response.content}})
            return True
        return False

    async def handle_event(self, event: dict[str, Any]) -> PlatformMessage | None:
        ws = event.get("ws")
        data = event.get("data", {})
        conn_id = event.get("conn_id", "")
        if ws:
            self._connections[conn_id] = ws
        return PlatformMessage(
            platform=self.platform_name,
            user_id=conn_id,
            content=data.get("content", ""),
            raw=data,
        ) if data.get("content") else None


class RESTPlatformAdapter(BasePlatformAdapter):
    platform_name = "rest_api"

    async def send_message(self, response: PlatformResponse, target: str) -> bool:
        return True

    async def handle_event(self, event: dict[str, Any]) -> PlatformMessage | None:
        return PlatformMessage(
            platform=self.platform_name,
            user_id=event.get("user_id", "anonymous"),
            content=event.get("content", ""),
            raw=event,
        )


class TelegramAdapter(BasePlatformAdapter):
    platform_name = "telegram"

    async def send_message(self, response: PlatformResponse, target: str) -> bool:
        return False

    async def handle_event(self, event: dict[str, Any]) -> PlatformMessage | None:
        return None


class DiscordAdapter(BasePlatformAdapter):
    platform_name = "discord"

    async def send_message(self, response: PlatformResponse, target: str) -> bool:
        return False

    async def handle_event(self, event: dict[str, Any]) -> PlatformMessage | None:
        return None


class HomeAssistantAdapter(BasePlatformAdapter):
    platform_name = "home_assistant"

    async def send_message(self, response: PlatformResponse, target: str) -> bool:
        return False

    async def handle_event(self, event: dict[str, Any]) -> PlatformMessage | None:
        return None


class XiaomiIoTAdapter(BasePlatformAdapter):
    platform_name = "xiaomi_iot"

    async def send_message(self, response: PlatformResponse, target: str) -> bool:
        return False

    async def handle_event(self, event: dict[str, Any]) -> PlatformMessage | None:
        return None


def _register_all_adapter_types():
    register_adapter_type(
        name="mqtt_terminal",
        display_name="MQTT 终端",
        description="通过 MQTT 协议连接 IoT 设备终端，支持状态上报、音频流和位置信息",
        adapter_cls=MQTTTerminalAdapter,
        config_template={
            "broker_host": "localhost",
            "broker_port": 1883,
            "username": "",
            "password": "",
        },
        config_metadata={
            "broker_host": {"label": "Broker 地址", "type": "text", "required": True},
            "broker_port": {"label": "Broker 端口", "type": "number", "required": True},
            "username": {"label": "用户名", "type": "text", "required": False},
            "password": {"label": "密码", "type": "password", "required": False},
        },
        icon="Radio",
        category="iot",
        support_proactive=True,
    )
    register_adapter_type(
        name="websocket",
        display_name="WebSocket 连接",
        description="通过 WebSocket 协议实现双向实时通信，适用于自定义客户端接入",
        adapter_cls=WebSocketPlatformAdapter,
        config_template={
            "endpoint": "/ws/platform",
        },
        config_metadata={
            "endpoint": {"label": "WebSocket 端点", "type": "text", "required": True},
        },
        icon="Cable",
        category="general",
        support_streaming=True,
        support_proactive=True,
    )
    register_adapter_type(
        name="rest_api",
        display_name="REST API",
        description="通过 HTTP REST API 接入第三方平台，支持 Webhook 回调",
        adapter_cls=RESTPlatformAdapter,
        config_template={
            "webhook_url": "",
            "api_key": "",
        },
        config_metadata={
            "webhook_url": {"label": "Webhook URL", "type": "text", "required": False},
            "api_key": {"label": "API Key", "type": "password", "required": False},
        },
        icon="Link",
        category="general",
        support_proactive=True,
    )

    from app.runtime.platform.adapters.qq_onebot import LuomiNestQQOneBotAdapter
    register_adapter_type(
        name="qq_onebot",
        display_name="QQ OneBot v11",
        description="通过 OneBot v11 协议接入 QQ 机器人，支持反向 WebSocket 连接（对接 NapCat/Lagrange/go-cqhttp），支持群聊和私聊、图片识别",
        adapter_cls=LuomiNestQQOneBotAdapter,
        config_template={
            "ws_host": "0.0.0.0",
            "ws_port": 8080,
            "access_token": "",
            "enable_group": True,
            "enable_private": True,
        },
        config_metadata={
            "ws_host": {"label": "监听地址", "type": "text", "required": True},
            "ws_port": {"label": "监听端口", "type": "number", "required": True},
            "access_token": {"label": "Access Token", "type": "password", "required": False},
            "enable_group": {"label": "启用群消息", "type": "switch", "required": False},
            "enable_private": {"label": "启用私聊", "type": "switch", "required": False},
        },
        icon="MessageCircle",
        category="social",
        support_streaming=False,
        support_proactive=True,
    )

    from app.runtime.platform.adapters.qq_official import LuomiNestQQOfficialAdapter
    register_adapter_type(
        name="qq_official",
        display_name="QQ 官方机器人",
        description="通过 QQ 开放平台 OpenAPI 接入 QQ 官方机器人，支持群消息和 C2C 消息，需要公网 Webhook",
        adapter_cls=LuomiNestQQOfficialAdapter,
        config_template={
            "app_id": "",
            "app_secret": "",
            "token": "",
            "enable_group": True,
            "enable_private": True,
        },
        config_metadata={
            "app_id": {"label": "App ID", "type": "text", "required": True},
            "app_secret": {"label": "App Secret", "type": "password", "required": True},
            "token": {"label": "Token（Webhook校验）", "type": "password", "required": False},
            "enable_group": {"label": "启用群消息", "type": "switch", "required": False},
            "enable_private": {"label": "启用 C2C 消息", "type": "switch", "required": False},
        },
        icon="MessageCircle",
        category="social",
        support_streaming=False,
        support_proactive=True,
    )

    from app.runtime.platform.adapters.wechat_work import LuomiNestWeComAdapter
    register_adapter_type(
        name="wechat_work",
        display_name="企业微信",
        description="通过企业微信 API 接入，支持用户消息和群聊消息，支持图片识别，消息加解密",
        adapter_cls=LuomiNestWeComAdapter,
        config_template={
            "corp_id": "",
            "agent_id": "",
            "secret": "",
            "token": "",
            "encoding_aes_key": "",
            "enable_user": True,
            "enable_group": False,
        },
        config_metadata={
            "corp_id": {"label": "企业 ID", "type": "text", "required": True},
            "agent_id": {"label": "Agent ID", "type": "text", "required": True},
            "secret": {"label": "应用 Secret", "type": "password", "required": True},
            "token": {"label": "回调 Token", "type": "password", "required": True},
            "encoding_aes_key": {"label": "EncodingAESKey", "type": "text", "required": True},
            "enable_user": {"label": "启用用户消息", "type": "switch", "required": False},
            "enable_group": {"label": "启用群聊消息", "type": "switch", "required": False},
        },
        icon="Briefcase",
        category="social",
        support_streaming=False,
        support_proactive=True,
    )

    from app.runtime.platform.adapters.wechat_mp import LuomiNestWeChatMPAdapter
    register_adapter_type(
        name="wechat_mp",
        display_name="微信公众号",
        description="通过微信公众号 API 接入，支持文本和图片消息，通过客服消息异步回复，消息加解密",
        adapter_cls=LuomiNestWeChatMPAdapter,
        config_template={
            "app_id": "",
            "app_secret": "",
            "token": "",
            "encoding_aes_key": "",
            "enable_text": True,
            "enable_image": True,
        },
        config_metadata={
            "app_id": {"label": "AppID", "type": "text", "required": True},
            "app_secret": {"label": "AppSecret", "type": "password", "required": True},
            "token": {"label": "服务器 Token", "type": "password", "required": True},
            "encoding_aes_key": {"label": "EncodingAESKey", "type": "text", "required": True},
            "enable_text": {"label": "启用文本消息", "type": "switch", "required": False},
            "enable_image": {"label": "启用图片消息", "type": "switch", "required": False},
        },
        icon="Users",
        category="social",
        support_streaming=False,
        support_proactive=True,
    )

    from app.runtime.platform.adapters.minecraft import LuomiNestMinecraftAdapter
    register_adapter_type(
        name="minecraft",
        display_name="Minecraft",
        description="通过 RCON 协议连接 Minecraft 服务器，支持发送游戏内消息、执行命令、接收玩家聊天事件和游戏截图识别（参考 mindcraft 视觉理解方法）",
        adapter_cls=LuomiNestMinecraftAdapter,
        config_template={
            "rcon_host": "127.0.0.1",
            "rcon_port": 25575,
            "rcon_password": "",
            "ws_enabled": False,
            "ws_host": "0.0.0.0",
            "ws_port": 8081,
            "bot_name": "LuomiNest",
            "message_format": "tellraw",
            "screenshot_enabled": True,
        },
        config_metadata={
            "rcon_host": {"label": "RCON 地址", "type": "text", "required": True},
            "rcon_port": {"label": "RCON 端口", "type": "number", "required": True},
            "rcon_password": {"label": "RCON 密码", "type": "password", "required": True},
            "ws_enabled": {"label": "启用聊天事件 WS", "type": "switch", "required": False},
            "ws_host": {"label": "WS 监听地址", "type": "text", "required": False},
            "ws_port": {"label": "WS 监听端口", "type": "number", "required": False},
            "bot_name": {"label": "机器人名称", "type": "text", "required": False},
            "message_format": {"label": "消息格式", "type": "select", "options": ["tellraw", "tell", "say"], "required": False},
            "screenshot_enabled": {"label": "启用截图识别", "type": "switch", "required": False},
        },
        icon="Gamepad2",
        category="game",
        support_streaming=False,
        support_proactive=True,
    )

    from app.runtime.platform.adapters.game_websocket import LuomiNestGameWebSocketAdapter
    register_adapter_type(
        name="game_websocket",
        display_name="游戏 WebSocket 网关",
        description="通用 WebSocket 游戏网关，支持任意游戏客户端通过 WebSocket 接入，自定义 JSON 协议，支持鉴权",
        adapter_cls=LuomiNestGameWebSocketAdapter,
        config_template={
            "ws_host": "0.0.0.0",
            "ws_port": 8082,
            "auth_token": "",
            "max_clients": 50,
        },
        config_metadata={
            "ws_host": {"label": "监听地址", "type": "text", "required": True},
            "ws_port": {"label": "监听端口", "type": "number", "required": True},
            "auth_token": {"label": "鉴权 Token", "type": "password", "required": False},
            "max_clients": {"label": "最大客户端数", "type": "number", "required": False},
        },
        icon="Gamepad2",
        category="game",
        support_streaming=True,
        support_proactive=True,
    )

    register_adapter_type(
        name="telegram",
        display_name="Telegram",
        description="通过 Telegram Bot API 接入 Telegram 平台，支持私聊和群组消息（占位符，待实现）",
        adapter_cls=TelegramAdapter,
        config_template={
            "bot_token": "",
            "command_register": True,
        },
        config_metadata={
            "bot_token": {"label": "Bot Token", "type": "password", "required": True},
            "command_register": {"label": "自动注册命令", "type": "switch", "required": False},
        },
        icon="Send",
        category="social",
        support_streaming=True,
        support_proactive=True,
    )
    register_adapter_type(
        name="discord",
        display_name="Discord",
        description="通过 Discord Bot 接入 Discord 服务器，支持频道消息和私聊（占位符，待实现）",
        adapter_cls=DiscordAdapter,
        config_template={
            "bot_token": "",
            "guild_id": "",
        },
        config_metadata={
            "bot_token": {"label": "Bot Token", "type": "password", "required": True},
            "guild_id": {"label": "服务器 ID", "type": "text", "required": False},
        },
        icon="Gamepad2",
        category="social",
        support_streaming=False,
        support_proactive=True,
    )
    register_adapter_type(
        name="home_assistant",
        display_name="HomeAssistant",
        description="接入 HomeAssistant 智能家居平台，控制和管理智能设备（占位符，待实现）",
        adapter_cls=HomeAssistantAdapter,
        config_template={
            "ha_url": "http://homeassistant.local:8123",
            "ha_token": "",
        },
        config_metadata={
            "ha_url": {"label": "HA 地址", "type": "text", "required": True},
            "ha_token": {"label": "长期访问令牌", "type": "password", "required": True},
        },
        icon="Home",
        category="iot",
        support_proactive=True,
    )
    register_adapter_type(
        name="xiaomi_iot",
        display_name="小米 IoT",
        description="接入小米 IoT 平台，控制米家智能设备（占位符，待实现）",
        adapter_cls=XiaomiIoTAdapter,
        config_template={
            "mi_user": "",
            "mi_pass": "",
        },
        config_metadata={
            "mi_user": {"label": "小米账号", "type": "text", "required": True},
            "mi_pass": {"label": "小米密码", "type": "password", "required": True},
        },
        icon="Smartphone",
        category="iot",
        support_proactive=True,
    )


_register_all_adapter_types()
