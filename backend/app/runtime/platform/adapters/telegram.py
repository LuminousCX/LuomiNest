"""Telegram 适配器 - 通过 Telegram Bot API 接入 Telegram 平台。

纯消息协议适配器，负责：
- 将 Telegram Update 对象转换为 PlatformMessage
- 将 PlatformResponse 发送到 Telegram
- 提供配置模板和元数据

轮询/Webhook 调度由外部服务负责，适配器仅提供 handle_update() 入口。
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from loguru import logger

from app.runtime.platform.base import (
    AdapterStatus,
    BasePlatformAdapter,
    PlatformMessage,
    PlatformResponse,
)
from app.runtime.platform.infrastructure.truncation import MessageTruncator, TruncateMode


# Telegram Bot API 限制：单条消息最大 4096 个 UTF-16 编码单元
TELEGRAM_MAX_MESSAGE_LENGTH = 4096


class TelegramAdapter(BasePlatformAdapter):
    """Telegram Bot 适配器。

    职责边界：
    - 消息协议转换（Telegram Update ↔ PlatformMessage / PlatformResponse）
    - 通过 Telegram Bot API 发送消息
    - 提供 handle_update() 供外部调度器传入 Update 对象

    不包含：
    - Long Polling 循环
    - Webhook 服务器
    这些由外部服务负责。
    """

    platform_name = "telegram"

    # ─── 配置模板 ──────────────────────────────────────────────

    config_template = {
        "bot_token": "",
        "polling_interval": 1,
        "use_webhook": False,
        "webhook_url": "",
        "allowed_users": "",
    }

    config_metadata = {
        "bot_token": {
            "type": "string",
            "required": True,
            "label": "Bot Token",
            "sensitive": True,
        },
        "polling_interval": {
            "type": "number",
            "required": False,
            "default": 1,
            "label": "轮询间隔(秒)",
        },
        "use_webhook": {
            "type": "boolean",
            "required": False,
            "default": False,
            "label": "使用Webhook",
        },
        "webhook_url": {
            "type": "string",
            "required": False,
            "label": "Webhook URL",
        },
        "allowed_users": {
            "type": "string",
            "required": False,
            "label": "允许的用户(逗号分隔)",
        },
    }

    # ─── 初始化 ────────────────────────────────────────────────

    def __init__(self) -> None:
        super().__init__()
        self._bot_token: str = ""
        self._base_url: str = ""
        self._bot_id: str = ""
        self._bot_username: str = ""
        self._allowed_users: set[str] = set()
        self._http_client: httpx.AsyncClient | None = None
        self._truncator = MessageTruncator()

    def initialize(self, config: dict[str, Any]) -> None:
        """解析配置并初始化资源。"""
        super().initialize(config)
        self._bot_token = config.get("bot_token", "")
        self._base_url = f"https://api.telegram.org/bot{self._bot_token}"

        # 解析允许的用户列表
        allowed_raw = config.get("allowed_users", "")
        if allowed_raw:
            self._allowed_users = {
                u.strip() for u in allowed_raw.split(",") if u.strip()
            }

    async def start(self) -> None:
        """启动适配器，创建 HTTP 客户端并验证 Bot Token。"""
        await super().start()
        self.update_status(AdapterStatus.STARTING)

        self._http_client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(30.0, connect=10.0),
        )

        try:
            me = await self._api_request("getMe")
            self._bot_id = str(me.get("id", ""))
            self._bot_username = me.get("username", "")
            self._log(
                "success",
                "connection_established",
                f"Telegram Bot 已连接: @{self._bot_username} (ID: {self._bot_id})",
                details={"bot_id": self._bot_id, "username": self._bot_username},
            )
            self.update_status(AdapterStatus.RUNNING)
        except Exception as e:
            self._log("error", "connection_failed", f"Telegram Bot 连接失败: {e}", details={"error": str(e)})
            self.record_error(str(e))
            raise

    async def stop(self) -> None:
        """停止适配器，关闭 HTTP 客户端。"""
        await super().stop()
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        self._log("info", "connection_closed", "Telegram 适配器已停止")
        self.update_status(AdapterStatus.STOPPED)

    # ─── 消息接收 ──────────────────────────────────────────────

    async def handle_update(self, data: dict[str, Any]) -> PlatformMessage | None:
        """处理来自外部调度器的 Telegram Update 对象。

        Args:
            data: Telegram Update 对象（JSON dict）。

        Returns:
            转换后的 PlatformMessage，如果不满足条件则返回 None。
        """
        message = data.get("message")
        if not message:
            return None

        platform_msg = self._convert_to_platform_message(message)
        if not platform_msg:
            return None

        # 用户白名单过滤
        if self._allowed_users and platform_msg.user_id not in self._allowed_users:
            self._log(
                "info",
                "message_filtered",
                f"用户 {platform_msg.user_id} 不在允许列表中，已忽略",
                details={"user_id": platform_msg.user_id},
            )
            return None

        # 群聊中只有被 @ 或回复时才响应
        if platform_msg.is_group and not self._should_respond_in_group(message):
            return None

        self._log(
            "info",
            "message_received",
            f"收到消息 [{'群聊' if platform_msg.is_group else '私聊'}] "
            f"{platform_msg.sender_name}: {platform_msg.content[:50]}",
            details={
                "user_id": platform_msg.user_id,
                "sender_name": platform_msg.sender_name,
                "is_group": platform_msg.is_group,
                "group_id": platform_msg.group_id,
                "message_id": platform_msg.message_id,
            },
        )

        return platform_msg

    def _convert_to_platform_message(self, message: dict[str, Any]) -> PlatformMessage | None:
        """将 Telegram Message 对象转换为 PlatformMessage。"""
        chat = message.get("chat", {})
        from_user = message.get("from", {})
        chat_type = chat.get("type", "")

        user_id = str(from_user.get("id", ""))
        sender_name = (
            from_user.get("first_name", "") + " " + from_user.get("last_name", "")
        ).strip() or user_id
        message_id = str(message.get("message_id", ""))

        is_group = chat_type in ("group", "supergroup")
        group_id = str(chat.get("id", "")) if is_group else ""
        session_id = group_id if is_group else user_id

        # 解析文本内容
        text = message.get("text", "")

        # 解析图片消息
        image_urls: list[str] = []
        photo = message.get("photo")
        if photo and isinstance(photo, list) and len(photo) > 0:
            # Telegram 返回多个尺寸的 photo 数组，取最大尺寸（最后一个）
            largest = photo[-1]
            file_id = largest.get("file_id", "")
            if file_id:
                # 将 file_id 作为 URL 占位，实际下载需通过 getFile API
                image_urls.append(f"telegram_file://{file_id}")

        # 解析语音消息（仅记录日志，暂不处理）
        voice = message.get("voice")
        if voice:
            logger.info(
                f"[telegram] 收到语音消息 from {sender_name}，暂不支持处理"
            )

        audio = message.get("audio")
        if audio:
            logger.info(
                f"[telegram] 收到音频消息 from {sender_name}，暂不支持处理"
            )

        content = text.strip()
        if not content and not image_urls:
            return None

        return PlatformMessage(
            platform=self.platform_name,
            user_id=user_id,
            content=content,
            session_id=session_id,
            message_id=message_id,
            group_id=group_id,
            sender_name=sender_name,
            is_group=is_group,
            image_urls=image_urls,
            raw=message,
        )

    def _should_respond_in_group(self, message: dict[str, Any]) -> bool:
        """判断群聊消息是否应该响应（被 @ 或被回复）。"""
        # 被回复的消息
        reply_to = message.get("reply_to_message")
        if reply_to:
            reply_from = reply_to.get("from", {})
            if str(reply_from.get("id", "")) == self._bot_id:
                return True

        # 检查 entities 中是否有 @mention 本 Bot
        entities = message.get("entities", [])
        text = message.get("text", "")
        for entity in entities:
            if entity.get("type") == "mention":
                offset = entity.get("offset", 0)
                length = entity.get("length", 0)
                mentioned = text[offset : offset + length].lstrip("@").lower()
                # 匹配 bot username 或 bot id
                if mentioned in (self._bot_username.lower(), self._bot_id.lower()):
                    return True

        return False

    # ─── 消息发送 ──────────────────────────────────────────────

    async def send_message(self, response: PlatformResponse, target: str) -> bool:
        """向 Telegram 发送响应消息。

        Args:
            response: 要发送的 PlatformResponse。
            target: 目标标识，格式为 "chat:{chat_id}" 或纯 chat_id。

        Returns:
            发送成功返回 True，失败返回 False。
        """
        if not self._http_client:
            self._log("warning", "message_failed", "HTTP 客户端未初始化")
            return False

        chat_id = self._parse_target(target)
        if not chat_id:
            self._log("warning", "message_failed", f"无效的目标: {target}", details={"target": target})
            return False

        success = True

        # 发送文本消息
        if response.content:
            text = self._truncator.truncate(
                response.content,
                max_length=TELEGRAM_MAX_MESSAGE_LENGTH,
                mode=TruncateMode.UTF16,
            )
            ok = await self._send_text(chat_id, text, reply_to=response.reply_to)
            if not ok:
                success = False

        # 发送图片
        for url in response.image_urls:
            ok = await self._send_photo(chat_id, url, reply_to=response.reply_to)
            if not ok:
                success = False

        # 如果既没有文本也没有图片，发送空消息提示
        if not response.content and not response.image_urls:
            ok = await self._send_text(chat_id, "[空消息]", reply_to=response.reply_to)
            if not ok:
                success = False

        return success

    async def _send_text(
        self,
        chat_id: str,
        text: str,
        reply_to: str = "",
    ) -> bool:
        """发送文本消息到指定 chat。"""
        params: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
        }
        if reply_to:
            try:
                params["reply_parameters"] = {"message_id": int(reply_to)}
            except (ValueError, TypeError):
                pass

        try:
            await self._api_request("sendMessage", params)
            self._log(
                "info",
                "message_sent",
                f"文本消息已发送 -> {chat_id}: {text[:50]}",
                details={"chat_id": chat_id, "text_length": len(text)},
            )
            return True
        except Exception as e:
            # 如果 Markdown 解析失败，回退到纯文本
            if "can't parse entities" in str(e).lower():
                params.pop("parse_mode", None)
                try:
                    await self._api_request("sendMessage", params)
                    self._log(
                        "info",
                        "message_sent",
                        f"文本消息已发送(纯文本回退) -> {chat_id}: {text[:50]}",
                        details={"chat_id": chat_id},
                    )
                    return True
                except Exception as e2:
                    self._log("error", "message_failed", f"文本发送失败: {e2}", details={"error": str(e2), "chat_id": chat_id})
                    return False
            self._log("error", "message_failed", f"文本发送失败: {e}", details={"error": str(e), "chat_id": chat_id})
            return False

    async def _send_photo(
        self,
        chat_id: str,
        photo: str,
        reply_to: str = "",
    ) -> bool:
        """发送图片到指定 chat。

        Args:
            chat_id: 目标 chat ID。
            photo: 图片 URL 或 Telegram file_id。
            reply_to: 回复的消息 ID。
        """
        params: dict[str, Any] = {"chat_id": chat_id}
        if photo.startswith("telegram_file://"):
            params["photo"] = photo.replace("telegram_file://", "")
        else:
            params["photo"] = photo

        if reply_to:
            try:
                params["reply_parameters"] = {"message_id": int(reply_to)}
            except (ValueError, TypeError):
                pass

        try:
            await self._api_request("sendPhoto", params)
            self._log(
                "info",
                "message_sent",
                f"图片消息已发送 -> {chat_id}",
                details={"chat_id": chat_id},
            )
            return True
        except Exception as e:
            self._log("error", "message_failed", f"图片发送失败: {e}", details={"error": str(e), "chat_id": chat_id})
            return False

    # ─── Webhook 入口 ──────────────────────────────────────────

    async def handle_webhook(self, data: dict[str, Any]) -> None:
        """处理 Webhook 传入的 Update（供外部 Webhook 服务器调用）。

        与 handle_update 行为一致。

        Args:
            data: Telegram Update 对象。
        """
        await self.handle_update(data)

    # ─── 工具方法 ──────────────────────────────────────────────

    @staticmethod
    def get_target(data: dict[str, Any]) -> str:
        """从 Telegram Update 对象中提取回复目标标识。

        外部调度器在收到 handle_update 返回的 PlatformMessage 后，
        调用此方法获取 send_message 所需的 target 参数。

        Args:
            data: Telegram Update 对象。

        Returns:
            target 字符串，格式为 "chat:{chat_id}"。
            如果无法提取则返回空字符串。
        """
        message = data.get("message")
        if not message:
            return ""
        chat = message.get("chat", {})
        chat_id = chat.get("id", "")
        if not chat_id:
            return ""
        return f"chat:{chat_id}"

    async def download_image(self, file_id: str) -> str | None:
        """通过 Telegram getFile API 获取图片下载 URL。

        Args:
            file_id: Telegram 文件 ID（从 photo 消息中提取）。

        Returns:
            图片下载 URL，失败返回 None。
        """
        try:
            result = await self._api_request("getFile", {"file_id": file_id})
            file_path = result.get("file_path", "")
            if not file_path:
                self._log("warning", "download_failed", "getFile 返回空 file_path", details={"file_id": file_id})
                return None
            # Telegram 文件下载 URL 格式
            url = f"https://api.telegram.org/file/bot{self._bot_token}/{file_path}"
            self._log(
                "info",
                "image_url_resolved",
                f"图片 URL 已解析: {file_id[:20]}...",
                details={"file_id": file_id, "file_path": file_path},
            )
            return url
        except Exception as e:
            self._log("error", "download_failed", f"获取图片 URL 失败: {e}", details={"file_id": file_id, "error": str(e)})
            return None

    async def _api_request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """调用 Telegram Bot API。

        Args:
            method: API 方法名（如 sendMessage）。
            params: 请求参数。

        Returns:
            API 响应中的 result 字段。

        Raises:
            httpx.HTTPStatusError: HTTP 错误。
            RuntimeError: API 返回 ok=False。
        """
        if not self._http_client:
            raise RuntimeError("HTTP 客户端未初始化")

        try:
            resp = await self._http_client.post(method, json=params or {})
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status == 429:
                # 速率限制：读取 retry_after
                try:
                    body = e.response.json()
                    retry_after = body.get("parameters", {}).get("retry_after", 5)
                except Exception:
                    retry_after = 5
                self._log(
                    "warning",
                    "rate_limited",
                    f"Telegram API 速率限制，{retry_after}s 后重试",
                    details={"retry_after": retry_after, "method": method},
                )
                await asyncio.sleep(retry_after)
                # 重试一次
                resp = await self._http_client.post(method, json=params or {})
                resp.raise_for_status()
                data = resp.json()
                if not data.get("ok"):
                    desc = data.get("description", "Unknown error")
                    raise RuntimeError(f"Telegram API 错误: {desc}")
                return data.get("result", {})
            else:
                raise
        except httpx.RequestError as e:
            raise RuntimeError(f"Telegram API 网络错误: {e}") from e

        if not data.get("ok"):
            desc = data.get("description", "Unknown error")
            raise RuntimeError(f"Telegram API 错误: {desc}")

        return data.get("result", {})

    @staticmethod
    def _parse_target(target: str) -> str:
        """解析 target 标识为 chat_id。"""
        if ":" in target:
            _, chat_id = target.split(":", 1)
            return chat_id
        return target
