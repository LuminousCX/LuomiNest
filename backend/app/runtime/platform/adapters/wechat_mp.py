import asyncio
import time
from typing import Any
from loguru import logger

from app.runtime.platform.base import BasePlatformAdapter, PlatformMessage, PlatformResponse
from app.runtime.platform.adapters.wechat_crypto import LuomiNestWeChatCrypto

# 用户信息缓存：{openid: (nickname, expire_timestamp)}
_user_info_cache: dict[str, tuple[str, float]] = {}
_USER_INFO_TTL = 300  # 5 分钟


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
        self._background_tasks: set[asyncio.Task] = set()
        self._welcome_message: str = "感谢关注！有什么可以帮你的吗？"

    def initialize(self, config: dict[str, Any]) -> None:
        super().initialize(config)
        self._app_id = config.get("app_id", "")
        self._app_secret = config.get("app_secret", "")
        self._token = config.get("token", "")
        self._encoding_aes_key = config.get("encoding_aes_key", "")
        self._enable_text = bool(config.get("enable_text", True))
        self._enable_image = bool(config.get("enable_image", True))
        self._welcome_message = config.get("welcome_message", self._welcome_message)

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
        # 如果 extra 中包含 template_id，使用模板消息发送
        if response.extra and response.extra.get("template_id"):
            return await self.send_template_message(
                target,
                template_id=response.extra["template_id"],
                data=response.extra.get("template_data", {}),
                url=response.extra.get("template_url", ""),
            )

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

    async def send_template_message(
        self,
        openid: str,
        template_id: str,
        data: dict[str, Any],
        url: str = "",
    ) -> bool:
        """发送模板消息。

        Args:
            openid: 接收者的 openid
            template_id: 模板消息 ID
            data: 模板数据，格式如 {"first": {"value": "xxx", "color": "#173177"}}
            url: 点击模板消息跳转的链接（可选）
        """
        token = await self._ensure_access_token()
        if not token:
            return False

        import httpx

        api_url = f"{self.API_BASE}/message/template/send?access_token={token}"
        payload: dict[str, Any] = {
            "touser": openid,
            "template_id": template_id,
            "data": data,
        }
        if url:
            payload["url"] = url

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(api_url, json=payload)
                if resp.status_code == 200:
                    result = resp.json()
                    if result.get("errcode") == 0:
                        logger.info(f"[WeChatMP] Template message sent to {openid}, template={template_id}")
                        return True
                    logger.error(f"[WeChatMP] Template message failed: {result.get('errmsg')}")
                    return False
                return False
        except Exception as e:
            logger.error(f"[WeChatMP] Template message exception: {e}")
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
            event = msg_data.get("Event", "")
            if event in ("subscribe", "unsubscribe", "SCAN", "LOCATION", "CLICK", "VIEW"):
                _task = asyncio.create_task(self._process_event(msg_data))
                self._background_tasks.add(_task)
                _task.add_done_callback(self._background_tasks.discard)
            return ""

        _task = asyncio.create_task(self._process_message(msg_data))
        self._background_tasks.add(_task)
        _task.add_done_callback(self._background_tasks.discard)
        return ""

    async def _process_event(self, msg_data: dict[str, str]) -> None:
        """处理事件消息。"""
        event = msg_data.get("Event", "").lower()
        from_user = msg_data.get("FromUserName", "")

        if event == "subscribe":
            logger.info(f"[WeChatMP] User subscribed: {from_user}")
            # 发送欢迎消息
            import httpx
            token = await self._ensure_access_token()
            if token:
                url = f"{self.API_BASE}/message/custom/send?access_token={token}"
                payload = {
                    "touser": from_user,
                    "msgtype": "text",
                    "text": {"content": self._welcome_message},
                }
                try:
                    async with httpx.AsyncClient(timeout=15) as client:
                        await client.post(url, json=payload)
                except Exception as e:
                    logger.error(f"[WeChatMP] Welcome message failed: {e}")

        elif event == "unsubscribe":
            logger.info(f"[WeChatMP] User unsubscribed: {from_user}")

        elif event == "scan":
            scan_content = msg_data.get("EventKey", "").strip()
            if scan_content:
                sender_name = await self._get_sender_name(from_user)
                platform_msg = PlatformMessage(
                    platform=self.platform_name,
                    user_id=from_user,
                    content=scan_content,
                    session_id=from_user,
                    message_id=msg_data.get("Ticket", ""),
                    sender_name=sender_name,
                    is_group=False,
                    raw=msg_data,
                )
                response = await self._emit_message(platform_msg)
                if response and response.content:
                    await self.send_message(response, from_user)

        elif event == "location":
            latitude = msg_data.get("Latitude", "")
            longitude = msg_data.get("Longitude", "")
            logger.info(f"[WeChatMP] Location update from {from_user}: lat={latitude}, lng={longitude}")

        elif event == "click":
            menu_key = msg_data.get("EventKey", "").strip()
            if menu_key:
                sender_name = await self._get_sender_name(from_user)
                platform_msg = PlatformMessage(
                    platform=self.platform_name,
                    user_id=from_user,
                    content=f"[菜单] {menu_key}",
                    session_id=from_user,
                    message_id="",
                    sender_name=sender_name,
                    is_group=False,
                    raw=msg_data,
                )
                response = await self._emit_message(platform_msg)
                if response and response.content:
                    await self.send_message(response, from_user)

        elif event == "view":
            view_url = msg_data.get("EventKey", "")
            logger.info(f"[WeChatMP] User {from_user} clicked menu link: {view_url}")

    async def _get_sender_name(self, openid: str) -> str:
        """获取用户昵称，优先从缓存获取，失败时回退到 openid。"""
        global _user_info_cache
        now = time.time()

        # 检查缓存
        cached = _user_info_cache.get(openid)
        if cached:
            nickname, expire_at = cached
            if now < expire_at:
                return nickname
            # 过期，移除
            del _user_info_cache[openid]

        # 调用微信用户信息 API
        token = await self._ensure_access_token()
        if not token:
            return openid

        import httpx
        url = f"{self.API_BASE}/user/info?openid={openid}&lang=zh_CN"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    nickname = data.get("nickname", "")
                    if nickname:
                        _user_info_cache[openid] = (nickname, now + _USER_INFO_TTL)
                        return nickname
                    logger.debug(f"[WeChatMP] User info has no nickname for {openid}")
                    return openid
                return openid
        except Exception as e:
            logger.debug(f"[WeChatMP] Get user info failed with exception: {e}")
            return openid

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

        sender_name = await self._get_sender_name(from_user)
        platform_msg = PlatformMessage(
            platform=self.platform_name,
            user_id=from_user,
            content=content,
            session_id=from_user,
            message_id=msg_id,
            sender_name=sender_name,
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
