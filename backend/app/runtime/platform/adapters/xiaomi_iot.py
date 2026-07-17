"""小米 IoT 适配器：通过米家 API 接收设备事件并将用户消息转发到米家设备。

工作流程：
1. 通过 Webhook 或轮询接收小米设备上报的事件
2. 将设备事件（状态变化、告警、语音助手对话）转换为 PlatformMessage
3. 主 Agent 处理后，通过小米 IoT API 发送控制命令或 TTS 回复
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import time
from typing import Any

import httpx
from loguru import logger

from app.runtime.platform.base import (
    BasePlatformAdapter,
    PlatformMessage,
    PlatformResponse,
)
from app.runtime.platform.infrastructure.retry import RetryConfig, async_retry


class LuomiNestXiaomiIoTAdapter(BasePlatformAdapter):
    """小米 IoT 适配器：对接米家 API，实现设备事件接收与控制指令下发。

    支持的事件类型：
    - 设备状态变化（如灯开关、温度变化）
    - 设备告警（如烟雾报警、门窗传感器触发）
    - 语音助手消息（小爱同学对话）

    签名认证：使用 HMAC-SHA256 对请求参数进行签名。
    """

    platform_name = "xiaomi_iot"

    # 设备缓存 TTL（秒）
    _DEVICE_CACHE_TTL: int = 600  # 10 分钟

    def __init__(self) -> None:
        super().__init__()
        self._http_client: httpx.AsyncClient | None = None
        self._polling_task: asyncio.Task | None = None
        self._app_key: str = ""
        self._app_secret: str = ""
        self._server_url: str = "https://api.io.mi.com"
        self._polling_interval: int = 60
        self._webhook_url: str = ""
        # 设备缓存: {device_id: {"data": ..., "ts": float}}
        self._device_cache: dict[str, dict[str, Any]] = {}
        self._device_list_cache: dict[str, Any] | None = None
        self._device_list_ts: float = 0.0

    # ------------------------------------------------------------------
    # 配置元数据
    # ------------------------------------------------------------------

    config_metadata: dict[str, dict[str, Any]] = {
        "app_key": {
            "type": "string",
            "required": True,
            "label": "App Key",
            "sensitive": True,
        },
        "app_secret": {
            "type": "string",
            "required": True,
            "label": "App Secret",
            "sensitive": True,
        },
        "server_url": {
            "type": "string",
            "required": False,
            "default": "https://api.io.mi.com",
            "label": "服务器URL",
        },
        "polling_interval": {
            "type": "number",
            "required": False,
            "default": 60,
            "label": "轮询间隔(秒)",
        },
        "webhook_url": {
            "type": "string",
            "required": False,
            "label": "Webhook URL",
        },
    }

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    def initialize(self, config: dict[str, Any]) -> None:
        """解析配置并初始化资源。"""
        super().initialize(config)
        self._app_key = config.get("app_key", "")
        self._app_secret = config.get("app_secret", "")
        self._server_url = config.get("server_url", "https://api.io.mi.com").rstrip("/")
        self._polling_interval = int(config.get("polling_interval", 60))
        self._webhook_url = config.get("webhook_url", "")

        if not self._app_key or not self._app_secret:
            raise ValueError("小米 IoT 适配器需要 app_key 和 app_secret")

    async def start(self) -> None:
        """启动适配器：创建 HTTP 客户端，启动轮询或注册 Webhook。"""
        self._http_client = httpx.AsyncClient(
            base_url=self._server_url,
            timeout=httpx.Timeout(30.0),
            headers={"Content-Type": "application/json"},
        )

        self._log(
            "info", "adapter_start",
            "小米 IoT 适配器已启动",
            details={
                "server_url": self._server_url,
                "polling_interval": self._polling_interval,
                "webhook_url": self._webhook_url or "(未配置)",
            },
        )

        # 如果配置了 Webhook，则通过 Webhook 接收事件；否则使用轮询
        if self._webhook_url:
            self._log("info", "webhook_mode", f"使用 Webhook 模式: {self._webhook_url}")
        else:
            self._polling_task = asyncio.create_task(self._polling_worker())
            self._log("info", "polling_mode", f"使用轮询模式，间隔 {self._polling_interval}s")

        self.update_status(self._status.__class__.RUNNING)

    async def stop(self) -> None:
        """停止适配器：取消轮询任务，关闭 HTTP 客户端。"""
        if self._polling_task and not self._polling_task.done():
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
            self._polling_task = None

        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

        self._device_cache.clear()
        self._device_list_cache = None
        self._device_list_ts = 0.0

        self._log("info", "adapter_stop", "小米 IoT 适配器已停止")
        await super().stop()

    # ------------------------------------------------------------------
    # 消息发送（设备控制）
    # ------------------------------------------------------------------

    async def send_message(self, response: PlatformResponse, target: str) -> bool:
        """向小米 IoT 设备发送响应。

        target 格式: "device:<device_id>" 或 "<device_id>"

        支持：
        - 文本回复：通过 TTS 设备播放
        - 设备控制命令：通过 response.extra 传递
        """
        device_id = self._parse_target(target)
        if not device_id:
            self._log("warning", "send_failed", f"无效的目标: {target}", details={"target": target})
            return False

        # 优先处理 extra 中的设备控制命令
        if response.extra and response.extra.get("device_command"):
            return await self._send_device_command(device_id, response)

        # 文本内容通过 TTS 播放
        if response.content:
            return await self._send_tts(device_id, response.content)

        self._log("warning", "send_empty", "响应内容为空，跳过发送", details={"target": target})
        return False

    async def _send_device_command(self, device_id: str, response: PlatformResponse) -> bool:
        """发送设备控制命令。"""
        command = response.extra.get("device_command", {}) if response.extra else {}
        params = {
            "device_id": device_id,
            "command": command,
        }
        if response.extra and response.extra.get("device_params"):
            params["params"] = response.extra["device_params"]

        try:
            result = await self._api_request("POST", "/app/device/control", params)
            self._log(
                "success", "device_command_sent",
                f"设备控制命令已发送 -> {device_id}",
                details={"device_id": device_id, "command": command},
            )
            return result.get("code", -1) == 0
        except Exception as e:
            self._log("error", "device_command_failed", f"设备控制命令发送失败: {e}", details={"error": str(e)})
            self.record_error(str(e))
            return False

    async def _send_tts(self, device_id: str, text: str) -> bool:
        """通过 TTS 设备播放文本。"""
        params = {
            "device_id": device_id,
            "text": text,
        }
        try:
            result = await self._api_request("POST", "/app/device/tts", params)
            self._log(
                "success", "tts_sent",
                f"TTS 已发送 -> {device_id}: {text[:50]}",
                details={"device_id": device_id, "text_length": len(text)},
            )
            return result.get("code", -1) == 0
        except Exception as e:
            self._log("error", "tts_failed", f"TTS 发送失败: {e}", details={"error": str(e)})
            self.record_error(str(e))
            return False

    # ------------------------------------------------------------------
    # 设备事件接收
    # ------------------------------------------------------------------

    async def handle_device_event(self, event: dict) -> None:
        """处理小米设备上报的事件。

        支持的事件类型：
        - device_status_change: 设备状态变化
        - device_alert: 设备告警
        - voice_assistant: 语音助手消息（小爱同学对话）

        Args:
            event: 小米设备上报的原始事件字典。
        """
        event_type = event.get("type", "")
        device_id = event.get("device_id", "")
        timestamp = event.get("timestamp", int(time.time()))

        self._log(
            "info", "device_event_received",
            f"收到设备事件 [{event_type}] 来自 {device_id}",
            details={"event_type": event_type, "device_id": device_id, "timestamp": timestamp},
        )

        platform_msg = self._convert_event_to_message(event, event_type, device_id)
        if platform_msg is None:
            return

        self._log(
            "info", "message_received",
            f"收到消息 [xiaomi_iot] 设备事件: {platform_msg.content[:50]}",
            details={
                "user_id": platform_msg.user_id,
                "device_id": device_id,
                "event_type": event_type,
            },
        )

        response = await self._emit_message(platform_msg)
        if response and response.content:
            target = f"device:{device_id}"
            await self.send_message(response, target)

    def _convert_event_to_message(
        self, event: dict, event_type: str, device_id: str
    ) -> PlatformMessage | None:
        """将设备事件转换为 PlatformMessage。"""
        if event_type == "device_status_change":
            return self._convert_status_change(event, device_id)
        elif event_type == "device_alert":
            return self._convert_alert(event, device_id)
        elif event_type == "voice_assistant":
            return self._convert_voice_assistant(event, device_id)
        else:
            self._log("warning", "unknown_event_type", f"未知事件类型: {event_type}")
            return None

    def _convert_status_change(self, event: dict, device_id: str) -> PlatformMessage:
        """转换设备状态变化事件。"""
        properties = event.get("properties", {})
        device_name = event.get("device_name", device_id)

        # 构建可读的状态描述
        status_parts: list[str] = []
        for key, value in properties.items():
            status_parts.append(f"{key}={value}")
        status_desc = ", ".join(status_parts) if status_parts else "状态已变化"

        content = f"[设备状态变化] {device_name}: {status_desc}"

        return PlatformMessage(
            platform=self.platform_name,
            user_id=device_id,
            content=content,
            session_id=device_id,
            message_id=event.get("message_id", f"{device_id}_{event.get('timestamp', '')}"),
            sender_name=device_name,
            raw=event,
        )

    def _convert_alert(self, event: dict, device_id: str) -> PlatformMessage:
        """转换设备告警事件。"""
        alert_type = event.get("alert_type", "unknown")
        alert_message = event.get("message", "")
        device_name = event.get("device_name", device_id)
        severity = event.get("severity", "info")

        content = f"[设备告警][{severity}] {device_name}: {alert_type} - {alert_message}"

        return PlatformMessage(
            platform=self.platform_name,
            user_id=device_id,
            content=content,
            session_id=device_id,
            message_id=event.get("message_id", f"alert_{device_id}_{event.get('timestamp', '')}"),
            sender_name=device_name,
            raw=event,
        )

    def _convert_voice_assistant(self, event: dict, device_id: str) -> PlatformMessage:
        """转换语音助手（小爱同学）对话事件。"""
        text = event.get("text", "")
        user_id = event.get("user_id", device_id)
        sender_name = event.get("user_name", "小爱用户")

        return PlatformMessage(
            platform=self.platform_name,
            user_id=user_id,
            content=text,
            session_id=user_id,
            message_id=event.get("message_id", f"voice_{device_id}_{event.get('timestamp', '')}"),
            sender_name=sender_name,
            raw=event,
        )

    # ------------------------------------------------------------------
    # 设备列表管理
    # ------------------------------------------------------------------

    async def list_devices(self) -> list[dict[str, Any]]:
        """获取绑定的设备列表（带缓存，TTL 10 分钟）。"""
        now = time.time()
        if self._device_list_cache is not None and (now - self._device_list_ts) < self._DEVICE_CACHE_TTL:
            return self._device_list_cache

        try:
            result = await self._api_request("GET", "/app/device/list")
            devices = result.get("data", {}).get("devices", [])
            self._device_list_cache = devices
            self._device_list_ts = now
            self._log("info", "device_list_fetched", f"获取到 {len(devices)} 个设备")
            return devices
        except Exception as e:
            self._log("error", "device_list_failed", f"获取设备列表失败: {e}", details={"error": str(e)})
            return []

    async def get_device_info(self, device_id: str) -> dict[str, Any] | None:
        """获取设备详情（带缓存，TTL 10 分钟）。"""
        now = time.time()
        cached = self._device_cache.get(device_id)
        if cached and (now - cached["ts"]) < self._DEVICE_CACHE_TTL:
            return cached["data"]

        try:
            result = await self._api_request("GET", "/app/device/info", params={"device_id": device_id})
            device_info = result.get("data", {})
            self._device_cache[device_id] = {"data": device_info, "ts": now}
            return device_info
        except Exception as e:
            self._log(
                "error", "device_info_failed",
                f"获取设备详情失败: {e}",
                details={"device_id": device_id, "error": str(e)},
            )
            return None

    # ------------------------------------------------------------------
    # 轮询
    # ------------------------------------------------------------------

    async def _polling_worker(self) -> None:
        """后台轮询任务：定期拉取设备状态变更事件。"""
        try:
            while True:
                await asyncio.sleep(self._polling_interval)
                try:
                    events = await self._fetch_pending_events()
                    for event in events:
                        await self.handle_device_event(event)
                except Exception as e:
                    self._log("error", "polling_failed", f"轮询失败: {e}", details={"error": str(e)})
        except asyncio.CancelledError:
            logger.debug("[xiaomi_iot] 轮询任务已取消")

    async def _fetch_pending_events(self) -> list[dict]:
        """从米家 API 拉取待处理的设备事件。"""
        try:
            result = await self._api_request("GET", "/app/event/pending")
            return result.get("data", {}).get("events", [])
        except Exception as e:
            self._log("warning", "fetch_events_failed", f"拉取事件失败: {e}", details={"error": str(e)})
            return []

    # ------------------------------------------------------------------
    # HTTP & 签名
    # ------------------------------------------------------------------

    def _sign_request(self, params: dict[str, Any], nonce: str, timestamp: str) -> str:
        """生成 HMAC-SHA256 签名。

        签名规则：将参数按 key 排序拼接为查询字符串，
        附加 nonce 和 timestamp，使用 app_secret 作为密钥进行 HMAC-SHA256 签名。
        """
        sorted_keys = sorted(params.keys())
        param_str = "&".join(f"{k}={params[k]}" for k in sorted_keys if params[k] is not None)
        sign_str = f"{param_str}&nonce={nonce}&timestamp={timestamp}"
        signature = hmac.new(
            self._app_secret.encode("utf-8"),
            sign_str.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return signature

    async def _api_request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """发送带签名的 API 请求。

        Args:
            method: HTTP 方法（GET / POST）。
            path: API 路径。
            params: 请求参数。

        Returns:
            API 响应字典。

        Raises:
            httpx.HTTPStatusError: HTTP 状态码异常。
            RuntimeError: 客户端未初始化。
        """
        if not self._http_client:
            raise RuntimeError("HTTP 客户端未初始化，请先调用 start()")

        if params is None:
            params = {}

        timestamp = str(int(time.time()))
        nonce = hashlib.md5(f"{time.time_ns()}".encode()).hexdigest()[:16]
        signature = self._sign_request(params, nonce, timestamp)

        headers = {
            "X-Xiaomi-AppKey": self._app_key,
            "X-Xiaomi-Timestamp": timestamp,
            "X-Xiaomi-Nonce": nonce,
            "X-Xiaomi-Signature": signature,
        }

        retry_config = RetryConfig(
            max_retries=3,
            base_delay=1.0,
            max_delay=10.0,
            jitter=0.5,
            retryable_exceptions=(httpx.TransportError, httpx.TimeoutException),
        )

        @async_retry(config=retry_config)
        async def _do_request() -> dict[str, Any]:
            assert self._http_client is not None
            if method.upper() == "GET":
                resp = await self._http_client.get(path, params=params, headers=headers)
            else:
                resp = await self._http_client.post(path, json=params, headers=headers)
            resp.raise_for_status()
            return resp.json()

        return await _do_request()

    # ------------------------------------------------------------------
    # 辅助
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_target(target: str) -> str:
        """解析 target 字符串，提取 device_id。

        支持格式: "device:<device_id>" 或纯 "<device_id>"。
        """
        if target.startswith("device:"):
            return target.split(":", 1)[1]
        return target
