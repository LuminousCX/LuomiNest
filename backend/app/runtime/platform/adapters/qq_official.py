import asyncio
import time
from typing import Any
from loguru import logger

from app.runtime.platform.base import BasePlatformAdapter, PlatformMessage, PlatformResponse


class LuomiNestQQOfficialAdapter(BasePlatformAdapter):
    """QQ 官方机器人适配器：通过 QQ 开放平台 OpenAPI 收发消息。

    工作流程：
    1. 使用 appId + appSecret 获取 access_token
    2. Webhook 接收事件回调（由 platform endpoint 统一注册路由）
    3. 收到消息事件后解析为 PlatformMessage，路由到主 Agent
    4. 主 Agent 响应后调用 OpenAPI 发送消息

    配置项：
    - app_id: QQ 开放平台应用 ID
    - app_secret: 应用密钥
    - token: 机器人 token（可选，用于 webhook 签名校验）
    - enable_group: 启用群消息
    - enable_private: 启用 C2C 消息
    """

    platform_name = "qq_official"

    API_BASE = "https://api.sgroup.qq.com"

    def __init__(self) -> None:
        super().__init__()
        self._access_token: str = ""
        self._token_expires: float = 0
        self._token_lock = asyncio.Lock()

    def initialize(self, config: dict[str, Any]) -> None:
        super().initialize(config)
        self._app_id = config.get("app_id", "")
        self._app_secret = config.get("app_secret", "")
        self._token = config.get("token", "")
        self._enable_group = bool(config.get("enable_group", True))
        self._enable_private = bool(config.get("enable_private", True))

    async def start(self) -> None:
        if not self._app_id or not self._app_secret:
            logger.warning(f"[QQOfficial] Missing app_id/app_secret, API calls will fail")
            return
        token_ok = await self._refresh_access_token()
        if token_ok:
            logger.success(f"[QQOfficial] Adapter ready, access_token obtained")
        else:
            logger.warning(f"[QQOfficial] Failed to obtain access_token, will retry on demand")

    async def stop(self) -> None:
        self._access_token = ""
        logger.info(f"[QQOfficial] Adapter stopped")

    async def send_message(self, response: PlatformResponse, target: str) -> bool:
        target_type, target_id = self._parse_target(target)
        if not target_id:
            logger.warning(f"[QQOfficial] Invalid target: {target}")
            return False

        token = await self._ensure_access_token()
        if not token:
            return False

        import httpx

        if target_type == "group":
            url = f"{self.API_BASE}/v2/groups/{target_id}/messages"
        else:
            url = f"{self.API_BASE}/v2/users/{target_id}/messages"

        payload = {
            "content": response.content,
            "msg_type": 0,
            "msg_id": response.reply_to or "",
        }

        headers = {"Authorization": f"QQBot {token}", "Content-Type": "application/json"}

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code in (200, 201, 204):
                    logger.info(f"[QQOfficial] Sent message to {target_id}: {response.content[:50]}")
                    return True
                logger.error(f"[QQOfficial] Send failed: {resp.status_code} {resp.text[:200]}")
                return False
        except Exception as e:
            logger.error(f"[QQOfficial] Send exception: {e}")
            return False

    async def handle_webhook(self, data: dict) -> None:
        """处理 QQ 官方 webhook 事件（由 platform endpoint 调用）。"""
        event_type = data.get("event_type") or data.get("t", "")
        event_data = data.get("event") or data.get("d", {})

        if event_type in ("GROUP_AT_MESSAGE_CREATE", "GROUP_MESSAGE_CREATE"):
            if not self._enable_group:
                return
            await self._handle_group_message(event_data)
        elif event_type in ("C2C_MESSAGE_CREATE", "DIRECT_MESSAGE_CREATE"):
            if not self._enable_private:
                return
            await self._handle_private_message(event_data)

    async def _handle_group_message(self, data: dict) -> None:
        group_openid = data.get("group_openid", "")
        author = data.get("author", {})
        user_id = author.get("member_openid", "")
        content = data.get("content", "").strip()
        message_id = data.get("id", "")

        if not content:
            return

        if content.startswith("@"):
            at_end = content.find(" ")
            if at_end > 0:
                content = content[at_end + 1:].strip()

        platform_msg = PlatformMessage(
            platform=self.platform_name,
            user_id=user_id,
            content=content,
            session_id=group_openid,
            message_id=message_id,
            group_id=group_openid,
            sender_name=author.get("username", user_id),
            is_group=True,
            raw=data,
        )

        response = await self._emit_message(platform_msg)
        if response and response.content:
            response.reply_to = message_id
            await self.send_message(response, f"group:{group_openid}")

    async def _handle_private_message(self, data: dict) -> None:
        user_openid = data.get("author", {}).get("user_openid", "")
        content = data.get("content", "").strip()
        message_id = data.get("id", "")

        if not content:
            return

        platform_msg = PlatformMessage(
            platform=self.platform_name,
            user_id=user_openid,
            content=content,
            session_id=user_openid,
            message_id=message_id,
            sender_name=data.get("author", {}).get("username", user_openid),
            is_group=False,
            raw=data,
        )

        response = await self._emit_message(platform_msg)
        if response and response.content:
            response.reply_to = message_id
            await self.send_message(response, f"private:{user_openid}")

    async def _refresh_access_token(self) -> bool:
        import httpx

        url = f"{self.API_BASE}/app/getAppAccessToken"
        payload = {"appId": self._app_id, "clientSecret": self._app_secret}

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    self._access_token = data.get("access_token", "")
                    expires_in = int(data.get("expires_in", 7200))
                    self._token_expires = time.time() + expires_in - 300
                    logger.info(f"[QQOfficial] Access token refreshed, expires in {expires_in}s")
                    return True
                logger.error(f"[QQOfficial] Token refresh failed: {resp.status_code} {resp.text[:200]}")
                return False
        except Exception as e:
            logger.error(f"[QQOfficial] Token refresh exception: {e}")
            return False

    async def _ensure_access_token(self) -> str:
        if self._access_token and time.time() < self._token_expires:
            return self._access_token
        async with self._token_lock:
            if self._access_token and time.time() < self._token_expires:
                return self._access_token
            await self._refresh_access_token()
            return self._access_token

    @staticmethod
    def _parse_target(target: str) -> tuple[str, str]:
        if ":" in target:
            t_type, t_id = target.split(":", 1)
            return t_type, t_id
        return "private", target
