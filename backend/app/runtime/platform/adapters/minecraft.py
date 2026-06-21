import asyncio
import json
import struct
from typing import Any
from loguru import logger

from app.runtime.platform.base import BasePlatformAdapter, PlatformMessage, PlatformResponse


class _LuomiNestRconClient:
    """Minecraft RCON 协议客户端（纯 Python 实现，无外部依赖）。

    RCON 数据包结构：
    - 4 字节：长度（后续数据长度，不含自身）
    - 4 字节：请求 ID
    - 4 字节：类型（3=登录, 2=执行命令, 0=响应）
    - 载荷：ASCII 字符串
    - 2 字节：两个 0x00 结尾
    """

    def __init__(self, host: str, port: int, password: str) -> None:
        self._host = host
        self._port = port
        self._password = password
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._request_id = 100

    async def connect(self) -> bool:
        try:
            self._reader, self._writer = await asyncio.open_connection(self._host, self._port)
            if await self._login():
                logger.success(f"[MinecraftRCON] Connected to {self._host}:{self._port}")
                return True
            logger.error(f"[MinecraftRCON] Login failed (wrong password)")
            await self.disconnect()
            return False
        except Exception as e:
            logger.error(f"[MinecraftRCON] Connection failed: {e}")
            return False

    async def disconnect(self) -> None:
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
        self._reader = None
        self._writer = None

    async def _login(self) -> bool:
        resp_id = await self._send_packet(3, self._password)
        return resp_id != -1 and resp_id is not None

    async def send_command(self, command: str) -> str:
        resp_id, body = await self._send_packet_with_body(2, command)
        if resp_id == -1:
            return ""
        return body

    async def _send_packet(self, packet_type: int, payload: str) -> int:
        resp_id, _ = await self._send_packet_with_body(packet_type, payload)
        return resp_id

    async def _send_packet_with_body(self, packet_type: int, payload: str) -> tuple[int, str]:
        if not self._writer or not self._reader:
            return -1, ""

        self._request_id += 1
        req_id = self._request_id

        payload_bytes = payload.encode("utf-8", errors="replace")
        length = 4 + 4 + len(payload_bytes) + 2

        header = struct.pack("<iii", length, req_id, packet_type)
        packet = header + payload_bytes + b"\x00\x00"

        try:
            self._writer.write(packet)
            await self._writer.drain()
        except Exception as e:
            logger.error(f"[MinecraftRCON] Send failed: {e}")
            return -1, ""

        return await self._read_response(req_id)

    async def _read_response(self, expected_id: int) -> tuple[int, str]:
        try:
            length_data = await self._reader.readexactly(4)
            length = struct.unpack("<i", length_data)[0]
            if length < 10 or length > 4096:
                return -1, ""

            data = await self._reader.readexactly(length)
            resp_id = struct.unpack("<i", data[0:4])[0]
            _pkt_type = struct.unpack("<i", data[4:8])[0]
            body = data[8:-2].decode("utf-8", errors="replace")

            if resp_id == -1:
                return -1, ""
            return resp_id, body
        except asyncio.IncompleteReadError:
            return -1, ""
        except Exception as e:
            logger.error(f"[MinecraftRCON] Read failed: {e}")
            return -1, ""


class LuomiNestMinecraftAdapter(BasePlatformAdapter):
    """Minecraft 适配器：通过 RCON 协议与 MC 服务器交互，可选 WebSocket 接收聊天事件和截图。

    工作模式：
    1. RCON 模式（默认）：通过 RCON 发送 say/tellraw 命令，主 Agent 可主动在游戏内说话
    2. WebSocket 模式（可选）：启动 WS 服务器接收服务端插件推送的玩家聊天事件和截图，
       实现被动响应玩家消息和游戏画面识别

    截图能力（参考 mindcraft 项目方法）：
    - 游戏客户端通过 Mod/插件定时截图或按需截图
    - 截图通过 WS 推送给 LuomiNest（base64 或 URL 格式）
    - 主 Agent 用 vision 模型识别截图内容
    - 响应通过 RCON 发送到游戏内聊天

    配置项：
    - rcon_host: RCON 主机地址
    - rcon_port: RCON 端口（默认 25575）
    - rcon_password: RCON 密码
    - ws_enabled: 是否启用 WebSocket 聊天事件接收
    - ws_host: WS 服务器监听地址
    - ws_port: WS 服务器监听端口
    - bot_name: 机器人在游戏内的显示名称
    - screenshot_enabled: 是否启用截图识别
    - screenshot_interval: 自动截图间隔（秒，0 表示禁用自动截图）
    """

    platform_name = "minecraft"

    def __init__(self) -> None:
        super().__init__()
        self._rcon: _LuomiNestRconClient | None = None
        self._ws_server: Any = None
        self._ws_connections: dict[int, Any] = {}
        self._reconnect_task: asyncio.Task | None = None
        self._running = False
        self._screenshot_enabled = False

    def initialize(self, config: dict[str, Any]) -> None:
        super().initialize(config)
        self._rcon_host = config.get("rcon_host", "127.0.0.1")
        self._rcon_port = int(config.get("rcon_port", 25575))
        self._rcon_password = config.get("rcon_password", "")
        self._ws_enabled = bool(config.get("ws_enabled", False))
        self._ws_host = config.get("ws_host", "0.0.0.0")
        self._ws_port = int(config.get("ws_port", 8081))
        self._bot_name = config.get("bot_name", "LuomiNest")
        self._message_format = config.get("message_format", "tellraw")
        self._screenshot_enabled = bool(config.get("screenshot_enabled", True))

    async def start(self) -> None:
        self._running = True
        self._log("info", "connection_attempting", f"正在连接 Minecraft 服务器 {self._rcon_host}:{self._rcon_port}")

        if self._rcon_password:
            self._rcon = _LuomiNestRconClient(self._rcon_host, self._rcon_port, self._rcon_password)
            connected = await self._rcon.connect()
            if not connected:
                logger.warning(f"[Minecraft] RCON connection failed, will retry in background")
                self._log("warning", "connection_failed", f"RCON 连接失败，将后台重试", details={
                    "host": self._rcon_host, "port": self._rcon_port,
                })
                self._reconnect_task = asyncio.create_task(self._reconnect_loop())
            else:
                self._log("success", "connection_established", f"RCON 已连接 {self._rcon_host}:{self._rcon_port}", details={
                    "host": self._rcon_host, "port": self._rcon_port,
                })
        else:
            logger.warning(f"[Minecraft] No RCON password configured, RCON disabled")
            self._log("warning", "config_missing", "未配置 RCON 密码，RCON 功能禁用")

        if self._ws_enabled:
            await self._start_ws_server()

        logger.success(f"[Minecraft] Adapter started (RCON={bool(self._rcon)}, WS={self._ws_enabled}, Screenshot={self._screenshot_enabled})")
        self._log("success", "instance_started", f"Minecraft 适配器已启动", details={
            "rcon": bool(self._rcon), "ws": self._ws_enabled, "screenshot": self._screenshot_enabled,
        })

    async def stop(self) -> None:
        self._running = False
        if self._reconnect_task:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
            self._reconnect_task = None

        if self._rcon:
            await self._rcon.disconnect()
            self._rcon = None
            self._log("info", "connection_lost", "RCON 连接已关闭")

        if self._ws_server:
            self._ws_server.close()
            await self._ws_server.wait_closed()
            self._ws_server = None

        for conn in list(self._ws_connections.values()):
            try:
                await conn.close()
            except Exception:
                pass
        self._ws_connections.clear()
        logger.info(f"[Minecraft] Adapter stopped")
        self._log("info", "instance_stopped", "Minecraft 适配器已停止")

    async def send_message(self, response: PlatformResponse, target: str) -> bool:
        if not self._rcon:
            logger.warning(f"[Minecraft] RCON not connected, cannot send message")
            self._log("warning", "message_failed", "RCON 未连接，无法发送消息", details={
                "target": target, "content_preview": response.content[:80],
            })
            return False

        text = response.content
        if not text:
            return False

        target_player = target if target and target != "broadcast" else None

        try:
            command = self._build_say_command(text, target_player)
            result = await self._rcon.send_command(command)
            logger.info(f"[Minecraft] Sent message via {self._message_format}: {text[:50]}")
            self._log("success", "message_sent", f"消息已发送到游戏: {text[:80]}", details={
                "target": target or "broadcast",
                "format": self._message_format,
                "content_length": len(text),
            })
            return True
        except Exception as e:
            logger.error(f"[Minecraft] Failed to send message: {e}")
            self._log("error", "message_failed", f"消息发送失败: {e}", details={
                "target": target or "broadcast",
                "error": str(e),
                "error_type": type(e).__name__,
            })
            return False

    async def _reconnect_loop(self) -> None:
        retry_count = 0
        while self._running:
            await asyncio.sleep(10)
            if not self._running:
                break
            retry_count += 1
            if self._rcon:
                try:
                    result = await self._rcon.send_command("list")
                    if result or result == "":
                        continue
                except Exception:
                    pass
                await self._rcon.disconnect()

            self._log("info", "connection_reconnecting", f"正在重连 RCON (第 {retry_count} 次)", details={
                "retry_count": retry_count,
                "host": self._rcon_host,
                "port": self._rcon_port,
            })
            logger.info(f"[Minecraft] Attempting RCON reconnect (attempt {retry_count})...")
            self._rcon = _LuomiNestRconClient(self._rcon_host, self._rcon_port, self._rcon_password)
            if await self._rcon.connect():
                logger.success(f"[Minecraft] RCON reconnected")
                self._log("success", "connection_established", f"RCON 重连成功 (第 {retry_count} 次)", details={
                    "retry_count": retry_count,
                })
                retry_count = 0

    async def _start_ws_server(self) -> None:
        import websockets

        async def ws_handler(websocket: Any) -> None:
            conn_id = id(websocket)
            self._ws_connections[conn_id] = websocket
            peer = websocket.remote_address if hasattr(websocket, "remote_address") else "unknown"
            logger.info(f"[Minecraft] WS plugin connected from {peer}")
            self._log("success", "connection_established", f"WS 插件已连接: {peer}", details={
                "peer": str(peer), "conn_id": conn_id,
            })

            try:
                async for raw in websocket:
                    try:
                        data = json.loads(raw)
                        await self._handle_ws_event(data)
                    except json.JSONDecodeError:
                        logger.warning(f"[Minecraft] Invalid WS JSON")
                        self._log("warning", "message_failed", "WS 收到无效 JSON 数据")
                    except Exception as e:
                        logger.error(f"[Minecraft] WS event handling failed: {e}")
                        self._log("error", "message_failed", f"WS 事件处理失败: {e}", details={
                            "error": str(e), "error_type": type(e).__name__,
                        })
            except Exception as e:
                logger.warning(f"[Minecraft] WS connection closed: {e}")
                self._log("warning", "connection_lost", f"WS 连接已关闭: {e}", details={
                    "peer": str(peer), "error": str(e),
                })
            finally:
                self._ws_connections.pop(conn_id, None)

        self._ws_server = await websockets.serve(ws_handler, self._ws_host, self._ws_port)
        logger.success(f"[Minecraft] WS server listening on {self._ws_host}:{self._ws_port} for chat events and screenshots")
        self._log("success", "handshake_ok", f"WS 服务器已启动: {self._ws_host}:{self._ws_port}", details={
            "host": self._ws_host, "port": self._ws_port,
        })

    async def _handle_ws_event(self, data: dict) -> None:
        event_type = data.get("type", "")

        if event_type == "chat":
            await self._handle_chat_event(data)
        elif event_type == "screenshot" and self._screenshot_enabled:
            await self._handle_screenshot_event(data)
        elif event_type == "ping":
            return
        else:
            self._log("info", "message_received", f"收到未处理的 WS 事件: {event_type}")

    async def _handle_chat_event(self, data: dict) -> None:
        player = data.get("player", data.get("sender", ""))
        message = data.get("message", data.get("content", ""))
        if not player or not message:
            return

        self._log("info", "message_received", f"收到游戏消息: {player}: {message[:80]}", details={
            "player": player,
            "content_length": len(message),
            "message_id": data.get("message_id", ""),
        })

        platform_msg = PlatformMessage(
            platform=self.platform_name,
            user_id=player,
            content=message,
            session_id=player,
            message_id=data.get("message_id", ""),
            sender_name=player,
            is_group=False,
            raw=data,
        )

        response = await self._emit_message(platform_msg)
        if response and response.content:
            await self.send_message(response, player)

    async def _handle_screenshot_event(self, data: dict) -> None:
        """处理游戏客户端推送的截图（参考 mindcraft 的视觉理解方法）。

        游戏客户端通过 Mod/插件截图后，将图片以 base64 或 URL 形式通过 WS 推送。
        LuomiNest 收到后用 vision 模型识别，响应通过 RCON 发送到游戏内聊天。

        数据格式：
        {
            "type": "screenshot",
            "player": "玩家名",
            "image_base64": "base64编码的图片数据（不含data:前缀）",
            "image_url": "图片URL（与image_base64二选一）",
            "prompt": "可选的识别提示词",
            "timestamp": "时间戳"
        }
        """
        player = data.get("player", data.get("sender", ""))
        image_base64 = data.get("image_base64", "")
        image_url = data.get("image_url", "")
        prompt = data.get("prompt", "请分析这张游戏截图，描述你看到的场景和重要元素")

        if not player:
            self._log("warning", "message_failed", "截图事件缺少玩家信息", details={"data": data})
            return

        image_urls: list[str] = []
        if image_base64:
            if not image_base64.startswith("data:"):
                image_urls.append(f"data:image/jpeg;base64,{image_base64}")
            else:
                image_urls.append(image_base64)
        elif image_url:
            image_urls.append(image_url)
        else:
            self._log("warning", "message_failed", "截图事件缺少图片数据", details={"player": player})
            return

        self._log("info", "message_received", f"收到游戏截图: 来自 {player}", details={
            "player": player,
            "image_count": len(image_urls),
            "image_source": "base64" if image_base64 else "url",
            "prompt": prompt[:100],
        })

        platform_msg = PlatformMessage(
            platform=self.platform_name,
            user_id=player,
            content=prompt,
            session_id=player,
            message_id=data.get("message_id", f"ss_{int(__import__('time').time())}"),
            sender_name=player,
            is_group=False,
            image_urls=image_urls,
            raw=data,
        )

        response = await self._emit_message(platform_msg)
        if response and response.content:
            await self.send_message(response, player)

    def _build_say_command(self, text: str, target_player: str | None) -> str:
        escaped = text.replace('\\', '\\\\').replace('"', '\\"')

        if self._message_format == "tellraw":
            display_name = self._bot_name.replace('"', '')
            if target_player:
                return f'tellraw {target_player} {{"text":"[{display_name}] {escaped}","color":"aqua"}}'
            return f'tellraw @a {{"text":"[{display_name}] {escaped}","color":"aqua"}}'

        if self._message_format == "tell":
            if target_player:
                return f'tell {target_player} [{self._bot_name}] {escaped}'
            return f'say [{self._bot_name}] {escaped}'

        if target_player:
            return f'tell {target_player} [{self._bot_name}] {escaped}'
        return f'say [{self._bot_name}] {escaped}'

    async def execute_command(self, command: str) -> str:
        """执行任意 RCON 命令（供高级用途调用）。"""
        if not self._rcon:
            return ""
        return await self._rcon.send_command(command)
