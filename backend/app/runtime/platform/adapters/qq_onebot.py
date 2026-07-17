import asyncio
import contextlib
import json
import random
from typing import Any

from loguru import logger

from app.runtime.platform.base import BasePlatformAdapter, PlatformMessage, PlatformResponse


class LuomiNestQQOneBotAdapter(BasePlatformAdapter):
    """QQ OneBot v11 适配器：通过反向 WebSocket 接收 NapCat/Lagrange/go-cqhttp 的连接。

    工作流程：
    1. LuomiNest 启动 WebSocket 服务器监听指定端口
    2. NapCat 等协议端连接到此服务器
    3. 收到 OneBot v11 事件后解析为 PlatformMessage，路由到主 Agent
    4. 主 Agent 响应后通过 send_group_msg / send_private_msg 发回

    增强功能：
    - 自动重连：服务器意外崩溃时使用指数退避策略自动重启（初始 5s，最大 60s）
    - 消息发送队列：发送失败的消息进入队列，后台任务定期重试
    - 回复引用支持：提取 OneBot v11 reply 消息段，记录被回复消息 ID
    """

    platform_name = "qq_onebot"

    # 消息队列默认最大长度
    _QUEUE_MAX_SIZE: int = 100
    # 队列重试间隔（秒）
    _QUEUE_RETRY_INTERVAL: float = 5.0
    # 重连策略
    _RECONNECT_INITIAL_DELAY: float = 5.0
    _RECONNECT_MAX_DELAY: float = 60.0
    _RECONNECT_MULTIPLIER: float = 2.0
    _RECONNECT_JITTER: float = 1.0

    def __init__(self) -> None:
        super().__init__()
        self._server: Any = None
        self._connections: dict[str, Any] = {}
        self._self_id: str = ""
        self._server_task: asyncio.Task | None = None
        # 消息发送队列
        self._send_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(
            maxsize=self._QUEUE_MAX_SIZE,
        )
        self._queue_worker_task: asyncio.Task | None = None
        # 每个用户的回复引用映射 {user_id: reply_to_message_id}
        self._pending_replies: dict[str, str] = {}
        # 重连状态
        self._reconnect_task: asyncio.Task | None = None
        self._reconnect_attempt: int = 0
        self._is_stopping: bool = False

    def initialize(self, config: dict[str, Any]) -> None:
        super().initialize(config)
        self._ws_host = config.get("ws_host", "0.0.0.0")
        self._ws_port = int(config.get("ws_port", 8080))
        self._access_token = config.get("access_token", "")
        self._enable_group = config.get("enable_group", True)
        self._enable_private = config.get("enable_private", True)

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    async def start(self) -> None:
        await self._start_server()
        # 启动消息队列后台重试任务
        self._queue_worker_task = asyncio.create_task(self._queue_retry_worker())
        # 启动服务器健康检查任务
        self._server_task = asyncio.create_task(self._server_watcher())

    async def _start_server(self) -> None:
        """启动 WebSocket 服务器（初始启动和重连共用）。"""
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

    async def _do_reconnect(self) -> bool:
        """尝试重新建立 WebSocket 服务器连接。

        Returns:
            True 表示重连成功，False 表示失败。
        """
        try:
            # 清理旧服务器资源
            if self._server:
                self._server.close()
                await self._server.wait_closed()
                self._server = None
            await self._start_server()
            return True
        except Exception as e:
            self._log(
                "warning", "reconnect_failed",
                f"重连失败: {e}",
                details={"attempt": self._reconnect_attempt, "error": str(e)},
            )
            return False

    async def _reconnect_loop(self) -> None:
        """指数退避重连循环。"""
        delay = self._RECONNECT_INITIAL_DELAY
        while not self._is_stopping:
            self._reconnect_attempt += 1
            jitter = random.uniform(0, self._RECONNECT_JITTER)
            actual_delay = min(delay, self._RECONNECT_MAX_DELAY) + jitter

            self._log(
                "info", "reconnect_wait",
                f"第 {self._reconnect_attempt} 次重连，等待 {actual_delay:.1f}s...",
                details={"attempt": self._reconnect_attempt, "delay": round(actual_delay, 2)},
            )
            await asyncio.sleep(actual_delay)

            if self._is_stopping:
                break

            success = await self._do_reconnect()
            if success:
                self._log(
                    "success", "reconnect_success",
                    f"第 {self._reconnect_attempt} 次重连成功",
                    details={"attempt": self._reconnect_attempt},
                )
                self._reconnect_attempt = 0
                # 重启服务器健康检查
                self._server_task = asyncio.create_task(self._server_watcher())
                return

            delay = min(delay * self._RECONNECT_MULTIPLIER, self._RECONNECT_MAX_DELAY)

    def _schedule_reconnect(self) -> None:
        """调度重连任务。"""
        if self._is_stopping:
            return
        if self._reconnect_task is not None and not self._reconnect_task.done():
            return
        self._reconnect_task = asyncio.create_task(self._reconnect_loop())

    async def _server_watcher(self) -> None:
        """定期检测 WebSocket 服务器是否仍在监听，崩溃时触发重连。

        每 10 秒尝试 TCP 连接服务器端口，失败则认为服务器已崩溃，
        触发指数退避重连。
        """
        try:
            while not self._is_stopping:
                await asyncio.sleep(10)
                if self._is_stopping:
                    break
                try:
                    _reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(self._ws_host, self._ws_port),
                        timeout=3.0,
                    )
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    if not self._is_stopping:
                        self._log("warning", "server_down", "检测到 WebSocket 服务器已停止监听，准备重连")
                        self._schedule_reconnect()
                        return
        except asyncio.CancelledError:
            return

    async def stop(self) -> None:
        self._is_stopping = True

        # 取消重连任务
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reconnect_task
            self._reconnect_task = None

        # 停止队列 worker
        if self._queue_worker_task and not self._queue_worker_task.done():
            self._queue_worker_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._queue_worker_task
            self._queue_worker_task = None

        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        for conn in list(self._connections.values()):
            with contextlib.suppress(Exception):
                await conn.close()
        self._connections.clear()
        self._pending_replies.clear()
        self._log("info", "connection_lost", "适配器已停止，所有连接已关闭")

    # ------------------------------------------------------------------
    # 消息发送
    # ------------------------------------------------------------------

    async def send_message(self, response: PlatformResponse, target: str) -> bool:
        websocket = self._find_connection()
        if not websocket:
            self._log("warning", "message_failed", "无可用连接，无法发送消息", details={"target": target})
            self._enqueue_message(response, target)
            return False

        target_type, target_id = self._parse_target(target)
        if not target_id:
            self._log("warning", "message_failed", f"无效的目标: {target}", details={"target": target})
            return False

        message_segments = self._build_message_segments(response)

        # 查找该目标用户的回复引用
        reply_id = self._pending_replies.get(target_id, "")
        if reply_id:
            message_segments.insert(0, {
                "type": "reply",
                "data": {"id": reply_id},
            })
            # 回复引用为一次性，使用后清除
            self._pending_replies.pop(target_id, None)

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
            self._enqueue_message(response, target)
            return False

    # ------------------------------------------------------------------
    # 消息发送队列
    # ------------------------------------------------------------------

    def _enqueue_message(self, response: PlatformResponse, target: str) -> None:
        """将发送失败的消息放入重试队列。队列满时丢弃最旧消息。"""
        item = {"response": response, "target": target}
        if self._send_queue.full():
            try:
                dropped = self._send_queue.get_nowait()
                self._log(
                    "warning", "queue_drop",
                    f"消息队列已满，丢弃最旧消息: {dropped['target']}",
                    details={"target": dropped["target"]},
                )
            except asyncio.QueueEmpty:
                pass
        try:
            self._send_queue.put_nowait(item)
            self._log(
                "info", "queue_enqueue",
                f"消息已入队等待重试 (队列长度: {self._send_queue.qsize()})",
                details={"target": target, "queue_size": self._send_queue.qsize()},
            )
        except asyncio.QueueFull:
            # 极端并发下的兜底
            self._log("warning", "queue_drop", "消息入队失败：队列已满")

    async def _queue_retry_worker(self) -> None:
        """后台任务：定期重试队列中的消息。"""
        try:
            while True:
                await asyncio.sleep(self._QUEUE_RETRY_INTERVAL)
                if self._send_queue.empty():
                    continue

                websocket = self._find_connection()
                if not websocket:
                    continue

                # 一次性取出所有待重试消息
                pending: list[dict[str, Any]] = []
                while not self._send_queue.empty():
                    try:
                        pending.append(self._send_queue.get_nowait())
                    except asyncio.QueueEmpty:
                        break

                self._log(
                    "info", "queue_retry",
                    f"开始重试队列中的 {len(pending)} 条消息",
                    details={"count": len(pending)},
                )

                for item in pending:
                    resp: PlatformResponse = item["response"]
                    tgt: str = item["target"]
                    # 构造一个轻量发送逻辑（不走 send_message 的再次入队，避免递归）
                    success = await self._try_send_direct(resp, tgt, websocket)
                    if not success:
                        # 重新入队
                        self._enqueue_message(resp, tgt)

        except asyncio.CancelledError:
            logger.debug("[qq_onebot] 队列重试任务已取消")

    async def _try_send_direct(
        self,
        response: PlatformResponse,
        target: str,
        websocket: Any,
    ) -> bool:
        """直接尝试通过 WebSocket 发送消息（不触发入队）。"""
        target_type, target_id = self._parse_target(target)
        if not target_id:
            return False

        message_segments = self._build_message_segments(response)
        # 查找该目标用户的回复引用
        reply_id = self._pending_replies.get(target_id, "")
        if reply_id:
            message_segments.insert(0, {
                "type": "reply",
                "data": {"id": reply_id},
            })
            # 回复引用为一次性，使用后清除
            self._pending_replies.pop(target_id, None)

        action = "send_group_msg" if target_type == "group" else "send_private_msg"
        payload: dict[str, Any] = {
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
                "info", "queue_retry_sent",
                f"队列重试发送成功 [{action}] -> {target_id}",
                details={"action": action, "target_id": target_id},
            )
            return True
        except Exception as e:
            self._log(
                "warning", "queue_retry_failed",
                f"队列重试发送仍失败: {e}",
                details={"error": str(e), "target": target},
            )
            return False

    # ------------------------------------------------------------------
    # 事件处理
    # ------------------------------------------------------------------

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
                # 提取被回复消息的 ID，按会话存储
                reply_id = str(seg_data.get("id", ""))
                if reply_id:
                    self._pending_replies[user_id] = reply_id
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
