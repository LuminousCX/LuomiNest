import asyncio
import json
from typing import Any

from app.runtime.platform.base import BasePlatformAdapter, PlatformMessage, PlatformResponse


class LuomiNestQQOneBotAdapter(BasePlatformAdapter):
    """QQ OneBot v11 适配器：通过反向 WebSocket 接收 NapCat/Lagrange/go-cqhttp 的连接。

    工作流程：
    1. LuomiNest 启动 WebSocket 服务器监听指定端口
    2. NapCat 等协议端连接到此服务器
    3. 收到 OneBot v11 事件后解析为 PlatformMessage，路由到主 Agent
    4. 主 Agent 响应后通过 send_group_msg / send_private_msg 发回
    """

    platform_name = "qq_onebot"

    def __init__(self) -> None:
        super().__init__()
        self._server: Any = None
        self._connections: dict[str, Any] = {}
        self._self_id: str = ""
        self._server_task: asyncio.Task | None = None

    def initialize(self, config: dict[str, Any]) -> None:
        super().initialize(config)
        self._ws_host = config.get("ws_host", "0.0.0.0")
        self._ws_port = int(config.get("ws_port", 8080))
        self._access_token = config.get("access_token", "")
        self._enable_group = config.get("enable_group", True)
        self._enable_private = config.get("enable_private", True)

    async def start(self) -> None:
        import websockets

        async def connection_handler(websocket: Any) -> None:
            conn_id = id(websocket)
            self._connections[conn_id] = websocket
            peer = websocket.remote_address if hasattr(websocket, "remote_address") else "unknown"
            self._log("success", "connection_established", f"客户端已连接: {peer}", details={"peer": str(peer)})

            try:
                async for raw in websocket:
                    try:
                        event = json.loads(raw)
                        await self._handle_onebot_event(event, websocket)
                    except json.JSONDecodeError:
                        self._log("warning", "error", "收到无效的 JSON 数据")
                    except Exception as e:
                        self._log("error", "error", f"事件处理失败: {e}", details={"error": str(e)})
            except Exception as e:
                self._log("warning", "connection_lost", f"连接已断开: {e}", details={"error": str(e)})
            finally:
                self._connections.pop(conn_id, None)
                self._log("info", "connection_lost", "客户端已断开连接")

        self._log("info", "handshake_init", f"启动反向 WebSocket 服务: {self._ws_host}:{self._ws_port}", details={"host": self._ws_host, "port": self._ws_port})
        self._server = await websockets.serve(connection_handler, self._ws_host, self._ws_port)
        self._log("success", "handshake_ok", f"WebSocket 服务已监听: {self._ws_host}:{self._ws_port}", details={"host": self._ws_host, "port": self._ws_port})

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        for conn in list(self._connections.values()):
            try:
                await conn.close()
            except Exception:
                pass
        self._connections.clear()
        self._log("info", "connection_lost", "适配器已停止，所有连接已关闭")

    async def send_message(self, response: PlatformResponse, target: str) -> bool:
        websocket = self._find_connection()
        if not websocket:
            self._log("warning", "message_failed", "无可用连接，无法发送消息", details={"target": target})
            return False

        target_type, target_id = self._parse_target(target)
        if not target_id:
            self._log("warning", "message_failed", f"无效的目标: {target}", details={"target": target})
            return False

        message_segments = self._build_message_segments(response)

        action = "send_group_msg" if target_type == "group" else "send_private_msg"
        payload = {
            "action": action,
            "params": {
                "message": message_segments,
                "auto_escape": False,
            },
            "echo": f"luominest_{id(response)}",
        }
        if target_type == "group":
            payload["params"]["group_id"] = int(target_id)
        else:
            payload["params"]["user_id"] = int(target_id)

        try:
            await websocket.send(json.dumps(payload))
            self._log(
                "info", "message_sent",
                f"消息已发送 [{action}] -> {target_id}: {response.content[:50]}",
                details={"action": action, "target_id": target_id, "target_type": target_type},
            )
            return True
        except Exception as e:
            self._log("error", "message_failed", f"消息发送失败: {e}", details={"error": str(e), "target": target})
            return False

    async def _handle_onebot_event(self, event: dict, websocket: Any) -> None:
        post_type = event.get("post_type")
        if post_type == "meta_event":
            sub_type = event.get("meta_event_type")
            if sub_type == "lifecycle":
                self._self_id = str(event.get("self_id", ""))
                self._log("info", "handshake_ok", f"生命周期事件，self_id={self._self_id}", details={"self_id": self._self_id})
            return

        if post_type != "message":
            return

        message_type = event.get("message_type")
        if message_type == "group" and not self._enable_group:
            return
        if message_type == "private" and not self._enable_private:
            return

        platform_msg = self._convert_onebot_to_platform(event)
        if not platform_msg:
            return

        self._log(
            "info", "message_received",
            f"收到消息 [{platform_msg.platform}] {'群聊' if platform_msg.is_group else '私聊'}: {platform_msg.content[:50]}",
            details={
                "user_id": platform_msg.user_id,
                "sender_name": platform_msg.sender_name,
                "is_group": platform_msg.is_group,
                "group_id": platform_msg.group_id,
                "message_id": platform_msg.message_id,
            },
        )

        if not self._should_respond(event, platform_msg):
            return

        response = await self._emit_message(platform_msg)
        if response and response.content:
            target = self._build_target(event)
            await self.send_message(response, target)

    def _convert_onebot_to_platform(self, event: dict) -> PlatformMessage | None:
        message_type = event.get("message_type", "")
        user_id = str(event.get("user_id", ""))
        group_id = str(event.get("group_id", ""))
        message_id = str(event.get("message_id", ""))
        sender = event.get("sender", {})
        sender_name = sender.get("nickname", "") or sender.get("card", "") or user_id

        is_group = message_type == "group"
        session_id = group_id if is_group else user_id

        text_parts: list[str] = []
        image_urls: list[str] = []

        for seg in event.get("message", []):
            if not isinstance(seg, dict):
                continue
            seg_type = seg.get("type", "")
            seg_data = seg.get("data", {})

            if seg_type == "text":
                text_parts.append(seg_data.get("text", ""))
            elif seg_type == "image":
                url = seg_data.get("url") or seg_data.get("file", "")
                if url and url.startswith("http"):
                    image_urls.append(url)
            elif seg_type == "at":
                qq = seg_data.get("qq", "")
                if qq and qq != self._self_id:
                    text_parts.append(f"@{qq}")
            elif seg_type == "reply":
                pass
            elif seg_type == "face":
                text_parts.append("[表情]")

        content = "".join(text_parts).strip()
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
            raw=event,
        )

    def _should_respond(self, event: dict, msg: PlatformMessage) -> bool:
        if not msg.is_group:
            return True

        for seg in event.get("message", []):
            if isinstance(seg, dict) and seg.get("type") == "at":
                qq = seg.get("data", {}).get("qq", "")
                if qq == self._self_id or qq == "all":
                    return True
        return False

    @staticmethod
    def _build_target(event: dict) -> str:
        if event.get("message_type") == "group":
            return f"group:{event.get('group_id')}"
        return f"private:{event.get('user_id')}"

    @staticmethod
    def _parse_target(target: str) -> tuple[str, str]:
        if ":" in target:
            t_type, t_id = target.split(":", 1)
            return t_type, t_id
        return "private", target

    def _find_connection(self) -> Any:
        for conn in self._connections.values():
            return conn
        return None

    @staticmethod
    def _build_message_segments(response: PlatformResponse) -> list[dict]:
        segments: list[dict] = []
        if response.content:
            segments.append({"type": "text", "data": {"text": response.content}})
        for url in response.image_urls:
            segments.append({"type": "image", "data": {"url": url}})
        if not segments:
            segments.append({"type": "text", "data": {"text": "[空消息]"}})
        return segments
