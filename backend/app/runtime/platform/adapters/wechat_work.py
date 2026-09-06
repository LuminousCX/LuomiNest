import asyncio
import re
from typing import Any

from loguru import logger

from app.runtime.platform.adapters.wechat_crypto import LuomiNestWeChatCrypto
from app.runtime.platform.base import BasePlatformAdapter, PlatformMessage, PlatformResponse
from app.runtime.platform.infrastructure.token_manager import AppTokenMixin


class LuomiNestWeComAdapter(AppTokenMixin, BasePlatformAdapter):
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
    - bot_name: 机器人名称（用于群聊 @ 检测）
    """

    platform_name = "wechat_work"

    # Token 相关日志前缀（AppTokenMixin）
    token_log_prefix = "[WeCom]"

    API_BASE = "https://qyapi.weixin.qq.com/cgi-bin"

    def __init__(self) -> None:
        super().__init__()
        self._access_token: str = ""
        self._token_expires: float = 0
        self._token_lock = asyncio.Lock()
        self._crypto: LuomiNestWeChatCrypto | None = None
        self._bot_name: str = ""

    def initialize(self, config: dict[str, Any]) -> None:
        super().initialize(config)
        self._corp_id = config.get("corp_id", "")
        self._agent_id = config.get("agent_id", "")
        self._secret = config.get("secret", "")
        self._token = config.get("token", "")
        self._encoding_aes_key = config.get("encoding_aes_key", "")
        self._enable_user = bool(config.get("enable_user", True))
        self._enable_group = bool(config.get("enable_group", False))
        self._bot_name = config.get("bot_name", "")

        if self._token and self._encoding_aes_key and self._corp_id:
            if LuomiNestWeChatCrypto.is_available():
                self._crypto = LuomiNestWeChatCrypto(
                    self._token, self._encoding_aes_key, self._corp_id
                )
                logger.info("[WeCom] Message crypto enabled")
            else:
                logger.warning(
                    "[WeCom] cryptography library not available, crypto disabled"
                )

    async def start(self) -> None:
        if not self._corp_id or not self._secret:
            logger.warning("[WeCom] Missing corp_id/secret, API calls will fail")
            return
        token_ok = await self._refresh_access_token()
        if token_ok:
            logger.success("[WeCom] Adapter ready, access_token obtained")
        else:
            logger.warning("[WeCom] Failed to obtain access_token")

    async def stop(self) -> None:
        self._access_token = ""
        logger.info("[WeCom] Adapter stopped")

    # ------------------------------------------------------------------
    # 群聊判断
    # ------------------------------------------------------------------

    def is_group_chat(self, msg_data: dict[str, str]) -> bool:
        """综合判断消息是否来自群聊。

        判断规则（满足任一即视为群聊）：
        1. ChatId 以 "wr" 开头（企业微信群聊 ChatId 特征）
        2. 消息内容包含 @机器人名称
        """
        chat_id = msg_data.get("ChatId", "")
        if chat_id.startswith("wr"):
            return True

        content = msg_data.get("Content", "")
        if self._bot_name and content:
            at_pattern = re.compile(r"@" + re.escape(self._bot_name) + r"\b")
            if at_pattern.search(content):
                return True

        return False

    @staticmethod
    def _strip_at_bot(content: str, bot_name: str) -> str:
        """去除消息内容中的 @机器人名称 部分。"""
        if not bot_name:
            return content.strip()
        pattern = re.compile(r"@" + re.escape(bot_name) + r"\b\s*")
        return pattern.sub("", content).strip()

    # ------------------------------------------------------------------
    # 主动推送
    # ------------------------------------------------------------------

    async def send_message(self, response: PlatformResponse, target: str) -> bool:
        """根据响应类型发送消息到指定目标。

        target 格式：
        - 普通用户: 用户 userid
        - 群聊: "group:<chatid>"
        - 部门: "dept:<deptid>"

        支持的消息类型：
        - text: 纯文本
        - image: 图片（通过 image_urls）
        - markdown: 图文消息（markdown 格式）
        """
        token = await self._ensure_access_token()
        if not token:
            return False

        if response.message_type == "image" and response.image_urls:
            return await self._send_image_message(token, response, target)

        if response.message_type == "markdown" or (
            response.extra and response.extra.get("markdown")
        ):
            return await self._send_markdown_message(token, response, target)

        return await self._send_text_message(token, response, target)

    async def _send_text_message(
        self, token: str, response: PlatformResponse, target: str
    ) -> bool:
        payload = self._build_base_payload("text", target)
        payload["text"] = {"content": response.content}
        return await self._post_message(payload, target)

    async def _send_image_message(
        self, token: str, response: PlatformResponse, target: str
    ) -> bool:
        """发送图片消息。

        企业微信不直接支持 URL 发图，需要用 media_id。
        这里退化为文本+链接的方式，实际生产环境应先上传素材。
        """
        image_url = response.image_urls[0] if response.image_urls else ""
        if not image_url:
            return await self._send_text_message(token, response, target)

        content = response.content or ""
        content = f"{content}\n{image_url}" if content else image_url

        payload = self._build_base_payload("text", target)
        payload["text"] = {"content": content}
        return await self._post_message(payload, target)

    async def _send_markdown_message(
        self, token: str, response: PlatformResponse, target: str
    ) -> bool:
        """发送 markdown 格式消息（仅支持应用推送，不支持群聊机器人）。"""
        md_content = response.content
        if response.extra and response.extra.get("markdown"):
            md_content = response.extra["markdown"]

        payload = self._build_base_payload("markdown", target)
        payload["markdown"] = {"content": md_content}
        return await self._post_message(payload, target)

    def _build_base_payload(self, msg_type: str, target: str) -> dict[str, Any]:
        """构建消息基础 payload，根据 target 设置接收者。"""
        payload: dict[str, Any] = {
            "msgtype": msg_type,
            "agentid": int(self._agent_id) if self._agent_id else 0,
            "safe": 0,
        }
        if target.startswith("group:"):
            payload["chatid"] = target[6:]
        elif target.startswith("dept:"):
            payload["toparty"] = target[5:]
        else:
            payload["touser"] = target
        return payload

    async def _post_message(self, payload: dict[str, Any], target: str) -> bool:
        """发送消息到企业微信 API，自动处理 token 过期刷新。"""
        import httpx

        from app.core.config import settings

        token = await self._ensure_access_token()
        if not token:
            return False

        url = f"{self.API_BASE}/message/send?access_token={token}"

        try:
            async with httpx.AsyncClient(timeout=settings.PLATFORM_HTTP_TIMEOUT) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    errcode = data.get("errcode", -1)

                    # access_token 过期，刷新后重试一次
                    if errcode in (40014, 42001):
                        logger.warning("[WeCom] Token expired, refreshing and retrying")
                        await self._refresh_access_token()
                        new_token = await self._ensure_access_token()
                        if not new_token:
                            return False
                        retry_url = (
                            f"{self.API_BASE}/message/send?access_token={new_token}"
                        )
                        async with httpx.AsyncClient(timeout=settings.PLATFORM_HTTP_TIMEOUT) as retry_client:
                            retry_resp = await retry_client.post(
                                retry_url, json=payload
                            )
                            if retry_resp.status_code == 200:
                                retry_data = retry_resp.json()
                                if retry_data.get("errcode") == 0:
                                    logger.info(
                                        "[WeCom] Sent message to {} (after token refresh)",
                                        target,
                                    )
                                    return True
                                logger.error(
                                    "[WeCom] Send failed after retry: {}",
                                    retry_data.get("errmsg"),
                                )
                                return False

                    if errcode == 0:
                        msg_preview = str(
                            payload.get("text", {}).get("content", "")
                        )[:50]
                        logger.info(
                            "[WeCom] Sent {} to {}: {}",
                            payload.get("msgtype"),
                            target,
                            msg_preview,
                        )
                        return True
                    logger.error(
                        "[WeCom] Send failed: {} (errcode={})",
                        data.get("errmsg"),
                        errcode,
                    )
                    return False
                logger.error("[WeCom] Send HTTP failed: {}", resp.status_code)
                return False
        except Exception as e:
            logger.error("[WeCom] Send exception: {}", e)
            return False

    # ------------------------------------------------------------------
    # URL 验证
    # ------------------------------------------------------------------

    async def verify_url(
        self, msg_signature: str, timestamp: str, nonce: str, echostr: str
    ) -> str | None:
        """验证回调 URL 有效性（企业微信 GET 请求）。"""
        if not self._crypto:
            return echostr
        if not self._crypto.verify_signature(msg_signature, timestamp, nonce, echostr):
            logger.warning("[WeCom] URL verification signature mismatch")
            return None
        try:
            plain_echostr, _ = self._crypto.decrypt(echostr)
            return plain_echostr
        except Exception as e:
            logger.error("[WeCom] URL verification decrypt failed: {}", e)
            return None

    # ------------------------------------------------------------------
    # Webhook 消息处理
    # ------------------------------------------------------------------

    async def handle_webhook(
        self, msg_signature: str, timestamp: str, nonce: str, body: str
    ) -> None:
        """处理企业微信 webhook 消息（由 platform endpoint 调用）。"""
        if not self._crypto:
            logger.warning(
                "[WeCom] Crypto not configured, cannot handle encrypted message"
            )
            return

        xml_data = LuomiNestWeChatCrypto.parse_xml(body)
        encrypt = xml_data.get("Encrypt", "")
        if not encrypt:
            logger.warning("[WeCom] No Encrypt field in webhook body")
            return

        if not self._crypto.verify_signature(msg_signature, timestamp, nonce, encrypt):
            logger.warning("[WeCom] Webhook signature mismatch")
            return

        try:
            plain_xml, _from_corp = self._crypto.decrypt(encrypt)
        except Exception as e:
            logger.error("[WeCom] Decrypt failed: {}", e)
            return

        msg_data = LuomiNestWeChatCrypto.parse_xml(plain_xml)
        msg_type = msg_data.get("MsgType", "")

        if msg_type == "event":
            await self._handle_event_message(msg_data)
            return

        if msg_type in ("text", "image", "voice"):
            await self._handle_user_message(msg_data)

    # ------------------------------------------------------------------
    # 事件消息处理
    # ------------------------------------------------------------------

    async def _handle_event_message(self, msg_data: dict[str, str]) -> None:
        """处理企业微信事件类型消息。

        支持的事件：
        - click: 用户点击自定义菜单
        - enter_agent: 用户进入应用
        - subscribe: 用户关注应用
        - unsubscribe: 用户取消关注
        """
        event = msg_data.get("Event", "").lower()
        from_user = msg_data.get("FromUserName", "")
        event_key = msg_data.get("EventKey", "")

        if event == "click":
            await self._handle_click_event(msg_data, from_user, event_key)
        elif event == "enter_agent":
            await self._handle_enter_agent_event(msg_data, from_user)
        elif event == "subscribe":
            await self._handle_subscribe_event(msg_data, from_user)
        elif event == "unsubscribe":
            logger.info("[WeCom] User {} unsubscribed", from_user)
        else:
            logger.debug(
                "[WeCom] Unhandled event type: {} from {}", event, from_user
            )

    async def _handle_click_event(
        self, msg_data: dict[str, str], from_user: str, event_key: str
    ) -> None:
        """处理菜单点击事件，将 EventKey 作为内容发送给 Agent。"""
        if not event_key:
            logger.warning("[WeCom] Click event without EventKey from {}", from_user)
            return

        logger.info("[WeCom] Menu click event from {}: {}", from_user, event_key)

        platform_msg = PlatformMessage(
            platform=self.platform_name,
            user_id=from_user,
            content=f"/menu {event_key}",
            session_id=from_user,
            message_id=msg_data.get("MsgId", ""),
            sender_name=msg_data.get("FromUserName", from_user),
            is_group=False,
            raw=msg_data,
        )

        response = await self._emit_message(platform_msg)
        if response and response.content:
            await self.send_message(response, from_user)

    async def _handle_enter_agent_event(
        self, msg_data: dict[str, str], from_user: str
    ) -> None:
        """处理用户进入应用事件。"""
        logger.info("[WeCom] User {} entered agent", from_user)

        platform_msg = PlatformMessage(
            platform=self.platform_name,
            user_id=from_user,
            content="[用户进入应用]",
            session_id=from_user,
            message_id=msg_data.get("MsgId", ""),
            sender_name=from_user,
            is_group=False,
            raw=msg_data,
        )

        response = await self._emit_message(platform_msg)
        if response and response.content:
            await self.send_message(response, from_user)

    async def _handle_subscribe_event(
        self, msg_data: dict[str, str], from_user: str
    ) -> None:
        """处理用户关注事件。"""
        logger.info("[WeCom] User {} subscribed", from_user)

        platform_msg = PlatformMessage(
            platform=self.platform_name,
            user_id=from_user,
            content="[用户关注]",
            session_id=from_user,
            message_id=msg_data.get("MsgId", ""),
            sender_name=from_user,
            is_group=False,
            raw=msg_data,
        )

        response = await self._emit_message(platform_msg)
        if response and response.content:
            await self.send_message(response, from_user)

    # ------------------------------------------------------------------
    # 普通用户消息处理
    # ------------------------------------------------------------------

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

        is_group = self.is_group_chat(msg_data)

        # 群聊中去除 @机器人 前缀
        if is_group and self._bot_name:
            content = self._strip_at_bot(content, self._bot_name)
            if not content and msg_type != "image":
                return

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
            chat_id = msg_data.get("ChatId", "")
            send_target = f"group:{chat_id}" if chat_id else from_user
            await self.send_message(response, send_target)

    # ------------------------------------------------------------------
    # Token 管理（缓存/刷新骨架见 AppTokenMixin）
    # ------------------------------------------------------------------

    async def _fetch_token(self) -> tuple[str, int] | None:
        import httpx

        from app.core.config import settings

        url = (
            f"{self.API_BASE}/gettoken"
            f"?corpid={self._corp_id}&corpsecret={self._secret}"
        )

        async with httpx.AsyncClient(timeout=settings.PLATFORM_HTTP_TIMEOUT) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("errcode") == 0:
                    return data.get("access_token", ""), int(data.get("expires_in", 7200))
                logger.error(
                    "[WeCom] Token refresh failed: {}", data.get("errmsg")
                )
                return None
            return None
