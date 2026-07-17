import asyncio
import time
from typing import Any

from loguru import logger

from app.runtime.platform.base import BasePlatformAdapter, PlatformMessage, PlatformResponse
from app.runtime.platform.infrastructure.retry import RetryConfig, async_retry


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
        self._rate_limiter = _RateLimiter()

    def initialize(self, config: dict[str, Any]) -> None:
        super().initialize(config)
        self._app_id = config.get("app_id", "")
        self._app_secret = config.get("app_secret", "")
        self._token = config.get("token", "")
        self._enable_group = bool(config.get("enable_group", True))
        self._enable_private = bool(config.get("enable_private", True))

    async def start(self) -> None:
        if not self._app_id or not self._app_secret:
            logger.warning("[QQOfficial] Missing app_id/app_secret, API calls will fail")
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
            async with httpx.AsyncClient(timeout=15) as client:
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
    # Token 管理
    # ------------------------------------------------------------------

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
