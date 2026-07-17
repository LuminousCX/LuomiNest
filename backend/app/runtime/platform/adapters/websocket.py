"""WebSocket 平台适配器 - 作为客户端连接外部 WebSocket 服务器，实现双向实时通信。

协议说明：
- 入站消息: {"type": "message", "user_id": "...", "content": "...", "session_id": "...", ...}
- 出站消息: {"type": "response", "content": "...", "message_type": "text", ...}
- 保活:     依赖 websockets 库内置 WebSocket 协议级 ping/pong 自动保活
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from loguru import logger

from app.runtime.platform.base import (
    AdapterStatus,
    BasePlatformAdapter,
    PlatformMessage,
    PlatformResponse,
)


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------


class WebSocketAdapter(BasePlatformAdapter):
    """通用 WebSocket 客户端适配器。

    作为客户端连接到外部 WebSocket 服务器，支持：
    - ws:// 与 wss:// (TLS) 协议
    - 基于 JSON 的消息协议
    - 断线自动重连
    """

    platform_name = "websocket"

    # ---- 配置元数据（供前端 / 管理界面动态渲染表单） ----
    config_metadata: dict[str, dict[str, Any]] = {
        "ws_url": {
            "type": "string",
            "required": True,
            "label": "WebSocket URL",
        },
        "heartbeat_interval": {
            "type": "number",
            "required": False,
            "default": 30,
            "label": "心跳间隔(秒)",
        },
        "reconnect_delay": {
            "type": "number",
            "required": False,
            "default": 5,
            "label": "重连延迟(秒)",
        },
    }

    # ------------------------------------------------------------------
    # 初始化
    # ------------------------------------------------------------------
    def __init__(self) -> None:
        super().__init__()
        self._ws: Any = None  # websockets 连接对象
        self._ws_url: str = ""
        self._heartbeat_interval: float = 30.0
        self._reconnect_delay: float = 5.0

        self._receive_task: asyncio.Task[None] | None = None
        self._authenticated: bool = False

    def initialize(self, config: dict[str, Any]) -> None:
        """解析配置并初始化资源。"""
        super().initialize(config)

        self._ws_url = config.get("ws_url", "")
        if not self._ws_url:
            raise ValueError("WebSocket URL (ws_url) 为必填项")

        self._heartbeat_interval = float(config.get("heartbeat_interval", 30))
        self._reconnect_delay = float(config.get("reconnect_delay", 5))

        logger.info(
            f"[WebSocket] 适配器已初始化: url={self._ws_url}, "
            f"heartbeat={self._heartbeat_interval}s, "
            f"reconnect_delay={self._reconnect_delay}s"
        )

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    async def start(self) -> None:
        """启动适配器：建立 WebSocket 连接。"""
        await super().start()
        self.update_status(AdapterStatus.STARTING)
        self._log("info", "adapter_starting", "WebSocket 适配器启动中", {"url": self._ws_url})

        success = await self._connect()
        if not success:
            logger.warning("[WebSocket] 首次连接失败，后台重试中")
            asyncio.create_task(self._retry_connect())

    async def stop(self) -> None:
        """停止适配器：关闭连接和所有后台任务。"""
        self.update_status(AdapterStatus.STOPPING)
        self._log("info", "adapter_stopping", "WebSocket 适配器停止中")

        self._cancel_receive_task()

        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception as exc:
                logger.warning(f"[WebSocket] 关闭连接时发生异常，继续停止流程: {exc}")
            self._ws = None

        self._authenticated = False
        self.update_status(AdapterStatus.STOPPED)
        self._log("success", "adapter_stopped", "WebSocket 适配器已停止")

    # ------------------------------------------------------------------
    # 消息发送
    # ------------------------------------------------------------------
    async def send_message(self, response: PlatformResponse, target: str) -> bool:
        """向 WebSocket 服务器发送响应消息。

        Args:
            response: 平台响应对象。
            target: 目标标识（当前连接为单连接，target 可忽略）。

        Returns:
            是否发送成功。
        """
        payload: dict[str, Any] = {
            "type": "response",
            "content": response.content,
            "message_type": response.message_type,
            "image_urls": response.image_urls,
            "metadata": response.extra or {},
        }

        raw = json.dumps(payload, ensure_ascii=False)

        # 连接正常 → 直接发送
        if self._ws is not None and self._authenticated:
            try:
                await self._ws.send(raw)
                logger.debug(f"[WebSocket] 已发送响应: {response.content[:80]}")
                self._log("info", "message_sent", "发送响应消息", {"content_preview": response.content[:80]})
                return True
            except Exception as e:
                logger.warning(f"[WebSocket] 发送失败: {e}")
                self._log("warning", "send_failed", "消息发送失败", {"error": str(e)})

        # 连接不可用 → 直接丢弃
        logger.warning("[WebSocket] 连接不可用，消息已丢弃")
        return False

    # ------------------------------------------------------------------
    # 连接核心
    # ------------------------------------------------------------------
    async def _connect(self) -> bool:
        """建立 WebSocket 连接并完成鉴权。

        Returns:
            True 表示连接并鉴权成功。
        """
        import websockets

        try:
            logger.info(f"[WebSocket] 正在连接 {self._ws_url} ...")
            self._ws = await websockets.connect(
                self._ws_url,
                ping_interval=self._heartbeat_interval,
                ping_timeout=self._heartbeat_interval,
                close_timeout=5,
            )
            logger.success(f"[WebSocket] 已连接到 {self._ws_url}")
            self._log("success", "connection_established", "WebSocket 连接已建立", {"url": self._ws_url})

            self._authenticated = True

            # 启动后台任务
            self._start_receive_loop()

            self.update_status(AdapterStatus.RUNNING)
            self._log("success", "adapter_running", "WebSocket 适配器运行中")
            return True

        except Exception as e:
            logger.error(f"[WebSocket] 连接失败: {e}")
            self._log("error", "connection_failed", "WebSocket 连接失败", {"error": str(e)})
            self.record_error(str(e))
            return False

    # ------------------------------------------------------------------
    # 接收循环
    # ------------------------------------------------------------------
    def _start_receive_loop(self) -> None:
        """启动消息接收后台任务。"""
        self._cancel_receive_task()
        self._receive_task = asyncio.create_task(self._receive_loop())

    def _cancel_receive_task(self) -> None:
        if self._receive_task is not None and not self._receive_task.done():
            self._receive_task.cancel()
            self._receive_task = None

    async def _receive_loop(self) -> None:
        """持续接收 WebSocket 消息并分发处理，断线后自动重连。"""
        while self._status not in (AdapterStatus.STOPPING, AdapterStatus.STOPPED):
            try:
                while self._ws is not None:
                    raw = await self._ws.recv()
                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError:
                        logger.warning(f"[WebSocket] 收到无效 JSON: {raw[:200]}")
                        continue

                    await self._handle_message(data)

            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.warning(f"[WebSocket] 接收循环异常: {e}")
                self._log("error", "receive_error", "消息接收异常", {"error": str(e)})

            # 连接断开，尝试重连
            self._authenticated = False
            if self._status in (AdapterStatus.STOPPING, AdapterStatus.STOPPED):
                return

            self.update_status(AdapterStatus.RECONNECTING)
            self._log("warning", "connection_lost", "WebSocket 连接断开，准备重连")
            logger.info(f"[WebSocket] {self._reconnect_delay}s 后尝试重连...")
            await asyncio.sleep(self._reconnect_delay)

            success = await self._connect()
            if not success:
                logger.warning(f"[WebSocket] 重连失败，{self._reconnect_delay}s 后重试")

    async def _handle_message(self, data: dict[str, Any]) -> None:
        """处理收到的 JSON 消息。

        Args:
            data: 解析后的 JSON 字典。
        """
        msg_type = data.get("type", "")

        # 普通消息
        if msg_type == "message":
            platform_msg = self._build_platform_message(data)
            if platform_msg is None:
                return

            self._log("info", "message_received", "收到消息", {
                "user_id": platform_msg.user_id,
                "content_preview": platform_msg.content[:80],
            })

            response = await super()._emit_message(platform_msg)
            if response is not None:
                await self.send_message(
                    response,
                    platform_msg.session_id or platform_msg.user_id,
                )
            return

        logger.debug(f"[WebSocket] 忽略未知消息类型: {msg_type}")

    # ------------------------------------------------------------------
    # 消息构建
    # ------------------------------------------------------------------
    def _build_platform_message(self, data: dict[str, Any]) -> PlatformMessage | None:
        """将入站 JSON 消息转换为 PlatformMessage。

        Args:
            data: 入站 JSON 数据。

        Returns:
            PlatformMessage 或 None（消息无效时）。
        """
        user_id = data.get("user_id", "unknown")
        content = data.get("content", "").strip()
        image_urls = data.get("image_urls", [])

        if not content and not image_urls:
            logger.debug("[WebSocket] 忽略空消息")
            return None

        session_id = data.get("session_id", user_id)
        metadata = data.get("metadata", {})

        return PlatformMessage(
            platform=self.platform_name,
            user_id=user_id,
            content=content,
            session_id=session_id,
            message_id=metadata.get("message_id", ""),
            sender_name=metadata.get("sender_name", user_id),
            is_group=bool(metadata.get("is_group", False)),
            image_urls=image_urls,
            raw=data,
        )

    # ------------------------------------------------------------------
    # 辅助
    # ------------------------------------------------------------------
    async def _retry_connect(self) -> None:
        """后台重试连接，直到成功或被停止。"""
        while self._status not in (AdapterStatus.STOPPING, AdapterStatus.STOPPED):
            await asyncio.sleep(self._reconnect_delay)
            if self._status in (AdapterStatus.STOPPING, AdapterStatus.STOPPED):
                return
            success = await self._connect()
            if success:
                return
            logger.warning(f"[WebSocket] 连接失败，{self._reconnect_delay}s 后重试")

    async def _close_ws(self) -> None:
        """安全关闭当前 WebSocket 连接。"""
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception as e:
                logger.debug(f"[WebSocket] 关闭连接时发生异常（已忽略）: {e}")
            self._ws = None
        self._authenticated = False

    async def health_check(self) -> dict:
        """健康检查，包含 WebSocket 连接状态。"""
        base = await super().health_check()
        base.update({
            "ws_url": self._ws_url,
            "connected": self._ws is not None,
            "authenticated": self._authenticated,
        })
        return base
