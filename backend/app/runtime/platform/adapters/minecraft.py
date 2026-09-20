import asyncio
import json
import struct
import time
import uuid
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
                # 断开清理：连接可能已失效，属预期情况
                logger.debug("[MinecraftRCON] 关闭连接时异常（忽略）", exc_info=True)
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
        self._rcon_host: str = "127.0.0.1"
        self._rcon_port: int = 25575
        self._rcon_password: str = ""
        self._ws_enabled: bool = True
        self._ws_host: str = "0.0.0.0"
        self._ws_port: int = 8081
        self._game_host: str = "127.0.0.1"
        self._game_port: int = 56587
        self._bot_name: str = "主Agent"
        self._message_format: str = "tellraw"
        self._auto_spawn_bot: bool = True
        self._bot_process: Any = None

        # 具身 AI 模组遥测与状态存储
        self._player_states: dict[str, dict[str, Any]] = {}
        self._player_screenshots: dict[str, list[str]] = {}
        self._pending_action_responses: dict[str, asyncio.Future] = {}

    def initialize(self, config: dict[str, Any]) -> None:
        super().initialize(config)
        self._game_host = config.get("game_host", "127.0.0.1")
        self._game_port = int(config.get("game_port", 56587) or 56587)
        self._rcon_host = config.get("rcon_host", "127.0.0.1")
        self._rcon_port = int(config.get("rcon_port", 25575))
        self._rcon_password = config.get("rcon_password", "")
        ws_val = config.get("ws_enabled", True)
        if isinstance(ws_val, str):
            self._ws_enabled = ws_val.strip().lower() in ("true", "1", "yes")
        else:
            self._ws_enabled = bool(ws_val)

        self._ws_host = config.get("ws_host", "0.0.0.0")
        self._ws_port = int(config.get("ws_port", 8081))

        # 优先使用显式指定的 bot_name，若未指定则统一继承设置里的主 Agent 名称
        from app.runtime.platform.main_agent_config import load_luominest_main_agent_config
        main_agent_cfg = load_luominest_main_agent_config()
        configured_bot_name = config.get("bot_name")
        self._bot_name = str(configured_bot_name or main_agent_cfg.get("name") or "主Agent").strip()

        self._message_format = config.get("message_format", "tellraw")

        auto_bot_val = config.get("auto_spawn_bot", True)
        if isinstance(auto_bot_val, str):
            self._auto_spawn_bot = auto_bot_val.strip().lower() in ("true", "1", "yes")
        else:
            self._auto_spawn_bot = bool(auto_bot_val)

        ss_val = config.get("screenshot_enabled", True)
        if isinstance(ss_val, str):
            self._screenshot_enabled = ss_val.strip().lower() in ("true", "1", "yes")
        else:
            self._screenshot_enabled = bool(ss_val)

    async def start(self) -> None:
        self._running = True
        self._log("info", "connection_attempting", f"正在连接 Minecraft 服务器 {self._rcon_host}:{self._rcon_port}")

        if self._rcon_password:
            self._rcon = _LuomiNestRconClient(self._rcon_host, self._rcon_port, self._rcon_password)
            connected = await self._rcon.connect()
            if not connected:
                logger.warning("[Minecraft] RCON connection failed, will retry in background")
                self._log("warning", "connection_failed", "RCON 连接失败，将后台重试", details={
                    "host": self._rcon_host, "port": self._rcon_port,
                })
                self._reconnect_task = asyncio.create_task(self._reconnect_loop())
            else:
                self._log("success", "connection_established", f"RCON 已连接 {self._rcon_host}:{self._rcon_port}", details={
                    "host": self._rcon_host, "port": self._rcon_port,
                })
        else:
            logger.warning("[Minecraft] No RCON password configured, RCON disabled")
            self._log("warning", "config_missing", "未配置 RCON 密码，RCON 功能禁用")

        if self._ws_enabled:
            await self._start_ws_server()

        if self._auto_spawn_bot and self._game_port > 0:
            await self._launch_bot_agent()

        logger.success(f"[Minecraft] Adapter started (RCON={bool(self._rcon)}, WS={self._ws_enabled}, Bot={self._auto_spawn_bot and self._game_port > 0}, Screenshot={self._screenshot_enabled})")
        self._log("success", "instance_started", "Minecraft 适配器已启动", details={
            "rcon": bool(self._rcon), "ws": self._ws_enabled, "bot": bool(self._bot_process), "screenshot": self._screenshot_enabled,
        })

    async def _launch_bot_agent(self) -> None:
        """自动派驻 Mineflayer 虚拟玩家实体加入局域网单机世界。"""
        import shutil
        import subprocess
        from pathlib import Path

        node_exe = shutil.which("node")
        if not node_exe:
            logger.warning("[Minecraft] 未检测到 Node.js 环境，跳过实体伴侣玩家自动派遣")
            self._log("warning", "bot_launch_skipped", "未检测到 Node.js，跳过实体玩家自动派遣")
            return

        bot_script = Path(__file__).resolve().parents[4] / "scripts" / "mc_bot" / "bot_agent.js"
        if not bot_script.exists():
            logger.warning(f"[Minecraft] 未找到伴侣脚本: {bot_script}")
            return

        cmd = [
            node_exe,
            str(bot_script),
            "--host", self._game_host,
            "--port", str(self._game_port),
            "--ws-port", str(self._ws_port),
            "--name", self._bot_name,
        ]

        try:
            logger.info(f"[Minecraft] 正在自动派遣实体伴侣加入游戏: {self._game_host}:{self._game_port} (Bot={self._bot_name})")
            self._log("info", "bot_spawning", f"正在自动派遣实体伴侣 {self._bot_name} 加入游戏 {self._game_host}:{self._game_port}")
            self._bot_process = subprocess.Popen(
                cmd,
                cwd=str(bot_script.parent),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            import threading
            def _log_bot_pipe(pipe, is_err: bool = False):
                try:
                    for raw_line in iter(pipe.readline, b''):
                        line_str = raw_line.decode("utf-8", errors="replace").strip()
                        if line_str:
                            if is_err:
                                logger.warning(f"[MC-Bot] {line_str}")
                            else:
                                logger.info(f"[MC-Bot] {line_str}")
                except Exception:
                    pass
                finally:
                    try:
                        pipe.close()
                    except Exception:
                        pass

            threading.Thread(target=_log_bot_pipe, args=(self._bot_process.stdout, False), daemon=True).start()
            threading.Thread(target=_log_bot_pipe, args=(self._bot_process.stderr, True), daemon=True).start()

        except Exception as e:
            logger.error(f"[Minecraft] 派遣实体伴侣异常: {e}")
            self._log("error", "bot_spawn_failed", f"派遣伴侣异常: {e}")

    async def stop(self) -> None:
        self._running = False
        if self._bot_process:
            try:
                self._bot_process.terminate()
                self._bot_process.wait(timeout=2)
            except Exception:
                try:
                    self._bot_process.kill()
                except Exception:
                    pass
            self._bot_process = None
            self._log("info", "bot_stopped", "实体伴侣玩家已离开游戏")

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
                # 停机清理：连接可能已断开，属预期情况
                logger.debug("[Minecraft] 关闭 WS 连接时异常（忽略）", exc_info=True)
        self._ws_connections.clear()
        logger.info("[Minecraft] Adapter stopped")
        self._log("info", "instance_stopped", "Minecraft 适配器已停止")

    async def send_message(self, response: PlatformResponse, target: str) -> bool:
        text = response.content
        if not text:
            return False

        target_player = target if target and target != "broadcast" else None

        # 1. 优先尝试 RCON 发送（若配置了 RCON）
        if self._rcon:
            try:
                command = self._build_say_command(text, target_player)
                result = await self._rcon.send_command(command)
                logger.info(f"[Minecraft] Sent message via RCON: {text[:50]}")
                self._log("success", "message_sent", f"消息已通过 RCON 发送到游戏: {text[:80]}", details={
                    "target": target or "broadcast",
                    "format": self._message_format,
                    "content_length": len(text),
                })
                return True
            except Exception as e:
                logger.warning(f"[Minecraft] RCON send failed, falling back to WS mod: {e}")

        # 2. 回退通过 WebSocket 模组发送聊天消息
        if self._ws_connections:
            act_res = await self.dispatch_mod_action("say", {"message": text, "target": target_player or "all"})
            if act_res.get("success", False):
                self._log("success", "message_sent", f"消息已通过 WS 模组发送到游戏: {text[:80]}", details={
                    "target": target or "broadcast",
                    "content_length": len(text),
                })
                return True

        logger.warning("[Minecraft] Neither RCON nor WS available to send message")
        self._log("warning", "message_failed", "RCON 与 WS 模组均未连接，无法发送消息", details={
            "target": target, "content_preview": text[:80],
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
                    # 探测失败即触发下方重连流程，属预期信号
                    logger.debug("[Minecraft] RCON 存活探测失败，准备重连", exc_info=True)
                await self._rcon.disconnect()

            self._log("info", "connection_reconnecting", f"正在重连 RCON (第 {retry_count} 次)", details={
                "retry_count": retry_count,
                "host": self._rcon_host,
                "port": self._rcon_port,
            })
            logger.info(f"[Minecraft] Attempting RCON reconnect (attempt {retry_count})...")
            self._rcon = _LuomiNestRconClient(self._rcon_host, self._rcon_port, self._rcon_password)
            if await self._rcon.connect():
                logger.success("[Minecraft] RCON reconnected")
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
                        logger.warning("[Minecraft] Invalid WS JSON")
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
        # 1. 响应 Action 回执
        action_id = data.get("action_id") or data.get("echo")
        if action_id and action_id in self._pending_action_responses:
            fut = self._pending_action_responses.pop(action_id)
            if not fut.done():
                fut.set_result(data)
            return

        event_type = data.get("type", "")

        if event_type == "telemetry":
            await self._handle_telemetry_event(data)
        elif event_type == "chat":
            await self._handle_chat_event(data)
        elif event_type == "screenshot" and self._screenshot_enabled:
            await self._handle_screenshot_event(data)
        elif event_type == "ping":
            return
        else:
            self._log("info", "message_received", f"收到未处理的 WS 事件: {event_type}")

    async def _handle_telemetry_event(self, data: dict) -> None:
        """处理来自 Minecraft 模组的实体遥测感知数据包。"""
        player = data.get("player", data.get("sender", "Steve"))
        self._player_states[player] = data
        pos = data.get("position", [0, 0, 0])
        hp = data.get("health", 20)
        hunger = data.get("hunger", 20)
        self._log(
            "info", "telemetry_received",
            f"收到玩家 {player} 实时状态: 坐标={pos}, 生命={hp}/20, 饱食度={hunger}/20",
            details={"player": player, "position": pos, "health": hp, "hunger": hunger},
        )

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

        # 结合当前角色的实时物理环境/遥测数据构造上下文，使 LLM / DeepSeek 具备环境感知能力
        augmented_content = message
        state = self._player_states.get(player)
        if state:
            obs_parts = []
            pos = state.get("position")
            if pos:
                obs_parts.append(f"当前坐标: {pos}")
            hp = state.get("health")
            if hp is not None:
                obs_parts.append(f"生命值: {hp}/20")
            hunger = state.get("hunger")
            if hunger is not None:
                obs_parts.append(f"饱食度: {hunger}/20")
            looking = state.get("looking_at")
            if looking:
                obs_parts.append(f"注视方块/目标: {looking}")
            nearby = state.get("nearby_entities", [])
            if nearby:
                mobs = [e.get("type", "").replace("minecraft:", "") for e in nearby[:5]]
                obs_parts.append(f"附近生物: {', '.join(mobs)}")
            if obs_parts:
                augmented_content = f"【游戏实时环境: {'; '.join(obs_parts)}】\n{message}"

        # 附带最新的截图（若有缓存）
        image_urls = list(self._player_screenshots.get(player, []))

        platform_msg = PlatformMessage(
            platform=self.platform_name,
            user_id=player,
            content=augmented_content,
            session_id=player,
            message_id=data.get("message_id", ""),
            sender_name=player,
            is_group=False,
            image_urls=image_urls,
            raw=data,
        )

        response = await self._emit_message(platform_msg)
        if response and response.content:
            await self.send_message(response, player)

    async def _handle_screenshot_event(self, data: dict) -> None:
        """处理游戏客户端推送的截图（参考 mindcraft 的视觉理解方法）。

        游戏客户端通过 Mod/插件截图后，将图片以 base64 或 URL 形式通过 WS 推送。
        LuomiNest 收到后用 vision 模型识别，响应通过 RCON 或 WS 发送到游戏内聊天。
        """
        player = data.get("player", data.get("sender", ""))
        image_base64 = data.get("image_base64", "")
        image_url = data.get("image_url", "")
        prompt = data.get("prompt", "请分析这张游戏截图，描述你看到的场景、危险与重要资源")

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

        # 缓存最新截图
        self._player_screenshots[player] = image_urls

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
            message_id=data.get("message_id", f"ss_{int(time.time())}"),
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

    # ------------------------------------------------------------------
    # 具身 AI 模组指令分发与平台专属工具
    # ------------------------------------------------------------------

    async def dispatch_mod_action(
        self,
        action: str,
        params: dict[str, Any],
        player: str = "",
        timeout: float = 6.0,
    ) -> dict[str, Any]:
        """向连接的 Minecraft 模组客户端分发具身动作指令并等待反馈。"""
        action_id = f"mc_act_{uuid.uuid4().hex[:8]}"
        payload = {
            "type": "action",
            "action": action,
            "params": params,
            "player": player,
            "action_id": action_id,
        }
        raw_msg = json.dumps(payload)

        # 优先通过 WebSocket 分发给连接的游戏客户端 Mod
        dispatched = False
        loop = asyncio.get_running_loop()
        fut: asyncio.Future = loop.create_future()
        self._pending_action_responses[action_id] = fut

        for conn in list(self._ws_connections.values()):
            try:
                await conn.send(raw_msg)
                dispatched = True
            except Exception as e:
                logger.debug(f"[Minecraft] WS send error: {e}")

        if dispatched:
            try:
                res = await asyncio.wait_for(fut, timeout=timeout)
                return res if isinstance(res, dict) else {"success": True, "output": str(res)}
            except asyncio.TimeoutError:
                self._pending_action_responses.pop(action_id, None)
                return {"success": True, "output": f"指令 [{action}] 已成功下发至 Minecraft 模组客户端"}
            except Exception as e:
                self._pending_action_responses.pop(action_id, None)
                return {"success": False, "error": str(e)}

        # 若无 WS 客户端，尝试通过 RCON 命令执行回退
        if self._rcon:
            if action == "say":
                msg = params.get("message", "")
                await self.send_message(PlatformResponse(content=msg), player)
                return {"success": True, "output": f"已通过 RCON 发送: {msg}"}
            elif action == "execute_command":
                cmd = params.get("command", "")
                out = await self.execute_command(cmd)
                return {"success": True, "output": out or "命令已执行"}
            elif action == "navigate":
                # 支持 Baritone 模组的 RCON 命令回退: #goto x y z
                x = params.get("x", 0)
                y = params.get("y", 0)
                z = params.get("z", 0)
                cmd = f"#goto {x} {y} {z}"
                out = await self.execute_command(cmd)
                return {"success": True, "output": f"已通过 RCON 下发寻路指令: {cmd}"}

        return {"success": False, "error": "当前无连接的 Minecraft 模组客户端且 RCON 离线"}

    @property
    def available_tools(self) -> list[dict[str, Any]]:
        """声明 Minecraft 平台专用的具身操作工具（供 DeepSeek 及大模型调用）。"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "mc.navigate",
                    "description": "操控 Minecraft 角色自动寻路或移动到指定世界坐标 (x, y, z)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "x": {"type": "number", "description": "目标 X 坐标"},
                            "y": {"type": "number", "description": "目标 Y 坐标（高度）"},
                            "z": {"type": "number", "description": "目标 Z 坐标"},
                            "player": {"type": "string", "description": "目标操作玩家（选填，默认当前玩家）"},
                        },
                        "required": ["x", "y", "z"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "mc.mine_block",
                    "description": "操控角色挖掘指定坐标的方块（如挖矿、伐木、清除障碍）",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "x": {"type": "integer", "description": "方块 X 坐标"},
                            "y": {"type": "integer", "description": "方块 Y 坐标"},
                            "z": {"type": "integer", "description": "方块 Z 坐标"},
                            "player": {"type": "string", "description": "目标操作玩家"},
                        },
                        "required": ["x", "y", "z"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "mc.place_block",
                    "description": "操控角色在指定坐标放置方块（如搭建庇护所、垫脚）",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "x": {"type": "integer", "description": "放置位置 X 坐标"},
                            "y": {"type": "integer", "description": "放置位置 Y 坐标"},
                            "z": {"type": "integer", "description": "放置位置 Z 坐标"},
                            "block_name": {"type": "string", "description": "方块类型（如 minecraft:cobblestone, minecraft:torch）"},
                            "player": {"type": "string", "description": "目标操作玩家"},
                        },
                        "required": ["x", "y", "z", "block_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "mc.attack",
                    "description": "操控角色攻击指定的敌对生物、怪物或目标",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "target_name": {"type": "string", "description": "目标生物类型或实体标识（如 zombie, skeleton, spider）"},
                            "player": {"type": "string", "description": "目标操作玩家"},
                        },
                        "required": ["target_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "mc.use_item",
                    "description": "操控角色使用、食用或激活手中的物品（如吃食物回血、使用盾牌防御、喝药水）",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "slot_or_item": {"type": "string", "description": "物品名称或槽位（如 bread, golden_apple, shield, mainhand）"},
                            "player": {"type": "string", "description": "目标操作玩家"},
                        },
                        "required": ["slot_or_item"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "mc.craft",
                    "description": "操控角色合成指定物品或配方",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_name": {"type": "string", "description": "要合成的物品标识（如 minecraft:iron_pickaxe, minecraft:crafting_table）"},
                            "count": {"type": "integer", "description": "合成数量，默认 1"},
                            "player": {"type": "string", "description": "目标操作玩家"},
                        },
                        "required": ["item_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "mc.say",
                    "description": "在 Minecraft 游戏公屏或向指定玩家发送聊天消息",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message": {"type": "string", "description": "要发送的文本消息"},
                            "target_player": {"type": "string", "description": "指定接收私聊的玩家名（留空表示全服广播）"},
                        },
                        "required": ["message"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "mc.execute_command",
                    "description": "在游戏服务器中执行控制台/管理命令",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {"type": "string", "description": "Minecraft 控制台指令（如 time set day, weather clear）"},
                        },
                        "required": ["command"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "mc.get_player_state",
                    "description": "实时获取当前角色的坐标、生命值、饱食度、手持物、背包与周边生物信息",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "player": {"type": "string", "description": "查询的玩家名"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "mc.request_screenshot",
                    "description": "主动请求游戏客户端模组截取当前第一人称画面，供多模态视觉模型观察场景",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "player": {"type": "string", "description": "目标玩家名"},
                        },
                    },
                },
            },
        ]

    async def execute_platform_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """执行 Minecraft 具身平台工具调用。"""
        player = str(arguments.get("player", ""))

        if tool_name == "mc.navigate":
            x = arguments.get("x")
            y = arguments.get("y")
            z = arguments.get("z")
            res = await self.dispatch_mod_action("navigate", {"x": x, "y": y, "z": z}, player=player)
            return {"success": res.get("success", True), "output": res.get("output", f"已导航至 ({x}, {y}, {z})"), "error": res.get("error", "")}

        elif tool_name == "mc.mine_block":
            x, y, z = arguments.get("x"), arguments.get("y"), arguments.get("z")
            res = await self.dispatch_mod_action("mine_block", {"x": x, "y": y, "z": z}, player=player)
            return {"success": res.get("success", True), "output": res.get("output", f"已下达挖掘指令: ({x}, {y}, {z})"), "error": res.get("error", "")}

        elif tool_name == "mc.place_block":
            x, y, z = arguments.get("x"), arguments.get("y"), arguments.get("z")
            block = arguments.get("block_name", "")
            res = await self.dispatch_mod_action("place_block", {"x": x, "y": y, "z": z, "block_name": block}, player=player)
            return {"success": res.get("success", True), "output": res.get("output", f"已放置方块 {block} 于 ({x}, {y}, {z})"), "error": res.get("error", "")}

        elif tool_name == "mc.attack":
            target = arguments.get("target_name", "")
            res = await self.dispatch_mod_action("attack", {"target_name": target}, player=player)
            return {"success": res.get("success", True), "output": res.get("output", f"已下达攻击指令: {target}"), "error": res.get("error", "")}

        elif tool_name == "mc.use_item":
            item = arguments.get("slot_or_item", "")
            res = await self.dispatch_mod_action("use_item", {"slot_or_item": item}, player=player)
            return {"success": res.get("success", True), "output": res.get("output", f"已使用物品: {item}"), "error": res.get("error", "")}

        elif tool_name == "mc.craft":
            item = arguments.get("item_name", "")
            count = int(arguments.get("count", 1))
            res = await self.dispatch_mod_action("craft", {"item_name": item, "count": count}, player=player)
            return {"success": res.get("success", True), "output": res.get("output", f"已合成 {count} 个 {item}"), "error": res.get("error", "")}

        elif tool_name == "mc.say":
            msg = arguments.get("message", "")
            target_player = arguments.get("target_player", "")
            res = await self.dispatch_mod_action("say", {"message": msg, "target": target_player}, player=player)
            return {"success": res.get("success", True), "output": res.get("output", f"已发言: {msg}"), "error": res.get("error", "")}

        elif tool_name == "mc.execute_command":
            cmd = arguments.get("command", "")
            res = await self.dispatch_mod_action("execute_command", {"command": cmd}, player=player)
            return {"success": res.get("success", True), "output": res.get("output", "命令已执行"), "error": res.get("error", "")}

        elif tool_name == "mc.get_player_state":
            target = str(arguments.get("player") or player or "").strip()
            if not target and self._player_states:
                target = next(iter(self._player_states.keys()))

            state = self._player_states.get(target) if target else None

            # 如果目标玩家没有直接遥测，但有其他遥测（如伴侣 Bot 或其他玩家），检查周边实体或回退伴侣自身状态
            if not state and self._player_states:
                for p_name, p_state in self._player_states.items():
                    for entity in p_state.get("nearby_entities", []):
                        if entity.get("name") and target and target.lower() in entity.get("name").lower():
                            state = {
                                "player": target,
                                "seen_by": p_name,
                                "position": entity.get("position"),
                                "distance": entity.get("distance"),
                                "observer_state": p_state,
                            }
                            break
                    if state:
                        break

                if not state:
                    first_k = next(iter(self._player_states.keys()))
                    state = {
                        "note": f"未直接定位到玩家 {target}，已返回伴侣自身实时遥测",
                        "companion_state": self._player_states[first_k],
                    }

            if state:
                return {"success": True, "output": json.dumps(state, ensure_ascii=False), "error": ""}
            return {
                "success": True,
                "output": json.dumps({
                    "status": "online",
                    "player": target or "player",
                    "message": "已连接到游戏，但暂无位置遥测数据包",
                }, ensure_ascii=False),
                "error": "",
            }

        elif tool_name == "mc.request_screenshot":
            res = await self.dispatch_mod_action("request_screenshot", {}, player=player)
            return {"success": res.get("success", True), "output": res.get("output", "已向模组请求最新截图"), "error": res.get("error", "")}

        return await super().execute_platform_tool(tool_name, arguments)

