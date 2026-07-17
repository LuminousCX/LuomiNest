"""Discord 适配器 - 通过 Discord Bot 接入 Discord 服务器。

实现 Discord Gateway v10 协议，通过 WebSocket 接收消息，
通过 REST API 发送消息。支持 DM 和 Guild 消息、Embed、
附件图片、自动重连和心跳维护。
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import httpx

from app.runtime.platform.base import (
    BasePlatformAdapter,
    PlatformMessage,
    PlatformResponse,
    AdapterStatus,
)
from app.runtime.platform.infrastructure.reconnect import (
    ReconnectMixin,
    ReconnectStrategy,
)
from app.runtime.platform.infrastructure.retry import RetryConfig, async_retry
from app.runtime.platform.infrastructure.truncation import MessageTruncator, TruncateMode

# ── Gateway Opcodes ──────────────────────────────────────────────────────────
OP_DISPATCH = 0
OP_HEARTBEAT = 1
OP_IDENTIFY = 2
OP_PRESENCE_UPDATE = 3
OP_VOICE_STATE_UPDATE = 4
OP_RESUME = 6
OP_RECONNECT = 7
OP_REQUEST_GUILD_MEMBERS = 8
OP_INVALID_SESSION = 9
OP_HELLO = 10
OP_HEARTBEAT_ACK = 11

# ── Gateway Close Codes ──────────────────────────────────────────────────────
GATEWAY_CLOSE_CODES: dict[int, str] = {
    4000: "未知错误",
    4001: "无效的 Gateway opcode",
    4002: "无效的 payload",
    4003: "未发送 Identify",
    4004: "认证失败（Token 无效）",
    4005: "已发送过 Identify",
    4007: "无效的 seq",
    4008: "发送 payload 过快",
    4009: "会话超时",
    4010: "无效的 shard",
    4011: "需要分片",
    4012: "无效的 API 版本",
    4013: "无效的 intents",
    4014: "权限不足（intents 未开启或已被禁用）",
}

# ── Intents ──────────────────────────────────────────────────────────────────
INTENT_GUILDS = 1 << 0
INTENT_GUILD_MESSAGES = 1 << 9
INTENT_MESSAGE_CONTENT = 1 << 15
INTENT_DIRECT_MESSAGES = 1 << 12
DEFAULT_INTENTS = INTENT_GUILDS | INTENT_GUILD_MESSAGES | INTENT_MESSAGE_CONTENT | INTENT_DIRECT_MESSAGES

# ── Constants ────────────────────────────────────────────────────────────────
GATEWAY_URL = "wss://gateway.discord.gg/?v=10&encoding=json"
API_BASE = "https://discord.com/api/v10"
MAX_MESSAGE_LENGTH = 2000


class DiscordAdapter(ReconnectMixin, BasePlatformAdapter):
    """Discord Bot 适配器：通过 Gateway WebSocket 接收消息，REST API 发送消息。

    工作流程：
    1. 连接到 Discord Gateway WebSocket
    2. 接收 Hello → 发送 Identify → 接收 Ready
    3. 维护心跳（定期发送 opcode 1）
    4. 接收 MESSAGE_CREATE 事件并路由到主 Agent
    5. 通过 REST API 发送响应消息
    """

    platform_name = "discord"

    # ── 配置元数据 ────────────────────────────────────────────────────────────
    config_metadata: dict[str, dict[str, Any]] = {
        "bot_token": {
            "type": "string",
            "required": True,
            "label": "Bot Token",
            "sensitive": True,
        },
        "intents": {
            "type": "number",
            "required": False,
            "default": DEFAULT_INTENTS,
            "label": "Gateway Intents",
        },
        "allowed_guilds": {
            "type": "string",
            "required": False,
            "label": "允许的服务器ID(逗号分隔)",
        },
        "prefix": {
            "type": "string",
            "required": False,
            "default": "",
            "label": "命令前缀",
        },
    }

    def __init__(self) -> None:
        super().__init__()
        self._bot_token: str = ""
        self._intents: int = DEFAULT_INTENTS
        self._allowed_guilds: set[str] = set()
        self._prefix: str = ""

        # Gateway 状态
        self._ws: Any = None
        self._session_id: str | None = None
        self._sequence: int | None = None
        self._resume_gateway_url: str | None = None
        self._heartbeat_interval: float = 41.25
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._heartbeat_ack_received: bool = True
        self._self_user_id: str = ""

        # HTTP 客户端
        self._http_client: httpx.AsyncClient | None = None

        # 消息截断器
        self._truncator = MessageTruncator(default_suffix="...")

        # 运行控制
        self._running: bool = False
        self._gateway_task: asyncio.Task[None] | None = None

    # ── 初始化 ────────────────────────────────────────────────────────────────

    def initialize(self, config: dict[str, Any]) -> None:
        """解析配置并初始化资源。"""
        super().initialize(config)
        self._bot_token = config.get("bot_token", "")
        if not self._bot_token:
            raise ValueError("Discord 适配器需要 bot_token 配置")

        self._intents = int(config.get("intents", DEFAULT_INTENTS))
        self._prefix = config.get("prefix", "")

        allowed_guilds_raw = config.get("allowed_guilds", "")
        if allowed_guilds_raw:
            self._allowed_guilds = {
                g.strip() for g in str(allowed_guilds_raw).split(",") if g.strip()
            }

        # 配置重连策略
        self.set_reconnect_strategy(ReconnectStrategy(
            initial_delay=2.0,
            max_delay=60.0,
            multiplier=2.0,
            max_attempts=0,  # 无限重试
            jitter=2.0,
        ))

    # ── 生命周期 ──────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """启动 Discord Gateway 连接。"""
        await super().start()
        self._running = True
        self._http_client = httpx.AsyncClient(
            base_url=API_BASE,
            headers={
                "Authorization": f"Bot {self._bot_token}",
                "Content-Type": "application/json",
                "User-Agent": "LuomiNest Bot",
            },
            timeout=httpx.Timeout(30.0),
        )

        self._log("info", "starting", "正在连接 Discord Gateway...")
        self._gateway_task = asyncio.create_task(self._gateway_loop())

    async def stop(self) -> None:
        """停止 Discord Gateway 连接。"""
        self._running = False
        self._log("info", "stopping", "正在停止 Discord 适配器...")

        await self._cancel_reconnect()

        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                # 任务在停止流程中被主动取消，这是预期行为。
                # 忽略该异常以继续执行清理逻辑。
                pass
            self._heartbeat_task = None

        if self._gateway_task and not self._gateway_task.done():
            self._gateway_task.cancel()
            try:
                await self._gateway_task
            except asyncio.CancelledError:
                # 任务在停止流程中被主动取消，这是预期行为。
                # 忽略该异常以继续执行清理逻辑。
                pass
            self._gateway_task = None

        if self._ws:
            try:
                await self._ws.close(1000, "Adapter stopping")
            except Exception:
                pass
            self._ws = None

        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

        self.update_status(AdapterStatus.STOPPED)
        self._log("info", "stopped", "Discord 适配器已停止")

    # ── Gateway 连接循环 ──────────────────────────────────────────────────────

    async def _gateway_loop(self) -> None:
        """Gateway 主连接循环，处理连接、事件接收和断线恢复。"""
        import websockets
        from websockets.exceptions import ConnectionClosed

        while self._running:
            try:
                url = self._resume_gateway_url or GATEWAY_URL
                self._log("info", "connecting", f"正在连接 Gateway: {url}")
                self.update_status(
                    AdapterStatus.RECONNECTING if self._resume_gateway_url else AdapterStatus.STARTING
                )

                async with websockets.connect(
                    url,
                    max_size=10 * 1024 * 1024,  # 10MB
                    ping_interval=None,  # 我们自己管理心跳
                    close_timeout=10,
                ) as ws:
                    self._ws = ws
                    self._log("success", "connected", "WebSocket 已连接，等待 Hello...")
                    await self._handle_connection(ws)

            except ConnectionClosed as e:
                close_code = e.code
                close_reason = e.reason or ""
                self._ws = None

                # 检查是否为不可恢复的关闭码
                if close_code in (4004, 4010, 4011, 4012, 4013, 4014):
                    error_msg = GATEWAY_CLOSE_CODES.get(close_code, f"未知关闭码 {close_code}")
                    self._log("error", "gateway_fatal", f"Gateway 致命错误: {error_msg} ({close_code})")
                    self.record_error(f"Gateway closed: {close_code} - {error_msg}")
                    self._running = False
                    return

                # 可恢复的断开 → 使用 Resume
                self._log(
                    "warning", "gateway_disconnected",
                    f"Gateway 连接断开 (code={close_code}), 将尝试 Resume...",
                    details={"close_code": close_code, "reason": close_reason},
                )
                self._stop_heartbeat()

                if not self._running:
                    return

                # 使用重连框架调度重连
                self._schedule_reconnect()
                # 等待重连完成
                if self._reconnect_task:
                    await self._reconnect_task
                continue

            except asyncio.CancelledError:
                self._ws = None
                self._stop_heartbeat()
                return
            except Exception as e:
                self._ws = None
                self._stop_heartbeat()
                self._log("error", "gateway_error", f"Gateway 异常: {type(e).__name__}: {e}")

                if not self._running:
                    return

                self._schedule_reconnect()
                if self._reconnect_task:
                    await self._reconnect_task
                continue

    async def _do_reconnect(self) -> bool:
        """重连框架回调：尝试重新连接 Gateway。"""
        # _do_reconnect 不直接在这里做完整连接，
        # 而是让 _gateway_loop 的 while 循环来处理
        # 返回 True 让重连框架认为成功，实际连接由 _gateway_loop 继续
        return True

    async def _handle_connection(self, ws: Any) -> None:
        """处理 WebSocket 连接上的所有事件。"""
        async for raw_msg in ws:
            if not self._running:
                break

            try:
                payload = json.loads(raw_msg)
            except json.JSONDecodeError:
                self._log("warning", "invalid_json", "收到无效的 JSON 数据")
                continue

            await self._dispatch_gateway_event(payload)

    # ── Gateway 事件分发 ──────────────────────────────────────────────────────

    async def _dispatch_gateway_event(self, payload: dict[str, Any]) -> None:
        """分发 Gateway 事件到对应处理器。"""
        op = payload.get("op")
        data = payload.get("d")
        seq = payload.get("s")
        event_name = payload.get("t")

        # 更新序列号
        if seq is not None:
            self._sequence = seq

        if op == OP_HELLO:
            await self._handle_hello(data)
        elif op == OP_DISPATCH:
            await self._handle_dispatch(event_name, data)
        elif op == OP_HEARTBEAT_ACK:
            self._heartbeat_ack_received = True
        elif op == OP_HEARTBEAT:
            # Discord 要求立即发送心跳
            await self._send_heartbeat()
        elif op == OP_RECONNECT:
            self._log("warning", "reconnect_requested", "Discord 请求重连")
            if self._ws:
                await self._ws.close(4000, "Reconnect requested")
        elif op == OP_INVALID_SESSION:
            self._log("warning", "invalid_session", "会话无效，将重新 Identify")
            self._session_id = None
            self._sequence = None
            self._resume_gateway_url = None
            if self._ws:
                await self._ws.close(4000, "Invalid session")

    async def _handle_hello(self, data: dict[str, Any]) -> None:
        """处理 Hello 事件（opcode 10）。"""
        self._heartbeat_interval = data.get("heartbeat_interval", 41250) / 1000.0
        self._log("info", "hello_received", f"收到 Hello，心跳间隔: {self._heartbeat_interval:.1f}s")

        # 启动心跳任务
        self._start_heartbeat()

        # 发送 Identify 或 Resume
        if self._session_id and self._sequence is not None:
            await self._send_resume()
        else:
            await self._send_identify()

    async def _handle_dispatch(self, event_name: str | None, data: Any) -> None:
        """处理 DISPATCH 事件（opcode 0）。"""
        if event_name == "READY":
            await self._handle_ready(data)
        elif event_name == "RESUMED":
            self._log("success", "resumed", "会话已恢复 (RESUMED)")
            self.update_status(AdapterStatus.RUNNING)
        elif event_name == "MESSAGE_CREATE":
            await self._handle_message_create(data)

    async def _handle_ready(self, data: dict[str, Any]) -> None:
        """处理 Ready 事件。"""
        user = data.get("user", {})
        self._self_user_id = str(user.get("id", ""))
        self._session_id = data.get("session_id")
        self._resume_gateway_url = data.get("resume_gateway_url")

        self._log(
            "success", "ready",
            f"Discord Bot 已就绪: {user.get('username', 'unknown')}#{user.get('discriminator', '')}",
            details={
                "user_id": self._self_user_id,
                "session_id": self._session_id,
                "guilds": len(data.get("guilds", [])),
            },
        )
        self.update_status(AdapterStatus.RUNNING)

    # ── 消息处理 ──────────────────────────────────────────────────────────────

    async def _handle_message_create(self, data: dict[str, Any]) -> None:
        """处理 MESSAGE_CREATE 事件。"""
        # 忽略 Bot 自己的消息
        author = data.get("author", {})
        if author.get("bot", False):
            return

        guild_id = data.get("guild_id")
        channel_id = data.get("channel_id", "")
        is_dm = guild_id is None

        # Guild 过滤
        if guild_id and self._allowed_guilds and guild_id not in self._allowed_guilds:
            return

        # 提取文本内容和图片
        content = data.get("content", "")
        image_urls = self._extract_attachments(data.get("attachments", []))

        # 处理消息引用中的图片
        if referenced_message := data.get("referenced_message"):
            ref_attachments = referenced_message.get("attachments", [])
            image_urls.extend(self._extract_attachments(ref_attachments))

        if not content and not image_urls:
            return

        # Guild 消息中检查是否需要响应（被 @mention 或回复）
        if not is_dm:
            if not self._should_respond_in_guild(data, content):
                return

        # 清理 mention 标签（Discord 的 <@id> 格式）
        clean_content = self._clean_mentions(content)

        # 构建 PlatformMessage
        user_id = str(author.get("id", ""))
        sender_name = author.get("username", "") or user_id
        message_id = str(data.get("id", ""))
        session_id = guild_id if guild_id else channel_id

        platform_msg = PlatformMessage(
            platform=self.platform_name,
            user_id=user_id,
            content=clean_content,
            session_id=session_id,
            message_id=message_id,
            group_id=guild_id or "",
            sender_name=sender_name,
            is_group=not is_dm,
            image_urls=image_urls,
            raw=data,
        )

        self._log(
            "info", "message_received",
            f"收到消息 [{'Guild' if not is_dm else 'DM'}] {sender_name}: {clean_content[:50]}",
            details={
                "user_id": user_id,
                "channel_id": channel_id,
                "guild_id": guild_id,
                "message_id": message_id,
                "is_dm": is_dm,
            },
        )

        # 路由到主 Agent
        response = await self._emit_message(platform_msg)
        if response and response.content:
            # target 格式: channel_id 或 guild_id:channel_id
            target = channel_id
            await self.send_message(response, target)

    def _should_respond_in_guild(self, data: dict[str, Any], content: str) -> bool:
        """判断 Guild 消息是否应该响应（被 @mention 或回复）。"""
        # 检查是否被回复
        if data.get("message_reference"):
            # 检查回复的消息是否是我们发的
            referenced_msg = data.get("referenced_message", {})
            if referenced_msg.get("author", {}).get("id") == self._self_user_id:
                return True

        # 检查是否被 @mention
        mentions = data.get("mentions", [])
        for mention in mentions:
            if str(mention.get("id", "")) == self._self_user_id:
                return True

        # 检查内容中是否包含 mention 标记
        if self._self_user_id and f"<@{self._self_user_id}>" in content:
            return True

        # 检查是否有命令前缀
        if self._prefix and content.startswith(self._prefix):
            return True

        return False

    @staticmethod
    def _clean_mentions(content: str) -> str:
        """清理 Discord mention 标签，保留可读名称。"""
        # 移除 <@USER_ID> 格式的 mention（实际名称无法从消息中获取，保留 ID）
        cleaned = re.sub(r"<@!?(\d+)>", "", content)
        # 移除 <#CHANNEL_ID> 格式的频道 mention
        cleaned = re.sub(r"<#(\d+)>", "", cleaned)
        # 移除 <@&ROLE_ID> 格式的角色 mention
        cleaned = re.sub(r"<@&(\d+)>", "", cleaned)
        # 清理多余空格
        cleaned = " ".join(cleaned.split())
        return cleaned.strip()

    @staticmethod
    def _extract_attachments(attachments: list[dict[str, Any]]) -> list[str]:
        """从附件列表中提取图片 URL。"""
        image_urls: list[str] = []
        for att in attachments:
            url = att.get("url", "")
            content_type = att.get("content_type", "")
            if url and (content_type.startswith("image/") or _is_image_url(url)):
                image_urls.append(url)
        return image_urls

    # ── 心跳 ──────────────────────────────────────────────────────────────────

    def _start_heartbeat(self) -> None:
        """启动心跳任务。"""
        self._stop_heartbeat()
        self._heartbeat_ack_received = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    def _stop_heartbeat(self) -> None:
        """停止心跳任务。"""
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            self._heartbeat_task = None

    async def _heartbeat_loop(self) -> None:
        """定期发送心跳。"""
        try:
            while self._running and self._ws:
                # 检查上一次心跳是否被确认
                if not self._heartbeat_ack_received:
                    self._log("warning", "heartbeat_timeout", "心跳未被确认，连接可能已断开")
                    if self._ws:
                        await self._ws.close(4000, "Heartbeat ACK timeout")
                    return

                self._heartbeat_ack_received = False
                await self._send_heartbeat()
                await asyncio.sleep(self._heartbeat_interval)
        except asyncio.CancelledError:
            return
        except Exception as e:
            self._log("error", "heartbeat_error", f"心跳异常: {e}")

    async def _send_heartbeat(self) -> None:
        """发送心跳包（opcode 1）。"""
        if not self._ws:
            return
        try:
            payload = {"op": OP_HEARTBEAT, "d": self._sequence}
            await self._ws.send(json.dumps(payload))
        except Exception as e:
            self._log("warning", "heartbeat_send_failed", f"心跳发送失败: {e}")

    # ── Identify / Resume ─────────────────────────────────────────────────────

    async def _send_identify(self) -> None:
        """发送 Identify 包（opcode 2）。"""
        payload = {
            "op": OP_IDENTIFY,
            "d": {
                "token": self._bot_token,
                "intents": self._intents,
                "properties": {
                    "os": "linux",
                    "browser": "LuomiNest",
                    "device": "LuomiNest",
                },
            },
        }
        await self._ws.send(json.dumps(payload))
        self._log("info", "identify_sent", "Identify 已发送")

    async def _send_resume(self) -> None:
        """发送 Resume 包（opcode 6）。"""
        payload = {
            "op": OP_RESUME,
            "d": {
                "token": self._bot_token,
                "session_id": self._session_id,
                "seq": self._sequence,
            },
        }
        await self._ws.send(json.dumps(payload))
        self._log("info", "resume_sent", f"Resume 已发送 (session={self._session_id}, seq={self._sequence})")

    # ── 发送消息（REST API）──────────────────────────────────────────────────

    async def send_message(self, response: PlatformResponse, target: str) -> bool:
        """通过 Discord REST API 发送消息。

        Args:
            response: 平台响应消息。
            target: 目标频道 ID。

        Returns:
            发送是否成功。
        """
        if not self._http_client:
            self._log("error", "no_http_client", "HTTP 客户端未初始化")
            return False

        channel_id = target.split(":")[-1] if ":" in target else target

        # 截断消息内容
        content = response.content or ""
        if content:
            content = self._truncator.truncate(
                content,
                max_length=MAX_MESSAGE_LENGTH,
                encoding="utf-8",
                mode=TruncateMode.CHARS,
            )

        # 构建请求体
        body: dict[str, Any] = {}

        if response.image_urls:
            # 有图片时使用 Embed
            embeds: list[dict[str, Any]] = []
            if content:
                body["content"] = content

            for url in response.image_urls[:10]:  # Discord 最多 10 个 embed
                embeds.append({
                    "type": "image",
                    "image": {"url": url},
                })
            body["embeds"] = embeds
        else:
            body["content"] = content or "..."
            body["embeds"] = []

        # 如果有回复目标
        if response.reply_to:
            body["message_reference"] = {"message_id": response.reply_to}

        # 发送请求（带重试）
        retry_config = RetryConfig(
            max_retries=3,
            base_delay=1.0,
            max_delay=30.0,
            jitter=0.5,
            retryable_exceptions=(httpx.HTTPStatusError, httpx.RequestError),
        )

        async def _do_send() -> httpx.Response:
            resp = await self._http_client.post(
                f"/channels/{channel_id}/messages",
                json=body,
            )

            # 处理速率限制
            if resp.status_code == 429:
                retry_after = float(resp.headers.get("Retry-After", "1"))
                self._log(
                    "warning", "rate_limited",
                    f"触发速率限制，等待 {retry_after}s",
                    details={"retry_after": retry_after, "channel_id": channel_id},
                )
                await asyncio.sleep(retry_after)
                resp = await self._http_client.post(
                    f"/channels/{channel_id}/messages",
                    json=body,
                )

            resp.raise_for_status()
            return resp

        try:
            result = await async_retry(_do_send, config=retry_config)
            msg_data = result.json() if hasattr(result, "json") else {}
            self._log(
                "info", "message_sent",
                f"消息已发送到频道 {channel_id}: {content[:50]}",
                details={
                    "channel_id": channel_id,
                    "message_id": str(msg_data.get("id", "")),
                },
            )
            return True
        except httpx.HTTPStatusError as e:
            self._log(
                "error", "send_failed",
                f"消息发送失败: HTTP {e.response.status_code}",
                details={"status_code": e.response.status_code, "channel_id": channel_id},
            )
            return False
        except Exception as e:
            self._log(
                "error", "send_failed",
                f"消息发送失败: {type(e).__name__}: {e}",
                details={"error": str(e), "channel_id": channel_id},
            )
            return False


def _is_image_url(url: str) -> bool:
    """判断 URL 是否指向图片文件。"""
    lower = url.lower().split("?")[0]
    return any(lower.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp"))
