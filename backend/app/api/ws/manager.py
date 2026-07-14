"""LuomiNest 浏览器自动化 WebSocket 连接管理器。

管理后端 ↔ 前端 Electron Main 之间的单一常驻 WS 连接。
后端 AI 工具通过本管理器向前端发送自动化请求（request_id 关联），
前端执行完毕后回送响应，由本管理器分发到对应的 asyncio.Future。

设计要点：
1. 单连接模型：Electron Main 常驻 1 个连接，无需连接池
2. request_id 关联：每个请求生成唯一 ID，前端响应带回同一 ID
3. asyncio.Future 等待：发送请求后挂起，响应到达时 set_result
4. 超时保护：默认 30s，截图等慢操作 60s
5. ping/pong 心跳：每 25s 检测连接存活
"""
import asyncio
import uuid
from typing import Any

from fastapi import WebSocket
from loguru import logger


class LuomiNestBrowserWSManager:
    """浏览器自动化 WebSocket 连接管理器（单例）"""

    def __init__(self) -> None:
        # 当前活跃的 WS 连接（仅 1 个，Electron Main 常驻）
        self._connection: WebSocket | None = None
        # request_id → Future 映射，用于关联请求与响应
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        # 心跳定时任务
        self._heartbeat_task: asyncio.Task[None] | None = None
        # 最近一次收到 pong 的时间（用于检测连接健康）
        self._last_pong: float = 0.0
        # 保护连接注册/注销等生命周期操作的锁
        self._lock = asyncio.Lock()

    @property
    def is_connected(self) -> bool:
        """WS 连接是否可用"""
        return self._connection is not None

    async def register_connection(self, ws: WebSocket) -> None:
        """注册新的 WS 连接（新连接会顶替旧连接）"""
        async with self._lock:
            if self._connection is not None:
                try:
                    await self._connection.close(code=1000, reason="Replaced by new connection")
                except Exception as e:
                    logger.warning(f"[BrowserWS] 关闭旧连接失败，继续使用新连接: {e}")
                logger.info("[BrowserWS] 旧连接被新连接顶替")

            self._connection = ws
            self._last_pong = asyncio.get_running_loop().time()
            logger.success("[BrowserWS] 前端 Electron Main 已连接")

        # 启动心跳（锁外执行，避免持锁时间过长）
        self._start_heartbeat()

    async def unregister_connection(self) -> None:
        """注销当前 WS 连接，并使所有 pending 请求失败"""
        async with self._lock:
            self._connection = None
            self._stop_heartbeat()

            # 让所有等待中的请求失败
            for req_id, future in list(self._pending.items()):
                if not future.done():
                    future.set_exception(ConnectionError("浏览器连接已断开"))
            self._pending.clear()
        logger.info("[BrowserWS] 前端连接已断开")

    async def send_request(
        self,
        action: str,
        args: dict[str, Any] | None = None,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        """向前端发送自动化请求并等待响应

        Args:
            action: 自动化动作名（navigate/click/type/screenshot 等）
            args: 动作参数
            timeout: 超时秒数（默认 30s，截图建议 60s）

        Returns:
            前端响应的 data 字段（dict）

        Raises:
            ConnectionError: WS 未连接
            asyncio.TimeoutError: 等待响应超时
            Exception: 前端执行返回的错误
        """
        if self._connection is None:
            raise ConnectionError("浏览器未连接，请先打开 LuomiNest 桌面端")

        request_id = f"req_{uuid.uuid4().hex[:12]}"
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._pending[request_id] = future

        message = {
            "type": "automation_request",
            "request_id": request_id,
            "action": action,
            "args": args or {},
        }

        # 快照连接引用：即使 _connection 在 await 期间被置 None，发送仍使用快照
        conn = self._connection
        if conn is None:
            self._pending.pop(request_id, None)
            raise ConnectionError("浏览器未连接，请先打开 LuomiNest 桌面端")

        try:
            await conn.send_json(message)
            logger.debug(f"[BrowserWS] → {action} (req={request_id[:8]})")
        except Exception as e:
            self._pending.pop(request_id, None)
            raise ConnectionError(f"发送 WS 消息失败: {e}") from e

        try:
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            self._pending.pop(request_id, None)
            logger.warning(f"[BrowserWS] 请求超时: {action} (req={request_id[:8]}, {timeout}s)")
            raise
        except Exception:
            self._pending.pop(request_id, None)
            raise

    async def handle_message(self, message: dict[str, Any]) -> None:
        """处理前端发来的消息（响应/事件/pong）"""
        msg_type = message.get("type")

        if msg_type == "automation_response":
            request_id = message.get("request_id", "")
            future = self._pending.pop(request_id, None)
            if future is None or future.done():
                logger.warning(f"[BrowserWS] 收到孤儿响应: req={request_id[:8]}")
                return

            success = message.get("success", False)
            if success:
                future.set_result(message.get("data", {}))
            else:
                err = message.get("error", "未知错误")
                future.set_exception(RuntimeError(err))
            logger.debug(f"[BrowserWS] ← 响应 req={request_id[:8]} success={success}")

        elif msg_type == "pong":
            self._last_pong = asyncio.get_running_loop().time()

        elif msg_type == "event":
            # 前端单向事件（如 tab_updated），目前仅记录日志
            event_name = message.get("event", "unknown")
            logger.debug(f"[BrowserWS] ← 事件: {event_name}")

        else:
            logger.warning(f"[BrowserWS] 未知消息类型: {msg_type}")

    def _start_heartbeat(self) -> None:
        """启动心跳定时任务"""
        self._stop_heartbeat()
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    def _stop_heartbeat(self) -> None:
        if self._heartbeat_task is not None and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
        self._heartbeat_task = None

    async def _heartbeat_loop(self) -> None:
        """每 25s 发送 ping，连续 2 次无 pong 则认为连接断开"""
        while True:
            try:
                await asyncio.sleep(25)
                if self._connection is None:
                    break

                loop = asyncio.get_running_loop()
                # 若超过 50s 未收到 pong，主动关闭连接
                if loop.time() - self._last_pong > 50:
                    logger.warning("[BrowserWS] 心跳超时，主动断开连接")
                    async with self._lock:
                        if self._connection is not None:
                            try:
                                await self._connection.close(code=1001, reason="Heartbeat timeout")
                            except Exception as e:
                                logger.debug(f"[BrowserWS] 心跳超时后关闭连接失败（可忽略）: {e}")
                    await self.unregister_connection()
                    break

                await self._connection.send_json({"type": "ping"})
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"[BrowserWS] 心跳发送失败: {e}")
                await self.unregister_connection()
                break

    async def shutdown(self) -> None:
        """关闭管理器（应用退出时调用）"""
        self._stop_heartbeat()
        if self._connection is not None:
            try:
                await self._connection.close(code=1001, reason="Server shutting down")
            except Exception as e:
                logger.debug(f"[BrowserWS] 关闭连接时发生异常（忽略并继续清理）: {e}")
            self._connection = None

        for req_id, future in list(self._pending.items()):
            if not future.done():
                future.set_exception(ConnectionError("服务正在关闭"))
        self._pending.clear()
        logger.info("[BrowserWS] 管理器已关闭")


# 全局单例
browser_ws_manager = LuomiNestBrowserWSManager()
