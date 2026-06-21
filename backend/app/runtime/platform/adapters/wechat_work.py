import asyncio
import time
from typing import Any
from loguru import logger

from app.runtime.platform.base import BasePlatformAdapter, PlatformMessage, PlatformResponse
from app.runtime.platform.adapters.wechat_crypto import LuomiNestWeChatCrypto


class LuomiNestWeComAdapter(BasePlatformAdapter):
    """企业微信适配器：通过企业微信 API 收发消息。

    工作流程：
    1. 使用 corp_id + secret 获取 access_token
    2. Webhook 接收消息回调（XML 格式，可能加密）
    3. 解析消息后路由到主 Agent
    4. 主 Agent 响应后调用 API 发送消息

    配置项：
    - corp_id: 企业 ID
    - agent_id: 应用 agent_id
    - secret: 应用 secret
    - token: 回调配置的 Token
    - encoding_aes_key: 回调配置的 EncodingAESKey
    - enable_user: 启用用户消息
    - enable_group: 启用群聊消息
    """

    platform_name = "wechat_work"

    API_BASE = "https://qyapi.weixin.qq.com/cgi-bin"

    def __init__(self) -> None:
        super().__init__()
        self._access_token: str = ""
        self._token_expires: float = 0
        self._token_lock = asyncio.Lock()
        self._crypto: LuomiNestWeChatCrypto | None = None

    def initialize(self, config: dict[str, Any]) -> None:
        super().initialize(config)
        self._corp_id = config.get("corp_id", "")
        self._agent_id = config.get("agent_id", "")
        self._secret = config.get("secret", "")
        self._token = config.get("token", "")
        self._encoding_aes_key = config.get("encoding_aes_key", "")
        self._enable_user = bool(config.get("enable_user", True))
        self._enable_group = bool(config.get("enable_group", False))

        if self._token and self._encoding_aes_key and self._corp_id:
            if LuomiNestWeChatCrypto.is_available():
                self._crypto = LuomiNestWeChatCrypto(self._token, self._encoding_aes_key, self._corp_id)
                logger.info(f"[WeCom] Message crypto enabled")
            else:
                logger.warning(f"[WeCom] cryptography library not available, crypto disabled")

    async def start(self) -> None:
        if not self._corp_id or not self._secret:
            logger.warning(f"[WeCom] Missing corp_id/secret, API calls will fail")
            return
        token_ok = await self._refresh_access_token()
        if token_ok:
            logger.success(f"[WeCom] Adapter ready, access_token obtained")
        else:
            logger.warning(f"[WeCom] Failed to obtain access_token")

    async def stop(self) -> None:
        self._access_token = ""
        logger.info(f"[WeCom] Adapter stopped")

    async def send_message(self, response: PlatformResponse, target: str) -> bool:
        token = await self._ensure_access_token()
        if not token:
            return False

        import httpx

        url = f"{self.API_BASE}/message/send?access_token={token}"
        payload: dict[str, Any] = {
            "msgtype": "text",
            "agentid": int(self._agent_id) if self._agent_id else 0,
            "text": {"content": response.content},
            "safe": 0,
        }

        if target.startswith("group:"):
            payload["chatid"] = target[6:]
        else:
            payload["touser"] = target

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("errcode") == 0:
                        logger.info(f"[WeCom] Sent message to {target}: {response.content[:50]}")
                        return True
                    logger.error(f"[WeCom] Send failed: {data.get('errmsg')}")
                    return False
                logger.error(f"[WeCom] Send HTTP failed: {resp.status_code}")
                return False
        except Exception as e:
            logger.error(f"[WeCom] Send exception: {e}")
            return False

    async def verify_url(self, msg_signature: str, timestamp: str, nonce: str, echostr: str) -> str | None:
        """验证回调 URL 有效性（企业微信 GET 请求）。"""
        if not self._crypto:
            return echostr
        if not self._crypto.verify_signature(msg_signature, timestamp, nonce, echostr):
            logger.warning(f"[WeCom] URL verification signature mismatch")
            return None
        try:
            plain_echostr, _ = self._crypto.decrypt(echostr)
            return plain_echostr
        except Exception as e:
            logger.error(f"[WeCom] URL verification decrypt failed: {e}")
            return None

    async def handle_webhook(self, msg_signature: str, timestamp: str, nonce: str, body: str) -> None:
        """处理企业微信 webhook 消息（由 platform endpoint 调用）。"""
        if not self._crypto:
            logger.warning(f"[WeCom] Crypto not configured, cannot handle encrypted message")
            return

        xml_data = LuomiNestWeChatCrypto.parse_xml(body)
        encrypt = xml_data.get("Encrypt", "")
        if not encrypt:
            logger.warning(f"[WeCom] No Encrypt field in webhook body")
            return

        if not self._crypto.verify_signature(msg_signature, timestamp, nonce, encrypt):
            logger.warning(f"[WeCom] Webhook signature mismatch")
            return

        try:
            plain_xml, from_corp = self._crypto.decrypt(encrypt)
        except Exception as e:
            logger.error(f"[WeCom] Decrypt failed: {e}")
            return

        msg_data = LuomiNestWeChatCrypto.parse_xml(plain_xml)
        msg_type = msg_data.get("MsgType", "")

        if msg_type == "event":
            return

        if msg_type == "text" or msg_type == "image":
            await self._handle_user_message(msg_data)
        elif msg_type == "voice":
            await self._handle_user_message(msg_data)

    async def _handle_user_message(self, msg_data: dict[str, str]) -> None:
        from_user = msg_data.get("FromUserName", "")
        content = msg_data.get("Content", "").strip()
        msg_id = msg_data.get("MsgId", "")
        msg_type = msg_data.get("MsgType", "")

        if not content and msg_type != "image":
            return

        image_urls: list[str] = []
        if msg_type == "image":
            pic_url = msg_data.get("PicUrl", "")
            if pic_url:
                image_urls.append(pic_url)
            content = content or "[图片]"

        is_group = from_user.startswith("@") or msg_data.get("ChatId", "") != ""

        platform_msg = PlatformMessage(
            platform=self.platform_name,
            user_id=from_user,
            content=content,
            session_id=msg_data.get("ChatId", "") or from_user,
            message_id=msg_id,
            group_id=msg_data.get("ChatId", ""),
            sender_name=msg_data.get("UserName", from_user),
            is_group=is_group,
            image_urls=image_urls,
            raw=msg_data,
        )

        if is_group and not self._enable_group:
            return
        if not is_group and not self._enable_user:
            return

        response = await self._emit_message(platform_msg)
        if response and response.content:
            await self.send_message(response, from_user)

    async def _refresh_access_token(self) -> bool:
        import httpx

        url = f"{self.API_BASE}/gettoken?corpid={self._corp_id}&corpsecret={self._secret}"

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("errcode") == 0:
                        self._access_token = data.get("access_token", "")
                        expires_in = int(data.get("expires_in", 7200))
                        self._token_expires = time.time() + expires_in - 300
                        logger.info(f"[WeCom] Access token refreshed, expires in {expires_in}s")
                        return True
                    logger.error(f"[WeCom] Token refresh failed: {data.get('errmsg')}")
                    return False
                return False
        except Exception as e:
            logger.error(f"[WeCom] Token refresh exception: {e}")
            return False

    async def _ensure_access_token(self) -> str:
        if self._access_token and time.time() < self._token_expires:
            return self._access_token
        async with self._token_lock:
            if self._access_token and time.time() < self._token_expires:
                return self._access_token
            await self._refresh_access_token()
            return self._access_token
