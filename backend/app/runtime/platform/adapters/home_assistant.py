"""HomeAssistant 适配器 - 接入 Home Assistant 智能家居平台。

通过 HA WebSocket API 监听事件接收用户消息，
通过 HA REST API 发送通知和调用服务。
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
from loguru import logger

from app.runtime.platform.base import (
    BasePlatformAdapter,
    PlatformMessage,
    PlatformResponse,
)
from app.runtime.platform.infrastructure.reconnect import (
    ReconnectMixin,
    ReconnectStrategy,
)
from app.runtime.platform.infrastructure.retry import RetryConfig, async_retry


class HomeAssistantAdapter(ReconnectMixin, BasePlatformAdapter):
    """Home Assistant 适配器。

    工作流程：
    1. 通过 WebSocket 连接到 HA，完成令牌认证
    2. 订阅 `luominest_message` 等自定义事件和 `call_service` 事件
    3. 收到事件后转换为 PlatformMessage，路由到主 Agent
    4. 主 Agent 响应后通过 HA REST API 的 notify 服务发回通知

    增强功能：
    - WebSocket 自动重连（指数退避）
    - REST API 请求自动重试
    - 心跳保活
    - 持久化通知
    - HA 服务调用
    """

    platform_name = "home_assistant"

    # 心跳间隔（秒）
    _HEARTBEAT_INTERVAL: float = 30.0
    # WebSocket 消息 ID 计数器
    _MSG_ID_START: int = 1

    # 配置元数据，供前端动态渲染配置表单
    config_metadata = {
        "ha_url": {
            "type": "string",
            "required": True,
            "label": "HA URL",
        },
        "ha_token": {
            "type": "string",
            "required": True,
            "label": "长期访问令牌",
            "sensitive": True,
        },
        "notify_service": {
            "type": "string",
            "required": False,
            "default": "notify",
            "label": "通知服务",
        },
        "listen_events": {
            "type": "string",
            "required": False,
            "default": "luominest_message",
            "label": "监听事件(逗号分隔)",
        },
    }

    def __init__(self) -> None:
        super().__init__()
        # HA 连接配置
        self._ha_url: str = ""
        self._ha_token: str = ""
        self._notify_service: str = "notify"
        self._listen_events: list[str] = ["luominest_message"]

        # WebSocket 相关
        self._ws: Any = None
        self._ws_task: asyncio.Task[None] | None = None
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._msg_id: int = self._MSG_ID_START
        self._authenticated: bool = False

        # HTTP 客户端
        self._http_client: httpx.AsyncClient | None = None

        # 重连策略：初始 5s，最大 120s
        self.set_reconnect_strategy(
            ReconnectStrategy(
                initial_delay=5.0,
                max_delay=120.0,
                multiplier=2.0,
                max_attempts=0,  # 无限重试
                jitter=2.0,
            )
        )

    # ------------------------------------------------------------------
    # 配置 & 生命周期
    # ------------------------------------------------------------------

    def initialize(self, config: dict[str, Any]) -> None:
        """解析配置并初始化资源。"""
        super().initialize(config)
        self._ha_url = config.get("ha_url", "").rstrip("/")
        self._ha_token = config.get("ha_token", "")
        self._notify_service = config.get("notify_service", "notify")

        raw_events = config.get("listen_events", "luominest_message")
        if isinstance(raw_events, str):
            self._listen_events = [e.strip() for e in raw_events.split(",") if e.strip()]
        elif isinstance(raw_events, list):
            self._listen_events = raw_events
        else:
            self._listen_events = ["luominest_message"]

        if not self._ha_url:
            raise ValueError("ha_url 为必填项")
        if not self._ha_token:
            raise ValueError("ha_token 为必填项")

    async def start(self) -> None:
        """启动适配器：创建 HTTP 客户端并连接 HA WebSocket。"""
        self._http_client = httpx.AsyncClient(
            base_url=self._ha_url,
            headers={
                "Authorization": f"Bearer {self._ha_token}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(30.0),
        )

        self._log(
            "info",
            "handshake_init",
            f"正在连接 Home Assistant: {self._ha_url}",
            details={"ha_url": self._ha_url, "listen_events": self._listen_events},
        )

        await self._connect_websocket()

    async def stop(self) -> None:
        """停止适配器：关闭 WebSocket、心跳和 HTTP 客户端。"""
        await self._cancel_reconnect()

        # 停止心跳
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None

        # 关闭 WebSocket
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

        # 取消 WebSocket 任务
        if self._ws_task and not self._ws_task.done():
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
            self._ws_task = None

        # 关闭 HTTP 客户端
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

        self._authenticated = False
        self._log("info", "connection_lost", "适配器已停止，所有连接已关闭")

    # ------------------------------------------------------------------
    # WebSocket 连接 & 认证
    # ------------------------------------------------------------------

    async def _connect_websocket(self) -> None:
        """建立到 HA 的 WebSocket 连接并完成认证。"""
        import websockets

        ws_url = self._build_ws_url()
        try:
            self._ws = await websockets.connect(ws_url)
            self._log("info", "ws_connected", f"WebSocket 已连接: {ws_url}")

            # 等待 auth_required 并发送认证
            await self._authenticate()

            # 订阅事件
            await self._subscribe_events()

            # 启动心跳
            self._start_heartbeat()

            # 更新状态
            self._authenticated = True
            self.update_status(self._status.__class__.RUNNING)
            self._log("success", "handshake_ok", "Home Assistant 连接已就绪")

            # 开始监听消息
            await self._listen_loop()

        except Exception as e:
            self._log("error", "ws_connect_failed", f"WebSocket 连接失败: {e}", details={"error": str(e)})
            self.record_error(str(e))
            raise

    def _build_ws_url(self) -> str:
        """将 HTTP URL 转换为 WebSocket URL。"""
        url = self._ha_url
        if url.startswith("https://"):
            url = "wss://" + url[len("https://"):]
        elif url.startswith("http://"):
            url = "ws://" + url[len("http://"):]
        elif not url.startswith("ws://") and not url.startswith("wss://"):
            url = "ws://" + url
        return f"{url}/api/websocket"

    async def _authenticate(self) -> None:
        """完成 HA WebSocket 认证流程。"""
        if self._ws is None:
            raise RuntimeError("WebSocket 未连接")

        # 接收 auth_required 消息
        raw = await self._ws.recv()
        msg = json.loads(raw)
        msg_type = msg.get("type")

        if msg_type == "auth_required":
            self._log("info", "auth_required", "收到认证请求，发送令牌")
            await self._ws.send(json.dumps({"type": "auth", "access_token": self._ha_token}))

            # 接收认证结果
            raw = await self._ws.recv()
            auth_result = json.loads(raw)
            if auth_result.get("type") != "auth_ok":
                error_msg = auth_result.get("message", "认证失败")
                self._log("error", "auth_failed", f"HA 认证失败: {error_msg}")
                raise RuntimeError(f"HA 认证失败: {error_msg}")

            self._log("success", "auth_ok", "HA 认证成功")
        elif msg_type == "auth_ok":
            # 某些 HA 版本可能直接认证成功
            self._log("success", "auth_ok", "HA 认证成功（无需 auth_required）")
        else:
            raise RuntimeError(f"意外的 WebSocket 消息类型: {msg_type}")

    async def _subscribe_events(self) -> None:
        """订阅 HA 事件。"""
        for event_type in self._listen_events:
            await self._send_ws_message({
                "type": "subscribe_events",
                "event_type": event_type,
            })
            self._log("info", "event_subscribed", f"已订阅事件: {event_type}")

        # 额外订阅 call_service 事件以监听服务调用
        if "call_service" not in self._listen_events:
            await self._send_ws_message({
                "type": "subscribe_events",
                "event_type": "call_service",
            })
            self._log("info", "event_subscribed", "已订阅事件: call_service")

    def _start_heartbeat(self) -> None:
        """启动心跳保活任务。"""
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def _heartbeat_loop(self) -> None:
        """定期发送 ping 以保持连接活跃。"""
        try:
            while self._ws is not None:
                await asyncio.sleep(self._HEARTBEAT_INTERVAL)
                if self._ws is not None:
                    try:
                        await self._send_ws_message({"type": "ping"})
                    except Exception as e:
                        self._log("warning", "heartbeat_failed", f"心跳发送失败: {e}")
                        break
        except asyncio.CancelledError:
            logger.debug("[home_assistant] 心跳任务已取消")

    async def _send_ws_message(self, payload: dict[str, Any]) -> None:
        """向 HA WebSocket 发送消息，自动分配消息 ID。"""
        if self._ws is None:
            raise RuntimeError("WebSocket 未连接")
        payload["id"] = self._msg_id
        self._msg_id += 1
        await self._ws.send(json.dumps(payload))

    # ------------------------------------------------------------------
    # 消息监听
    # ------------------------------------------------------------------

    async def _listen_loop(self) -> None:
        """WebSocket 消息监听主循环。"""
        try:
            while self._ws is not None:
                raw = await self._ws.recv()
                try:
                    msg = json.loads(raw)
                    await self._handle_ws_message(msg)
                except json.JSONDecodeError:
                    self._log("warning", "invalid_json", "收到无效的 JSON 数据")
                except Exception as e:
                    self._log("error", "event_error", f"事件处理失败: {e}", details={"error": str(e)})
        except Exception as e:
            self._log("warning", "ws_disconnected", f"WebSocket 连接断开: {e}", details={"error": str(e)})
            self._authenticated = False
            # 触发重连
            self._schedule_reconnect()

    async def _handle_ws_message(self, msg: dict[str, Any]) -> None:
        """处理 WebSocket 消息。"""
        msg_type = msg.get("type")

        if msg_type == "pong":
            # 心跳响应，忽略
            return

        if msg_type == "result":
            # 订阅确认或命令结果
            success = msg.get("success", False)
            if not success:
                self._log("warning", "ws_result_error", f"WebSocket 操作失败: {msg.get('error', {})}")
            return

        if msg_type == "event":
            event_data = msg.get("event", {})
            await self._handle_ha_event(event_data)
            return

        # 其他消息类型忽略

    async def _handle_ha_event(self, event: dict[str, Any]) -> None:
        """处理 HA 事件并转换为 PlatformMessage。"""
        event_type = event.get("event_type", "")
        data = event.get("data", {})

        # 处理 luominest_message 自定义事件
        if event_type in self._listen_events:
            platform_msg = self._convert_custom_event(event)
            if platform_msg:
                await self._process_message(platform_msg)
            return

        # 处理 call_service 事件（如 conversation 服务调用）
        if event_type == "call_service":
            domain = data.get("domain", "")
            service = data.get("service", "")
            if domain == "conversation" and service == "process":
                platform_msg = self._convert_conversation_event(event)
                if platform_msg:
                    await self._process_message(platform_msg)

    def _convert_custom_event(self, event: dict[str, Any]) -> PlatformMessage | None:
        """将 luominest_message 自定义事件转换为 PlatformMessage。"""
        data = event.get("data", {})
        user_id = str(data.get("user_id", data.get("sender", "unknown")))
        content = str(data.get("message", data.get("text", data.get("content", "")))).strip()
        sender_name = str(data.get("sender_name", data.get("name", user_id)))
        session_id = str(data.get("session_id", user_id))
        message_id = str(data.get("message_id", event.get("origin", {}).get("time_fired", "")))

        if not content:
            return None

        return PlatformMessage(
            platform=self.platform_name,
            user_id=user_id,
            content=content,
            session_id=session_id,
            message_id=message_id,
            sender_name=sender_name,
            is_group=False,
            raw=event,
        )

    def _convert_conversation_event(self, event: dict[str, Any]) -> PlatformMessage | None:
        """将 conversation.process 服务调用转换为 PlatformMessage。"""
        data = event.get("data", {})
        service_data = data.get("service_data", {})
        text = str(service_data.get("text", "")).strip()
        if not text:
            return None

        user_id = str(service_data.get("user_id", "ha_user"))
        return PlatformMessage(
            platform=self.platform_name,
            user_id=user_id,
            content=text,
            session_id=user_id,
            message_id=str(event.get("origin", {}).get("time_fired", "")),
            sender_name=user_id,
            is_group=False,
            raw=event,
        )

    async def _process_message(self, platform_msg: PlatformMessage) -> None:
        """处理转换后的平台消息：触发路由并发送回复。"""
        self._log(
            "info",
            "message_received",
            f"收到消息: {platform_msg.content[:50]}",
            details={
                "user_id": platform_msg.user_id,
                "sender_name": platform_msg.sender_name,
                "session_id": platform_msg.session_id,
            },
        )

        response = await self._emit_message(platform_msg)
        if response and response.content:
            target = f"notify:{platform_msg.user_id}"
            await self.send_message(response, target)

    # ------------------------------------------------------------------
    # 消息发送（REST API）
    # ------------------------------------------------------------------

    async def send_message(self, response: PlatformResponse, target: str) -> bool:
        """通过 HA REST API 发送通知。

        Args:
            response: 要发送的响应消息。
            target: 目标格式为 "notify:{service}" 或 "notify"（使用默认服务）。

        Returns:
            发送成功返回 True。
        """
        if not self._http_client:
            self._log("warning", "message_failed", "HTTP 客户端未初始化")
            return False

        service = self._extract_notify_service(target)

        # 构建通知数据
        notify_data: dict[str, Any] = {"message": response.content}
        if response.extra:
            # 支持 HA 通知的额外字段（title, data 等）
            if "title" in response.extra:
                notify_data["title"] = response.extra["title"]
            if "data" in response.extra:
                notify_data["data"] = response.extra["data"]

        try:
            result = await self._call_notify_service(service, notify_data)
            if result:
                self._log(
                    "info",
                    "message_sent",
                    f"通知已发送 -> {service}: {response.content[:50]}",
                    details={"service": service, "target": target},
                )
            return result
        except Exception as e:
            self._log(
                "error",
                "message_failed",
                f"通知发送失败: {e}",
                details={"error": str(e), "service": service},
            )
            return False

    @async_retry(config=RetryConfig(max_retries=3, base_delay=1.0, max_delay=10.0))
    async def _call_notify_service(self, service: str, data: dict[str, Any]) -> bool:
        """调用 HA 通知服务（带自动重试）。"""
        if not self._http_client:
            return False

        resp = await self._http_client.post(
            f"/api/services/notify/{service}",
            json=data,
        )
        resp.raise_for_status()
        return True

    def _extract_notify_service(self, target: str) -> str:
        """从 target 中提取通知服务名。"""
        if ":" in target:
            _, service = target.split(":", 1)
            return service or self._notify_service
        return self._notify_service

    async def send_persistent_notification(
        self,
        title: str,
        message: str,
        notification_id: str | None = None,
    ) -> bool:
        """发送持久化通知。

        Args:
            title: 通知标题。
            message: 通知内容。
            notification_id: 通知 ID（用于更新/删除）。

        Returns:
            发送成功返回 True。
        """
        if not self._http_client:
            return False

        data: dict[str, Any] = {"title": title, "message": message}
        if notification_id:
            data["notification_id"] = notification_id

        try:
            resp = await self._http_client.post(
                "/api/services/persistent_notification/create",
                json=data,
            )
            resp.raise_for_status()
            self._log(
                "info",
                "persistent_notification_sent",
                f"持久化通知已发送: {title}",
                details={"title": title, "notification_id": notification_id},
            )
            return True
        except Exception as e:
            self._log(
                "error",
                "persistent_notification_failed",
                f"持久化通知发送失败: {e}",
                details={"error": str(e)},
            )
            return False

    async def call_service(
        self,
        domain: str,
        service: str,
        service_data: dict[str, Any] | None = None,
        target: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """调用 HA 服务。

        Args:
            domain: 服务域（如 light, switch）。
            service: 服务名（如 turn_on, turn_off）。
            service_data: 服务参数。
            target: 目标实体。

        Returns:
            服务调用结果。
        """
        if not self._http_client:
            raise RuntimeError("HTTP 客户端未初始化")

        payload: dict[str, Any] = {}
        if service_data:
            payload.update(service_data)
        if target:
            payload["entity_id"] = target.get("entity_id", "")

        resp = await self._http_client.post(
            f"/api/services/{domain}/{service}",
            json=payload,
        )
        resp.raise_for_status()
        result = resp.json()
        self._log(
            "info",
            "service_called",
            f"已调用服务: {domain}.{service}",
            details={"domain": domain, "service": service, "target": target},
        )
        return result

    # ------------------------------------------------------------------
    # 重连逻辑（ReconnectMixin）
    # ------------------------------------------------------------------

    async def _do_reconnect(self) -> bool:
        """尝试重新连接 HA WebSocket。"""
        try:
            # 关闭旧连接
            if self._ws is not None:
                try:
                    await self._ws.close()
                except Exception:
                    pass
                self._ws = None

            # 停止旧心跳
            if self._heartbeat_task and not self._heartbeat_task.done():
                self._heartbeat_task.cancel()
                try:
                    await self._heartbeat_task
                except asyncio.CancelledError:
                    pass
                self._heartbeat_task = None

            import websockets
            ws_url = self._build_ws_url()
            self._ws = await websockets.connect(ws_url)

            # 重新认证
            await self._authenticate()

            # 重新订阅
            await self._subscribe_events()

            # 重启心跳
            self._start_heartbeat()

            self._authenticated = True
            return True

        except Exception as e:
            self._log("warning", "reconnect_failed", f"重连失败: {e}", details={"error": str(e)})
            return False

    def _on_reconnect_success(self) -> None:
        """重连成功回调。"""
        super()._on_reconnect_success()
        self.update_status(self._status.__class__.RUNNING)
        self._log("success", "reconnect_success", "HA WebSocket 重连成功")

        # 重连后需要重新启动监听循环
        if self._ws_task is None or self._ws_task.done():
            self._ws_task = asyncio.create_task(self._listen_loop())

    def _on_reconnect_failed(self, error: Exception | None = None) -> None:
        """重连失败回调。"""
        super()._on_reconnect_failed(error)
        if error:
            self.record_error(str(error))

    # ------------------------------------------------------------------
    # 内部工具方法
    # ------------------------------------------------------------------

    async def health_check(self) -> dict:
        """健康检查，扩展基类方法。"""
        base = await super().health_check()
        base["ha_url"] = self._ha_url
        base["authenticated"] = self._authenticated
        base["listen_events"] = self._listen_events

        # 尝试检查 HA 连通性
        if self._http_client:
            try:
                resp = await self._http_client.get("/api/")
                base["ha_reachable"] = resp.status_code == 200
            except Exception:
                base["ha_reachable"] = False
        else:
            base["ha_reachable"] = False

        return base
