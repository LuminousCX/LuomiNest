"""平台适配器包 - 导入所有适配器并注册。"""

from app.runtime.platform.adapters.discord import DEFAULT_INTENTS, DiscordAdapter
from app.runtime.platform.adapters.game_websocket import LuomiNestGameWebSocketAdapter
from app.runtime.platform.adapters.home_assistant import HomeAssistantAdapter
from app.runtime.platform.adapters.minecraft import LuomiNestMinecraftAdapter
from app.runtime.platform.adapters.mqtt_terminal import MQTTTerminalAdapter
from app.runtime.platform.adapters.qq_official import LuomiNestQQOfficialAdapter

# 已有的独立文件适配器
from app.runtime.platform.adapters.qq_onebot import LuomiNestQQOneBotAdapter
from app.runtime.platform.adapters.rest_api import RESTPlatformAdapter
from app.runtime.platform.adapters.telegram import TelegramAdapter
from app.runtime.platform.adapters.websocket import WebSocketAdapter
from app.runtime.platform.adapters.wechat_mp import LuomiNestWeChatMPAdapter
from app.runtime.platform.adapters.wechat_personal import LuomiNestWeChatPersonalAdapter
from app.runtime.platform.adapters.wechat_work import LuomiNestWeComAdapter
from app.runtime.platform.adapters.xiaomi_iot import LuomiNestXiaomiIoTAdapter as XiaomiIoTAdapter
from app.runtime.platform.registry import register_adapter_type


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
        adapter_cls=WebSocketAdapter,
        # 模板键以 WebSocketAdapter.initialize 实际读取的键为准（P1-5 防漂移）
        config_template={
            "ws_url": "",
            "access_token": "",
            "heartbeat_interval": 30,
            "reconnect_delay": 5,
        },
        config_metadata={
            "ws_url": {"label": "WebSocket 服务地址 (ws://...)", "type": "text", "required": True},
            "access_token": {"label": "访问 Token (对端要求鉴权时填写)", "type": "password", "required": False},
            "heartbeat_interval": {"label": "心跳间隔 (秒)", "type": "number", "required": False},
            "reconnect_delay": {"label": "重连间隔 (秒)", "type": "number", "required": False},
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
        # 模板键以 RESTPlatformAdapter.initialize 实际读取的键为准（P1-5 防漂移）
        config_template={
            "callback_url": "",
            "api_key": "",
            "max_queue_size": 100,
        },
        config_metadata={
            "callback_url": {"label": "回调通知 URL (选填，回复产生后 POST 推送)", "type": "text", "required": False},
            "api_key": {"label": "API Key (入站鉴权)", "type": "password", "required": False},
            "max_queue_size": {"label": "离线回复队列上限", "type": "number", "required": False},
        },
        icon="Link",
        category="general",
        support_proactive=True,
    )
    register_adapter_type(
        name="qq_onebot",
        display_name="QQ OneBot v11",
        description="通过 OneBot v11 协议接入 QQ 机器人，支持反向 WebSocket 连接（对接 NapCat/Lagrange/go-cqhttp），支持群聊和私聊、图片识别、拟人防风控延迟与输入态上报",
        adapter_cls=LuomiNestQQOneBotAdapter,
        config_template={
            "ws_host": "0.0.0.0",
            "ws_port": 8080,
            "access_token": "",
            "enable_group": True,
            "enable_private": True,
            "anti_ban_enabled": True,
            "typing_delay_enabled": True,
            "send_input_status": True,
            "rate_limit_per_minute": 25,
        },
        config_metadata={
            "ws_host": {"label": "监听地址", "type": "text", "required": True},
            "ws_port": {"label": "监听端口", "type": "number", "required": True},
            "access_token": {"label": "Access Token", "type": "password", "required": False},
            "enable_group": {"label": "启用群消息", "type": "switch", "required": False},
            "enable_private": {"label": "启用私聊", "type": "switch", "required": False},
            "anti_ban_enabled": {"label": "启用防风控保护", "type": "switch", "required": False},
            "typing_delay_enabled": {"label": "启用拟人打字延迟", "type": "switch", "required": False},
            "send_input_status": {"label": "输入状态上报", "type": "switch", "required": False},
            "rate_limit_per_minute": {"label": "每分钟发送上限", "type": "number", "required": False},
        },
        icon="MessageCircle",
        category="social",
        support_streaming=False,
        support_proactive=True,
    )
    register_adapter_type(
        name="qq_official",
        display_name="QQ 官方机器人",
        description="通过 QQ 开放平台 OpenAPI 接入 QQ 官方机器人，支持群消息和 C2C 消息，需要公网 Webhook（推送经 Ed25519 验签，密钥为 AppSecret）",
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
            "app_secret": {"label": "App Secret（同时用于 Webhook 验签）", "type": "password", "required": True},
            "token": {"label": "Token（QQ 已弃用，不参与验签）", "type": "password", "required": False},
            "enable_group": {"label": "启用群消息", "type": "switch", "required": False},
            "enable_private": {"label": "启用 C2C 消息", "type": "switch", "required": False},
        },
        icon="MessageCircle",
        category="social",
        support_streaming=False,
        support_proactive=True,
    )
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
    register_adapter_type(
        name="wechat_personal",
        display_name="个人微信",
        description="通过 Gewechat / 微信扫码接入个人微信号，支持二维码扫码登录、消息回调、图片多模态与防封控拟人打字延迟",
        adapter_cls=LuomiNestWeChatPersonalAdapter,
        config_template={
            "api_url": "http://127.0.0.1:2531/v2/api",
            "token": "",
            "app_id": "",
            "callback_url": "",
            "webhook_token": "",
            "self_wxid": "",
            "anti_ban_enabled": True,
            "typing_delay_enabled": True,
            "rate_limit_per_minute": 20,
            "mock_mode": False,
        },
        config_metadata={
            "api_url": {"label": "Gewechat 接口地址", "type": "text", "required": True},
            "token": {"label": "访问 Token", "type": "password", "required": False},
            "app_id": {"label": "设备/实例 AppID (选填)", "type": "text", "required": False},
            "callback_url": {"label": "回调 URL (选填)", "type": "text", "required": False},
            "webhook_token": {
                "label": "Webhook 回调密钥 (必填，推送体需携带，未配置回调全拒绝)",
                "type": "password",
                "required": True,
            },
            "self_wxid": {"label": "机器人自身 wxid (选填，登录后自动学习)", "type": "text", "required": False},
            "anti_ban_enabled": {"label": "启用防封控保护", "type": "switch", "required": False},
            "typing_delay_enabled": {"label": "启用拟人打字延迟", "type": "switch", "required": False},
            "rate_limit_per_minute": {"label": "每分钟发送上限", "type": "number", "required": False},
            "mock_mode": {"label": "本地演示/模拟模式", "type": "switch", "required": False},
        },
        icon="MessageSquare",
        category="social",
        support_streaming=False,
        support_proactive=True,
    )
    register_adapter_type(
        name="minecraft",
        display_name="Minecraft",
        description="通过 RCON 协议连接 Minecraft 服务器，支持发送游戏内消息、执行命令、接收玩家聊天事件和游戏截图识别（参考 mindcraft 视觉理解方法）",
        adapter_cls=LuomiNestMinecraftAdapter,
        config_template={
            "game_port": 56587,
            "game_host": "127.0.0.1",
            "auto_spawn_bot": True,
            "bot_name": "",
            "ws_enabled": True,
            "ws_host": "127.0.0.1",
            "ws_port": 8081,
            "ws_token": "",
            "rcon_host": "127.0.0.1",
            "rcon_port": 25575,
            "rcon_password": "",
            "message_format": "tellraw",
            "screenshot_enabled": True,
        },
        config_metadata={
            "game_port": {"label": "游戏局域网端口 (如 56587)", "type": "number", "required": False},
            "game_host": {"label": "游戏服务器地址", "type": "text", "required": False},
            "auto_spawn_bot": {"label": "自动派遣实体伴侣进服 (Bot)", "type": "switch", "required": False},
            "bot_name": {"label": "伴侣/机器人名称 (留空自动继承主Agent)", "type": "text", "required": False},
            "ws_enabled": {"label": "启用模组 WebSocket 通道", "type": "switch", "required": False},
            "ws_host": {"label": "WS 监听地址", "type": "text", "required": False},
            "ws_port": {"label": "WS 监听端口", "type": "number", "required": False},
            "ws_token": {"label": "WS 网关鉴权 Token (选填，未配置时仅本机模组可接入)", "type": "password", "required": False},
            "rcon_host": {"label": "RCON 地址 (选填)", "type": "text", "required": False},
            "rcon_port": {"label": "RCON 端口 (选填)", "type": "number", "required": False},
            "rcon_password": {"label": "RCON 密码 (选填)", "type": "password", "required": False},
            "message_format": {"label": "消息格式", "type": "select", "options": ["tellraw", "tell", "say"], "required": False},
            "screenshot_enabled": {"label": "启用截图/画面感知", "type": "switch", "required": False},
        },
        icon="Gamepad2",
        category="game",
        support_streaming=False,
        support_proactive=True,
    )
    register_adapter_type(
        name="game_websocket",
        display_name="游戏 WebSocket 网关",
        description="通用 WebSocket 游戏网关，支持任意游戏客户端通过 WebSocket 接入，自定义 JSON 协议，支持鉴权",
        adapter_cls=LuomiNestGameWebSocketAdapter,
        config_template={
            "ws_host": "127.0.0.1",
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
        description="通过 Telegram Bot API 接入 Telegram 平台，支持私聊和群组消息",
        adapter_cls=TelegramAdapter,
        # 模板键以 TelegramAdapter.initialize 实际读取的键为准（P1-5 防漂移）
        config_template={
            "bot_token": "",
            "allowed_users": "",
            "polling_interval": 1,
            "use_webhook": False,
            "webhook_url": "",
        },
        config_metadata={
            "bot_token": {"label": "Bot Token", "type": "password", "required": True},
            "allowed_users": {"label": "允许的用户 (逗号分隔用户名/ID，留空不限制)", "type": "text", "required": False},
            "polling_interval": {"label": "轮询间隔 (秒，最小 1)", "type": "number", "required": False},
            "use_webhook": {"label": "使用 Webhook 模式 (关闭则长轮询)", "type": "switch", "required": False},
            "webhook_url": {"label": "Webhook URL (Webhook 模式必填)", "type": "text", "required": False},
        },
        icon="Send",
        category="social",
        support_streaming=True,
        support_proactive=True,
    )
    register_adapter_type(
        name="discord",
        display_name="Discord",
        description="通过 Discord Bot 接入 Discord 服务器，支持频道消息和私聊",
        adapter_cls=DiscordAdapter,
        # 模板键以 DiscordAdapter.initialize 实际读取的键为准（P1-5 防漂移：
        # 原 guild_id 实现从不读取，改为 allowed_guilds 白名单才真正生效）
        config_template={
            "bot_token": "",
            "allowed_guilds": "",
            "prefix": "",
            "intents": DEFAULT_INTENTS,
        },
        config_metadata={
            "bot_token": {"label": "Bot Token", "type": "password", "required": True},
            "allowed_guilds": {"label": "允许的服务器 ID (逗号分隔，留空不限制)", "type": "text", "required": False},
            "prefix": {"label": "消息前缀 (选填，仅响应带前缀消息)", "type": "text", "required": False},
            "intents": {"label": "Gateway Intents 位掩码 (留空用默认)", "type": "number", "required": False},
        },
        icon="Gamepad2",
        category="social",
        support_streaming=False,
        support_proactive=True,
    )
    register_adapter_type(
        name="home_assistant",
        display_name="HomeAssistant",
        description="接入 HomeAssistant 智能家居平台，控制和管理智能设备",
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
        description="接入小米 IoT 平台，控制米家智能设备",
        adapter_cls=XiaomiIoTAdapter,
        # 模板键以 XiaomiIoTAdapter.initialize 实际读取的键为准（P1-5 防漂移：
        # 原 mi_user/mi_pass 实现从不读取，缺 app_key/app_secret 建实例必失败）
        config_template={
            "app_key": "",
            "app_secret": "",
            "server_url": "https://api.io.mi.com",
            "polling_interval": 60,
            "webhook_url": "",
        },
        config_metadata={
            "app_key": {"label": "App Key (开放平台应用标识)", "type": "text", "required": True},
            "app_secret": {"label": "App Secret", "type": "password", "required": True},
            "server_url": {"label": "服务器 URL", "type": "text", "required": False},
            "polling_interval": {"label": "轮询间隔 (秒)", "type": "number", "required": False},
            "webhook_url": {"label": "Webhook URL (选填，配置后走事件推送)", "type": "text", "required": False},
        },
        icon="Smartphone",
        category="iot",
        support_proactive=True,
    )


_register_all_adapter_types()
