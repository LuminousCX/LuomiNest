"""LuomiNest Avatar Drive WebSocket.

实时模型驱动 WebSocket 端点，用于非 chat 来源的模型驱动推送：
- 摄像头面部追踪 → VRM 表情驱动
- 截屏感知 → AI 主动评论触发
- 语音情感分析 → PAD 连续情感推送
- AI 自主行为 → 随机动作触发

设计原则：
- 与 chat stream emotion 解耦：chat stream 仍通过 SSE 推送 ChatStreamChunk.emotion
- /avatar/drive 是可选的额外模态通道
- 客户端通过 subscribe/unsubscribe 控制订阅
- 服务端按模型 ID 分组广播（未来扩展，当前为单连接 echo + push 接口）
"""
from __future__ import annotations

import json
import asyncio
import time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from loguru import logger

from app.schemas.avatar import (
    AvatarDrivePacket,
    AvatarDriveData,
    PadEmotion,
)
from app.security.auth.local_token import load_auth_token, verify_token


router = APIRouter()


# ---------------------------------------------------------------------------
# 连接管理器（线程安全）
# ---------------------------------------------------------------------------

class AvatarDriveConnectionManager:
    """/avatar/drive WebSocket 连接管理器。

    维护当前活跃连接列表，支持按 model_id 分组广播。
    未来可扩展为跨连接的 AI 自主行为推送（如所有订阅某模型的客户端都收到
    随机眨眼/打哈欠指令）。
    """

    def __init__(self) -> None:
        self._connections: dict[WebSocket, set[str]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> bool:
        """接受连接，返回是否成功。"""
        await websocket.accept()
        async with self._lock:
            self._connections[websocket] = set()
        logger.info(f"[AvatarDriveWS] Connected: {websocket.client}")
        return True

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.pop(websocket, None)
        logger.info(f"[AvatarDriveWS] Disconnected: {websocket.client}")

    async def subscribe(self, websocket: WebSocket, model_id: str) -> None:
        async with self._lock:
            if websocket in self._connections:
                self._connections[websocket].add(model_id)
        logger.debug(f"[AvatarDriveWS] Subscribed: {websocket.client} → {model_id}")

    async def unsubscribe(self, websocket: WebSocket) -> None:
        async with self._lock:
            if websocket in self._connections:
                self._connections[websocket].clear()
        logger.debug(f"[AvatarDriveWS] Unsubscribed: {websocket.client}")

    async def broadcast(self, model_id: str, packet: AvatarDrivePacket) -> None:
        """向所有订阅了 model_id 的连接广播驱动包。"""
        message = packet.model_dump_json()
        dead: list[WebSocket] = []
        async with self._lock:
            for ws, models in self._connections.items():
                if model_id in models:
                    try:
                        await ws.send_text(message)
                    except Exception:
                        dead.append(ws)
        for ws in dead:
            await self.disconnect(ws)


# 全局单例
avatar_drive_ws_manager = AvatarDriveConnectionManager()


# ---------------------------------------------------------------------------
# WebSocket 端点
# ---------------------------------------------------------------------------

@router.websocket("/avatar/drive")
async def avatar_drive_endpoint(websocket: WebSocket):
    """Avatar 驱动 WebSocket 端点。

    连接路径：ws://127.0.0.1:18000/ws/avatar/drive?token=<auth_token>

    客户端 → 服务端消息：
    - {"type": "subscribe", "model_id": "builtin-vrm-sample"}
    - {"type": "unsubscribe"}
    - {"type": "emotion_drive", "timestamp": ..., "data": {...}}  # 客户端可主动推送（如摄像头追踪）

    服务端 → 客户端消息：
    - {"type": "emotion_drive", "timestamp": ..., "data": {...}}

    注意：websocket 参数必须有 WebSocket 类型注解，否则 FastAPI 无法识别。
    """
    expected_token = load_auth_token()

    if expected_token:
        provided = websocket.query_params.get("token", "")
        if not verify_token(provided, expected_token):
            logger.warning(f"[AvatarDriveWS] Rejected unauthorized connection: {websocket.client}")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="未授权")
            return

    await avatar_drive_ws_manager.connect(websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning(f"[AvatarDriveWS] Invalid JSON: {raw[:100]}")
                continue

            msg_type = msg.get("type")
            if msg_type == "subscribe":
                model_id = msg.get("model_id", "")
                if model_id:
                    await avatar_drive_ws_manager.subscribe(websocket, model_id)
                    await websocket.send_text(json.dumps({
                        "type": "subscribed",
                        "model_id": model_id,
                        "timestamp": int(time.time() * 1000),
                    }))
            elif msg_type == "unsubscribe":
                await avatar_drive_ws_manager.unsubscribe(websocket)
                await websocket.send_text(json.dumps({
                    "type": "unsubscribed",
                    "timestamp": int(time.time() * 1000),
                }))
            elif msg_type == "emotion_drive":
                # 客户端主动推送驱动包（如摄像头追踪驱动 VRM）
                # 验证并广播给其他订阅同一模型的连接
                try:
                    packet = AvatarDrivePacket.model_validate(msg)
                    await avatar_drive_ws_manager.broadcast(packet.data.emotion or "", packet)
                except Exception as e:
                    logger.warning(f"[AvatarDriveWS] Invalid drive packet: {e}")
            else:
                logger.warning(f"[AvatarDriveWS] Unknown message type: {msg_type}")

    except WebSocketDisconnect:
        await avatar_drive_ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"[AvatarDriveWS] Error: {e}", exc_info=True)
        await avatar_drive_ws_manager.disconnect(websocket)


# ---------------------------------------------------------------------------
# 供其他后端模块调用的推送接口
# ---------------------------------------------------------------------------

async def push_emotion_drive(
    model_id: str,
    emotion: str | None = None,
    pad: PadEmotion | None = None,
    action: str | None = None,
    lip_sync: float | None = None,
    viseme: str | None = None,
    params: dict[str, float] | None = None,
) -> None:
    """供后端其他服务（语音情感分析、AI 自主行为等）调用，推送驱动包。

    例如 voice_emotion_analyzer 分析 TTS 音频后，调用此函数推送 PAD 值。
    """
    packet = AvatarDrivePacket(
        timestamp=int(time.time() * 1000),
        data=AvatarDriveData(
            emotion=emotion,
            pad=pad,
            action=action,
            lip_sync=lip_sync,
            viseme=viseme,
            params=params,
        ),
    )
    await avatar_drive_ws_manager.broadcast(model_id, packet)
