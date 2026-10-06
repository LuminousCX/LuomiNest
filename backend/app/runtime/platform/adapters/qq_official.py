import asyncio
import time
from typing import Any

from loguru import logger

from app.runtime.platform.base import BasePlatformAdapter, PlatformMessage, PlatformResponse
from app.runtime.platform.infrastructure.retry import RetryConfig, async_retry
from app.runtime.platform.infrastructure.token_manager import AppTokenMixin, parse_target


class _RateLimiter:
    """简易令牌桶速率限制器，用于 QQ 官方 API 调用。"""

    def __init__(self, max_per_second: float = 5.0) -> None:
        self._max_per_second = max_per_second
        self._min_interval = 1.0 / max_per_second
        self._last_request_time: float = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            if elapsed < self._min_interval:
                await asyncio.sleep(self._min_interval - elapsed)
            self._last_request_time = time.monotonic()

    def update_from_headers(self, headers: dict[str, str]) -> None:
        """根据响应头 X-RateLimit-Remaining 动态调整速率。"""
        remaining = headers.get("x-ratelimit-remaining")
        reset = headers.get("x-ratelimit-reset")
        if remaining is not None:
            try:
                rem = int(remaining)
                if rem <= 1:
                    # 即将耗尽，大幅降低速率
                    if reset is not None:
                        try:
                            reset_time = int(reset)
                            wait = max(reset_time - int(time.time()), 1)
                            self._min_interval = min(wait / max(rem, 1), 5.0)
                        except ValueError:
                            self._min_interval = 2.0
                    else:
                        self._min_interval = 2.0
                    logger.warning(
                        f"[QQOfficial] Rate limit low, remaining={rem}, "
                        f"adjusted interval to {self._min_interval:.2f}s"
                    )
                else:
                    # 恢复默认
                    self._min_interval = 1.0 / self._max_per_second
            except ValueError:
                # 响应头格式异常时忽略动态调整，回退到默认速率，避免中断主流程。
                self._min_interval = 1.0 / self._max_per_second
                logger.debug(
                    "[QQOfficial] Invalid rate limit headers, fallback to default interval."
                )


class RateLimitError(Exception):
    """QQ API 返回 429 时抛出。"""

    def __init__(self, retry_after: float = 1.0) -> None:
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded, retry after {retry_after}s")


class LuomiNestQQOfficialAdapter(AppTokenMixin, BasePlatformAdapter):
    """QQ 官方机器人适配器：通过 QQ 开放平台 OpenAPI 收发消息。

    工作流程：
    1. 使用 appId + appSecret 获取 access_token
    2. Webhook 接收事件回调（由 platform endpoint 统一注册路由）
    3. 收到消息事件后解析为 PlatformMessage，路由到主 Agent
    4. 主 Agent 响应后调用 OpenAPI 发送消息

    配置项：
    - app_id: QQ 开放平台应用 ID
    - app_secret: 应用密钥（同时作为 Webhook Ed25519 验签密钥的种子，官方算法）
    - webhook_secret: Webhook 验签密钥（可选，缺省回退 app_secret）
    - token: 机器人 token（QQ 官方已弃用，不参与任何校验，仅为兼容保留）
    - enable_group: 启用群消息
    - enable_private: 启用 C2C 消息
    """

    platform_name = "qq_official"

    # Token 相关日志前缀（AppTokenMixin）
    token_log_prefix = "[QQOfficial]"

    API_BASE = "https://api.sgroup.qq.com"

    def __init__(self) -> None:
        super().__init__()
        self._access_token: str = ""
        self._token_expires: float = 0
        self._token_lock = asyncio.Lock()
        self._rate_limiter = _RateLimiter()

    def initialize(self, config: dict[str, Any]) -> None:
        super().initialize(config)
        self._app_id = config.get("app_id", "")
        self._app_secret = config.get("app_secret", "")
        self._token = config.get("token", "")
        # P0-1 webhook 验签密钥：官方以 AppSecret 作为 Ed25519 种子，
        # webhook_secret 仅作显式覆盖入口，缺省回退 app_secret
        self._webhook_secret = str(config.get("webhook_secret", "") or self._app_secret or "")
        self._enable_group = bool(config.get("enable_group", True))
        self._enable_private = bool(config.get("enable_private", True))

    async def start(self) -> None:
        if not self._app_id or not self._app_secret:
            logger.warning("[QQOfficial] Missing app_id/app_secret, API calls will fail")
            logger.warning(
                "[QQOfficial] Webhook secret not configured, "
                "all webhook events will be rejected (fail-closed)"
            )
            return
        token_ok = await self._refresh_access_token()
        if token_ok:
            logger.success("[QQOfficial] Adapter ready, access_token obtained")
        else:
            logger.warning("[QQOfficial] Failed to obtain access_token, will retry on demand")

    async def stop(self) -> None:
        self._access_token = ""
        logger.info("[QQOfficial] Adapter stopped")

    # ------------------------------------------------------------------
    # 消息发送
    # ------------------------------------------------------------------

    async def send_message(self, response: PlatformResponse, target: str) -> bool:
        target_type, target_id = self._parse_target(target)
        if not target_id:
            logger.warning(f"[QQOfficial] Invalid target: {target}")
            return False

        token = await self._ensure_access_token()
        if not token:
            return False

        # 如果有图片，先通过富媒体 API 上传
        file_info = ""
        if response.image_urls:
            file_info = await self._upload_image(
                response.image_urls[0], target_type, target_id, token
            )

        return await self._send_with_retry(
            response=response,
            target_type=target_type,
            target_id=target_id,
            token=token,
            file_info=file_info,
        )

    async def _send_with_retry(
        self,
        response: PlatformResponse,
        target_type: str,
        target_id: str,
        token: str,
        file_info: str,
    ) -> bool:
        """带速率限制重试的消息发送。"""
        import httpx

        from app.core.config import settings

        if target_type == "group":
            url = f"{self.API_BASE}/v2/groups/{target_id}/messages"
        else:
            url = f"{self.API_BASE}/v2/users/{target_id}/messages"

        payload: dict[str, Any] = {
            "content": response.content,
            "msg_type": 0,
            "msg_id": response.reply_to or "",
        }
        if file_info:
            payload["file_info"] = file_info
            payload["msg_type"] = 7  # 富媒体消息

        headers = {"Authorization": f"QQBot {token}", "Content-Type": "application/json"}

        async def _do_send() -> bool:
            await self._rate_limiter.acquire()
            async with httpx.AsyncClient(timeout=settings.PLATFORM_HTTP_TIMEOUT) as client:
                resp = await client.post(url, json=payload, headers=headers)
                self._rate_limiter.update_from_headers(dict(resp.headers))

                if resp.status_code == 429:
                    retry_after = float(resp.headers.get("retry-after", "1"))
                    logger.warning(
                        f"[QQOfficial] Rate limited (429), retry after {retry_after}s"
                    )
                    raise RateLimitError(retry_after)

                if resp.status_code in (200, 201, 204):
                    logger.info(
                        f"[QQOfficial] Sent message to {target_id}: "
                        f"{response.content[:50]}"
                    )
                    return True

                logger.error(
                    f"[QQOfficial] Send failed: {resp.status_code} {resp.text[:200]}"
                )
                return False

        try:
            retry_config = RetryConfig(
                max_retries=3,
                base_delay=1.0,
                max_delay=30.0,
                jitter=0.5,
                retryable_exceptions=(RateLimitError,),
            )

            async def _on_retry(attempt: int, exc: Exception, delay: float) -> None:
                if isinstance(exc, RateLimitError):
                    logger.info(
                        f"[QQOfficial] 429 retry {attempt}/3, "
                        f"waiting {exc.retry_after:.1f}s (Retry-After)"
                    )

            return await async_retry(_do_send, config=retry_config, on_retry=_on_retry)
        except RateLimitError:
            logger.error("[QQOfficial] Send failed after all retries (rate limited)")
            return False
        except Exception as e:
            logger.error(f"[QQOfficial] Send exception: {e}")
            return False

    # ------------------------------------------------------------------
    # 富媒体上传
    # ------------------------------------------------------------------

    async def _upload_image(
        self, image_url: str, target_type: str, target_id: str, token: str
    ) -> str:
        """通过 QQ 富媒体 API 上传图片，返回 file_info。

        流程：
        1. 下载图片数据
        2. POST 到 /v2/groups/{group_openid}/files 或 /v2/users/{openid}/files
        3. 从响应中提取 file_info
        """
        import httpx

        if target_type == "group":
            upload_url = f"{self.API_BASE}/v2/groups/{target_id}/files"
        else:
            upload_url = f"{self.API_BASE}/v2/users/{target_id}/files"

        headers = {"Authorization": f"QQBot {token}"}

        try:
            # 判断文件类型
            srv_send_type = 1 if target_type == "group" else 0
            file_type = 1  # 图片

            # 上传到 QQ
            await self._rate_limiter.acquire()
            async with httpx.AsyncClient(timeout=30) as client:
                upload_resp = await client.post(
                    upload_url,
                    json={
                        "file_type": file_type,
                        "url": image_url,
                        "srv_send_type": srv_send_type,
                    },
                    headers={
                        **headers,
                        "Content-Type": "application/json",
                    },
                )
                self._rate_limiter.update_from_headers(
                    dict(upload_resp.headers)
                )

                if upload_resp.status_code in (200, 201):
                    data = upload_resp.json()
                    file_info = data.get("file_info", "")
                    if file_info:
                        logger.info("[QQOfficial] Image uploaded, file_info obtained")
                        return file_info
                    logger.warning(
                        f"[QQOfficial] Upload response missing file_info: "
                        f"{upload_resp.text[:200]}"
                    )
                else:
                    logger.error(
                        f"[QQOfficial] Image upload failed: "
                        f"{upload_resp.status_code} {upload_resp.text[:200]}"
                    )
        except Exception as e:
            logger.error(f"[QQOfficial] Image upload exception: {e}")

        return ""

    # ------------------------------------------------------------------
    # Webhook 事件处理
    # ------------------------------------------------------------------

    def _webhook_signing_key(self):
        """由 webhook secret 派生 Ed25519 签名私钥（对齐官方 Go 示例的种子推导）。

        官方算法：将 secret 字节串反复翻倍至 >= 32 字节后截取 32 字节作为
        Ed25519 种子，由种子确定性生成密钥对；事件推送用对应私钥签名，
        本端用派生公钥验签；op=13 回调地址验证则用本私钥对挑战串签名。
        webhook 调用量低，按请求即时派生即可。
        """
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        seed = self._webhook_secret.encode("utf-8")
        while len(seed) < 32:
            seed = seed * 2
        return Ed25519PrivateKey.from_private_bytes(seed[:32])

    def _webhook_verify_key(self):
        """由 webhook secret 派生 Ed25519 验签公钥（复用同一套种子推导）。"""
        return self._webhook_signing_key().public_key()

    def _build_callback_validation_payload(self, data: dict) -> dict[str, str] | None:
        """计算 op=13 回调地址验证应答（QQ 开放平台官方算法）。

        控制台保存回调地址时会推送 op=13 挑战（该请求本身不带签名头）：
            {"op": 13, "d": {"plain_token": "...", "event_ts": "..."}}
        服务端须用派生私钥对「event_ts + plain_token」做 Ed25519 签名（hex），
        并以 {"plain_token": ..., "signature": ...} 作为响应体原样返回。

        Returns:
            应答载荷；secret 未配置或挑战字段缺失时返回 None（fail-closed）。
        """
        if not self._webhook_secret:
            logger.warning(
                "[QQOfficial] Webhook secret not configured, "
                "reject op=13 callback validation (fail-closed)"
            )
            return None
        payload = data.get("d") or {}
        plain_token = str(payload.get("plain_token", "") or "")
        event_ts = str(payload.get("event_ts", "") or "")
        if not plain_token or not event_ts:
            logger.warning(
                "[QQOfficial] op=13 payload missing plain_token/event_ts, "
                "reject callback validation"
            )
            return None
        message = event_ts.encode("utf-8") + plain_token.encode("utf-8")
        signature = self._webhook_signing_key().sign(message).hex()
        logger.info("[QQOfficial] op=13 callback validation answered")
        return {"plain_token": plain_token, "signature": signature}

    def _verify_webhook_signature(
        self, signature: str, timestamp: str, raw_body: bytes | str
    ) -> bool:
        """校验 webhook 事件推送签名（P0-1，QQ 开放平台官方算法）。

        官方推送在请求头携带：
        - X-Signature-Ed25519：对「X-Signature-Timestamp + 原始请求体」的
          Ed25519 签名（hex 编码）；
        - X-Signature-Timestamp：签名所用时间戳。

        Fail-closed：未配置 secret、缺签名头、hex 格式非法或验签不通过
        一律拒绝，由调用方（platform endpoint）返回 401，不触发任何业务逻辑。

        Returns:
            True 表示验签通过；False 表示拒绝。
        """
        if not self._webhook_secret:
            logger.warning(
                "[QQOfficial] Webhook secret not configured, reject webhook (fail-closed)"
            )
            return False
        if not signature or not timestamp:
            logger.warning(
                "[QQOfficial] Missing X-Signature-Ed25519/X-Signature-Timestamp, "
                "reject webhook"
            )
            return False
        try:
            from cryptography.exceptions import InvalidSignature

            if isinstance(raw_body, str):
                raw_body = raw_body.encode("utf-8")
            message = timestamp.encode("utf-8") + raw_body
            self._webhook_verify_key().verify(bytes.fromhex(signature), message)
            return True
        except InvalidSignature:
            logger.warning("[QQOfficial] Webhook signature mismatch, reject webhook")
            return False
        except (ValueError, TypeError) as e:
            # hex 解码失败、时间戳非法等格式异常同样 fail-closed
            logger.warning(f"[QQOfficial] Malformed webhook signature, reject: {e}")
            return False

    async def handle_webhook(
        self,
        data: dict,
        *,
        signature: str = "",
        timestamp: str = "",
        raw_body: bytes | str = b"",
    ) -> bool | dict[str, str]:
        """处理 QQ 官方 webhook 事件（由 platform endpoint 调用）。

        op=13 回调地址验证：控制台保存回调地址时推送的挑战请求，本身不携带
        签名头，必须在验签之前识别；命中时返回
        ``{"plain_token": ..., "signature": ...}`` 应答载荷（endpoint 据此
        原样透出响应体，不能包统一信封），未配置 secret/字段缺失返回 False。

        普通事件推送（P0-1）：入口强制 Ed25519 验签，验签失败不触发任何业务
        逻辑并返回 False（endpoint 据此返回 401）。验签材料取自原始请求：
        - signature: 请求头 X-Signature-Ed25519
        - timestamp: 请求头 X-Signature-Timestamp
        - raw_body: 原始请求体字节（签名对象为 timestamp + 原始 body，
          不可用重新序列化后的 dict 代替）

        Returns:
            True 表示验签通过且事件已分发；False 表示验签失败被拒绝；
            dict 表示 op=13 回调地址验证应答载荷。
        """
        # op=13 回调地址验证（官方挑战请求不带签名头，先于验签识别）
        if data.get("op") in (13, "13"):
            payload = self._build_callback_validation_payload(data)
            return payload if payload is not None else False

        if not self._verify_webhook_signature(signature, timestamp, raw_body):
            return False

        event_type = data.get("event_type") or data.get("t", "")
        event_data = data.get("event") or data.get("d", {})

        if event_type in ("GROUP_AT_MESSAGE_CREATE", "GROUP_MESSAGE_CREATE"):
            if not self._enable_group:
                return True
            await self._handle_group_message(event_data)
        elif event_type in ("C2C_MESSAGE_CREATE", "DIRECT_MESSAGE_CREATE"):
            if not self._enable_private:
                return True
            await self._handle_private_message(event_data)
        return True

    async def _handle_group_message(self, data: dict) -> None:
        group_openid = data.get("group_openid", "")
        author = data.get("author", {})
        user_id = author.get("member_openid", "")
        content = data.get("content", "").strip()
        message_id = data.get("id", "")

        # 提取图片 URL（富媒体消息）
        image_urls = self._extract_image_urls(data)

        if not content and not image_urls:
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
            image_urls=image_urls,
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

        # 提取图片 URL（富媒体消息）
        image_urls = self._extract_image_urls(data)

        if not content and not image_urls:
            return

        platform_msg = PlatformMessage(
            platform=self.platform_name,
            user_id=user_openid,
            content=content,
            session_id=user_openid,
            message_id=message_id,
            sender_name=data.get("author", {}).get("username", user_openid),
            is_group=False,
            image_urls=image_urls,
            raw=data,
        )

        response = await self._emit_message(platform_msg)
        if response and response.content:
            response.reply_to = message_id
            await self.send_message(response, f"private:{user_openid}")

    # ------------------------------------------------------------------
    # 富媒体消息解析
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_image_urls(data: dict) -> list[str]:
        """从 QQ 消息事件中提取图片 URL。

        QQ 官方富媒体消息中图片可能出现在以下位置：
        - attachments 数组（type=image 的条目包含 url）
        - image 字段（直接 URL）
        - 消息内容中嵌入的 URL（http(s) 链接指向图片）
        """
        urls: list[str] = []

        # 1. attachments 数组
        attachments = data.get("attachments") or []
        for att in attachments:
            if att.get("content_type", "").startswith("image") or att.get("type") == "image":
                url = att.get("url", "")
                if url:
                    urls.append(url)

        # 2. 直接 image 字段
        image = data.get("image", "")
        if image and image not in urls:
            urls.append(image)

        # 3. embed 中的缩略图等
        embed = data.get("embed") or {}
        for img_key in ("thumbnail", "image"):
            img_url = embed.get(img_key, "")
            if img_url and img_url not in urls:
                urls.append(img_url)

        # 4. ark 模板消息中的图片
        ark = data.get("ark") or {}
        for kv in ark.get("kv", []):
            if kv.get("key", "").endswith(("#img", "#pic", "#image")):
                val = kv.get("value", "")
                if val and val.startswith("http") and val not in urls:
                    urls.append(val)

        return urls

    # ------------------------------------------------------------------
    # Token 管理（缓存/刷新骨架见 AppTokenMixin）
    # ------------------------------------------------------------------

    async def _fetch_token(self) -> tuple[str, int] | None:
        import httpx

        from app.core.config import settings

        url = f"{self.API_BASE}/app/getAppAccessToken"
        payload = {"appId": self._app_id, "clientSecret": self._app_secret}

        async with httpx.AsyncClient(timeout=settings.PLATFORM_HTTP_TIMEOUT) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("access_token", ""), int(data.get("expires_in", 7200))
            logger.error(f"[QQOfficial] Token refresh failed: {resp.status_code} {resp.text[:200]}")
            return None

    _parse_target = staticmethod(parse_target)
