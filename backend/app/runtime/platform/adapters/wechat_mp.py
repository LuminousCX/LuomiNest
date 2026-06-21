import asyncio
import time
from typing import Any
from loguru import logger

from app.runtime.platform.base import BasePlatformAdapter, PlatformMessage, PlatformResponse
from app.runtime.platform.adapters.wechat_crypto import LuomiNestWeChatCrypto


class LuomiNestWeChatMPAdapter(BasePlatformAdapter):
    """微信公众号适配器：通过公众号 API 收发消息。

    工作流程：
    1. 使用 app_id + app_secret 获取 access_token
    2. Webhook 接收消息回调（XML 格式，可能加密）
    3. 解析消息后路由到主 Agent
    4. 主 Agent 响应后通过客服消息 API 发送（避免 5 秒超时）

    配置项：
    - app_id: 公众号 AppID
    - app_secret: 公众号 AppSecret
    - token: 服务器配置的 Token
    - encoding_aes_key: 服务器配置的 EncodingAESKey
    - enable_text: 启用文本消息
    - enable_image: 启用图片消息
    """

    platform_name = "wechat_mp"

    API_BASE = "https://api.weixin.qq.com/cgi-bin"

    def __init__(self) -> None:
        super().__init__()
        self._access_token: str = ""
        self._token_expires: float = 0
        self._token_lock = asyncio.Lock()
        self._crypto: LuomiNestWeChatCrypto | None = None

    def initialize(self, config: dict[str, Any]) -> None:
        super().initialize(config)
        self._app_id = config.get("app_id", "")
        self._app_secret = config.get("app_secret", "")
        self._token = config.get("token", "")
        self._encoding_aes_key = config.get("encoding_aes_key", "")
        self._enable_text = bool(config.get("enable_text", True))
        self._enable_image = bool(config.get("enable_image", True))

        if self._token and self._encoding_aes_key and self._app_id:
            if LuomiNestWeChatCrypto.is_available():
                self._crypto = LuomiNestWeChatCrypto(self._token, self._encoding_aes_key, self._app_id)
                logger.info(f"[WeChatMP] Message crypto enabled")
            else:
                logger.warning(f"[WeChatMP] cryptography library not available, crypto disabled")

    async def start(self) -> None:
        if not self._app_id or not self._app_secret:
            logger.warning(f"[WeChatMP] Missing app_id/app_secret, API calls will fail")
            return
        token_ok = await self._refresh_access_token()
        if token_ok:
            logger.success(f"[WeChatMP] Adapter ready, access_token obtained")
        else:
            logger.warning(f"[WeChatMP] Failed to obtain access_token")

    async def stop(self) -> None:
        self._access_token = ""
        logger.info(f"[WeChatMP] Adapter stopped")

    async def send_message(self, response: PlatformResponse, target: str) -> bool:
        token = await self._ensure_access_token()
        if not token:
            return False

        import httpx

        url = f"{self.API_BASE}/message/custom/send?access_token={token}"
        payload: dict[str, Any] = {
            "touser": target,
            "msgtype": "text",
            "text": {"content": response.content},
        }

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("errcode") == 0:
                        logger.info(f"[WeChatMP] Sent message to {target}: {response.content[:50]}")
                        return True
                    logger.error(f"[WeChatMP] Send failed: {data.get('errmsg')}")
                    return False
                return False
        except Exception as e:
            logger.error(f"[WeChatMP] Send exception: {e}")
            return False

    async def verify_url(self, signature: str, timestamp: str, nonce: str, echostr: str) -> str | None:
        """验证服务器地址有效性（公众号 GET 请求）。"""
        if not self._crypto:
            if self._verify_plain_signature(signature, timestamp, nonce):
                return echostr
            return None

        if not self._crypto.verify_signature(signature, timestamp, nonce, echostr):
            logger.warning(f"[WeChatMP] URL verification signature mismatch")
            return None
        try:
            plain_echostr, _ = self._crypto.decrypt(echostr)
            return plain_echostr
        except Exception as e:
            logger.error(f"[WeChatMP] URL verification decrypt failed: {e}")
            return None

    def _verify_plain_signature(self, signature: str, timestamp: str, nonce: str) -> bool:
        if not self._token:
            return False
        parts = sorted([self._token, timestamp, nonce])
        computed = __import__("hashlib").sha1("".join(parts).encode()).hexdigest()
        return computed == signature

    async def handle_webhook(self, signature: str, timestamp: str, nonce: str, body: str) -> str:
        """处理公众号 webhook 消息，返回被动回复 XML（或空字符串表示异步处理）。

        返回空字符串时，响应将通过客服消息 API 异步发送。
        """
        xml_data = LuomiNestWeChatCrypto.parse_xml(body)
        encrypt = xml_data.get("Encrypt", "")

        if encrypt:
            if not self._crypto:
                logger.warning(f"[WeChatMP] Encrypted message but crypto not configured")
                return ""
            if not self._crypto.verify_signature(signature, timestamp, nonce, encrypt):
                logger.warning(f"[WeChatMP] Webhook signature mismatch")
                return ""
            try:
                plain_xml, _ = self._crypto.decrypt(encrypt)
            except Exception as e:
                logger.error(f"[WeChatMP] Decrypt failed: {e}")
                return ""
            msg_data = LuomiNestWeChatCrypto.parse_xml(plain_xml)
        else:
            if self._token and not self._verify_plain_signature(signature, timestamp, nonce):
                logger.warning(f"[WeChatMP] Plain mode signature mismatch")
                return ""
            msg_data = xml_data

        msg_type = msg_data.get("MsgType", "")
        if msg_type == "event":
            return ""

        asyncio.create_task(self._process_message(msg_data))
        return ""

    async def _process_message(self, msg_data: dict[str, str]) -> None:
        msg_type = msg_data.get("MsgType", "")
        from_user = msg_data.get("FromUserName", "")
        content = msg_data.get("Content", "").strip()
        msg_id = msg_data.get("MsgId", "")

        if msg_type == "text":
            if not self._enable_text:
                return
        elif msg_type == "image":
            if not self._enable_image:
                return
            content = content or "[图片]"
        else:
            return

        if not content:
            return

        image_urls: list[str] = []
        if msg_type == "image":
            pic_url = msg_data.get("PicUrl", "")
            if pic_url:
                image_urls.append(pic_url)

        platform_msg = PlatformMessage(
            platform=self.platform_name,
            user_id=from_user,
            content=content,
            session_id=from_user,
            message_id=msg_id,
            sender_name=from_user,
            is_group=False,
            image_urls=image_urls,
            raw=msg_data,
        )

        response = await self._emit_message(platform_msg)
        if response and response.content:
            await self.send_message(response, from_user)

    async def _refresh_access_token(self) -> bool:
        import httpx

        url = f"{self.API_BASE}/token?grant_type=client_credential&appid={self._app_id}&secret={self._app_secret}"

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    if "access_token" in data:
                        self._access_token = data.get("access_token", "")
                        expires_in = int(data.get("expires_in", 7200))
                        self._token_expires = time.time() + expires_in - 300
                        logger.info(f"[WeChatMP] Access token refreshed, expires in {expires_in}s")
                        return True
                    logger.error(f"[WeChatMP] Token refresh failed: {data.get('errmsg')}")
                    return False
                return False
        except Exception as e:
            logger.error(f"[WeChatMP] Token refresh exception: {e}")
            return False

    async def _ensure_access_token(self) -> str:
        if self._access_token and time.time() < self._token_expires:
            return self._access_token
        async with self._token_lock:
            if self._access_token and time.time() < self._token_expires:
                return self._access_token
            await self._refresh_access_token()
            return self._access_token
