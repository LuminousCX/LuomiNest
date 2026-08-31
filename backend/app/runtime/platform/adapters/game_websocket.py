import asyncio
import json
from typing import Any
from loguru import logger

from app.runtime.platform.base import BasePlatformAdapter, PlatformMessage, PlatformResponse


class LuomiNestGameWebSocketAdapter(BasePlatformAdapter):
    """游戏 WebSocket 网关适配器：通过 WebSocket 接入任意游戏客户端。

    工作流程：
    1. LuomiNest 启动 WebSocket 服务器
    2. 游戏客户端（Mod/插件/脚本）连接到此服务器
    3. 客户端发送 JSON 格式消息，适配器解析后路由到主 Agent
    4. 主 Agent 响应后通过 WebSocket 发回客户端

    消息协议（JSON）：
    入站：{
        "type": "message",
        "user_id": "玩家ID",
        "content": "消息内容",
        "sender_name": "玩家昵称",
        "is_group": false,
        "image_urls": ["图片URL"],
        "game_context": {"game": "xxx", "scene": "xxx"}
    }
    出站：{
        "type": "response",
        "content": "响应内容",
        "reply_to": "原消息ID"
    }

    配置项：
    - ws_host: 监听地址
    - ws_port: 监听端口
    - auth_token: 可选鉴权 token
    - max_clients: 最大客户端数
    """

    platform_name = "game_websocket"

    def __init__(self) -> None:
        super().__init__()
        self._server: Any = None
        self._clients: dict[str, Any] = {}
        self._client_meta: dict[str, dict] = {}

    def initialize(self, config: dict[str, Any]) -> None:
        super().initialize(config)
        self._ws_host = config.get("ws_host", "0.0.0.0")
        self._ws_port = int(config.get("ws_port", 8082))
        self._auth_token = config.get("auth_token", "")
        self._max_clients = int(config.get("max_clients", 50))

    async def start(self) -> None:
        import websockets

        async def client_handler(websocket: Any) -> None:
            client_id = id(websocket)
            if len(self._clients) >= self._max_clients:
                logger.warning(f"[GameWS] Max clients reached, rejecting connection")
                await websocket.close(code=1013, reason="Server overloaded")
                return

            self._clients[client_id] = websocket
            peer = websocket.remote_address if hasattr(websocket, "remote_address") else "unknown"
            logger.info(f"[GameWS] Client connected from {peer}")

            try:
                async for raw in websocket:
                    try:
                        data = json.loads(raw)
                        await self._handle_client_message(data, websocket, client_id)
                    except json.JSONDecodeError:
                        await self._send_error(websocket, "Invalid JSON format")
                    except Exception as e:
                        logger.error(f"[GameWS] Message handling failed: {e}")
                        await self._send_error(websocket, f"Internal error: {e}")
            except Exception as e:
                logger.warning(f"[GameWS] Client disconnected: {e}")
            finally:
                self._clients.pop(client_id, None)
                self._client_meta.pop(client_id, None)

        logger.info(f"[GameWS] Starting WebSocket server on {self._ws_host}:{self._ws_port}")
        self._server = await websockets.serve(client_handler, self._ws_host, self._ws_port)
        logger.success(f"[GameWS] Server listening on {self._ws_host}:{self._ws_port}")

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        for ws in list(self._clients.values()):
            try:
                await ws.close()
            except Exception:
                # 停机清理：连接可能已断开，属预期情况
                logger.debug("[GameWS] 关闭客户端连接时异常（忽略）", exc_info=True)
        self._clients.clear()
        self._client_meta.clear()
        logger.info(f"[GameWS] Adapter stopped")

    async def send_message(self, response: PlatformResponse, target: str) -> bool:
        websocket = self._clients.get(int(target)) if target.isdigit() else None
        if not websocket:
            for cid, ws in self._clients.items():
                if str(cid) == target:
                    websocket = ws
                    break

        if not websocket:
            logger.warning(f"[GameWS] Client {target} not found")
            return False

        payload = {
            "type": "response",
            "content": response.content,
            "reply_to": response.reply_to,
            "message_type": response.message_type,
        }
        if response.image_urls:
            payload["image_urls"] = response.image_urls

        try:
            await websocket.send(json.dumps(payload, ensure_ascii=False))
            logger.info(f"[GameWS] Sent response to {target}: {response.content[:50]}")
            return True
        except Exception as e:
            logger.error(f"[GameWS] Send failed: {e}")
            return False

    async def broadcast(self, content: str) -> int:
        """向所有连接的游戏客户端广播消息。"""
        payload = {"type": "broadcast", "content": content}
        raw = json.dumps(payload, ensure_ascii=False)
        success = 0
        for cid, ws in list(self._clients.items()):
            try:
                await ws.send(raw)
                success += 1
            except Exception as e:
                logger.warning(f"[GameWS] Broadcast failed for client {cid}: {e}")
                self._clients.pop(cid, None)
                self._client_meta.pop(cid, None)
        logger.info(f"[GameWS] Broadcast to {success}/{len(self._clients)} clients")
        return success

    async def _handle_client_message(self, data: dict, websocket: Any, client_id: int) -> None:
        msg_type = data.get("type", "")

        if msg_type == "auth":
            await self._handle_auth(data, websocket, client_id)
            return

        if msg_type == "ping":
            await websocket.send(json.dumps({"type": "pong"}))
            return

        if msg_type != "message":
            await self._send_error(websocket, f"Unknown message type: {msg_type}")
            return

        if self._auth_token and not self._client_meta.get(client_id, {}).get("authenticated"):
            await self._send_error(websocket, "Not authenticated")
            return

        platform_msg = self._convert_game_message(data, client_id)
        if not platform_msg:
            await self._send_error(websocket, "Invalid message format")
            return

        game_context = data.get("game_context", {})
        if game_context:
            self._client_meta.setdefault(client_id, {}).update({"game_context": game_context})

        response = await self._emit_message(platform_msg)
        if response and response.content:
            await self.send_message(response, str(client_id))

    async def _handle_auth(self, data: dict, websocket: Any, client_id: int) -> None:
        token = data.get("token", "")
        if not self._auth_token or token == self._auth_token:
            self._client_meta.setdefault(client_id, {})["authenticated"] = True
            await websocket.send(json.dumps({"type": "auth_ok"}))
            logger.info(f"[GameWS] Client {client_id} authenticated")
        else:
            await websocket.send(json.dumps({"type": "auth_failed", "message": "Invalid token"}))
            await websocket.close()

    def _convert_game_message(self, data: dict, client_id: int) -> PlatformMessage | None:
        user_id = data.get("user_id", "")
        content = data.get("content", "").strip()
        if not content and not data.get("image_urls"):
            return None

        return PlatformMessage(
            platform=self.platform_name,
            user_id=user_id or f"client_{client_id}",
            content=content,
            session_id=data.get("session_id", user_id or f"client_{client_id}"),
            message_id=data.get("message_id", ""),
            sender_name=data.get("sender_name", user_id),
            is_group=bool(data.get("is_group", False)),
            image_urls=data.get("image_urls", []),
            raw=data,
        )

    async def _send_error(self, websocket: Any, message: str) -> None:
        try:
            await websocket.send(json.dumps({"type": "error", "message": message}))
        except Exception:
            logger.warning(f"[GameWS] 错误消息下发失败: {message}", exc_info=True)
