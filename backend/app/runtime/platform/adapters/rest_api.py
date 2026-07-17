"""REST API 平台适配器 - 通过 HTTP REST API 接入第三方系统。

提供标准的 HTTP 接口，让外部系统可以通过 REST API 与 LuomiNest 对话。
支持两种出站模式：
- 回调推送：配置 callback_url 后，响应会主动 POST 到该 URL
- 主动轮询：未配置回调时，响应存入内存队列，由外部轮询拉取
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict
from typing import Any

import httpx
from loguru import logger

from app.runtime.platform.base import (
    AdapterStatus,
    BasePlatformAdapter,
    PlatformMessage,
    PlatformResponse,
)
from app.runtime.platform.infrastructure.retry import RetryConfig, async_retry


class RESTPlatformAdapter(BasePlatformAdapter):
    """REST API 适配器：通过标准 HTTP 接口与外部系统交互。

    入站：外部系统 POST 消息到本适配器，转换为 PlatformMessage 路由到主 Agent。
    出站：主 Agent 的响应通过 callback_url 推送，或存入队列供外部轮询。
    """

    platform_name = "rest_api"

    config_metadata = {
        "callback_url": {"type": "string", "required": False, "label": "回调URL"},
        "api_key": {"type": "string", "required": False, "label": "API密钥", "sensitive": True},
        "max_queue_size": {"type": "number", "required": False, "default": 100, "label": "消息队列大小"},
    }

    def __init__(self) -> None:
        super().__init__()
        self._callback_url: str = ""
        self._api_key: str = ""
        self._max_queue_size: int = 100
        # user_id -> list of response dicts
        self._message_queues: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._http_client: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    def initialize(self, config: dict[str, Any]) -> None:
        """解析配置并初始化资源。"""
        super().initialize(config)
        self._callback_url = config.get("callback_url", "")
        self._api_key = config.get("api_key", "")
        self._max_queue_size = int(config.get("max_queue_size", 100))
        self._http_client = httpx.AsyncClient(timeout=30.0)
        logger.info(
            f"[rest_api] 适配器已初始化 | callback_url={self._callback_url or '(未配置)'}"
        )

    async def start(self) -> None:
        """启动适配器。"""
        await super().start()
        self.update_status(AdapterStatus.RUNNING)
        self._log(
            "success",
            "adapter_started",
            "REST API 适配器已启动",
            details={"callback_url": self._callback_url or "(未配置)"},
        )

    async def stop(self) -> None:
        """停止适配器，释放 HTTP 客户端。"""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        self._message_queues.clear()
        self._log("info", "adapter_stopped", "REST API 适配器已停止")
        await super().stop()

    # ------------------------------------------------------------------
    # 入站：消息接收（REST API 特有格式验证 + 内部闭环）
    # ------------------------------------------------------------------

    async def handle_incoming_message(self, data: dict[str, Any]) -> PlatformMessage:
        """接收外部系统的 JSON 消息，进行 REST API 格式验证并转换为 PlatformMessage。

        本方法仅负责格式验证与转换，消息路由由路由层调用 ``_emit_message()`` 完成。

        Args:
            data: 请求体，格式如下::

                {
                    "user_id": "user123",
                    "content": "你好",
                    "session_id": "session456",   # 可选
                    "image_urls": ["https://..."], # 可选
                    "metadata": {}                 # 可选额外数据
                }

        Returns:
            转换后的 PlatformMessage 实例。
        """
        user_id = data.get("user_id", "anonymous")
        content = data.get("content", "")
        session_id = data.get("session_id", user_id)
        image_urls: list[str] = data.get("image_urls", [])
        metadata: dict[str, Any] = data.get("metadata", {})
        message_id = str(uuid.uuid4())

        platform_msg = PlatformMessage(
            platform=self.platform_name,
            user_id=user_id,
            content=content,
            session_id=session_id,
            message_id=message_id,
            sender_name=metadata.get("sender_name", user_id),
            is_group=False,
            image_urls=image_urls,
            raw=data,
        )

        self._log(
            "info",
            "message_received",
            f"收到 REST API 消息: {content[:50]}",
            details={
                "user_id": user_id,
                "session_id": session_id,
                "message_id": message_id,
                "has_images": bool(image_urls),
            },
        )

        return platform_msg

    # ------------------------------------------------------------------
    # 出站：消息发送
    # ------------------------------------------------------------------

    async def send_message(self, response: PlatformResponse, target: str) -> bool:
        """向外部系统发送响应。

        如果配置了 callback_url，将响应 POST 到该 URL；
        否则将响应存入内存队列，供外部轮询拉取。

        Args:
            response: 主 Agent 生成的响应。
            target: 目标用户 ID。

        Returns:
            是否发送成功。
        """
        response_data = self._build_response_payload(response, target)

        if self._callback_url:
            return await self._push_callback(response_data, target)

        # 无回调 URL，存入队列
        self._enqueue_message(target, response_data)
        return True

    # ------------------------------------------------------------------
    # 轮询
    # ------------------------------------------------------------------

    def poll_messages(self, user_id: str) -> list[dict[str, Any]]:
        """获取指定用户的待拉取消息列表，拉取后从队列中移除。

        Args:
            user_id: 用户标识。

        Returns:
            该用户待拉取的消息列表，可能为空。
        """
        messages = self._message_queues.pop(user_id, [])
        if messages:
            self._log(
                "info",
                "messages_polled",
                f"用户 {user_id} 拉取了 {len(messages)} 条消息",
                details={"user_id": user_id, "count": len(messages)},
            )
        return messages

    # ------------------------------------------------------------------
    # API 密钥验证
    # ------------------------------------------------------------------

    def verify_api_key(self, provided_key: str | None) -> bool:
        """验证请求中提供的 API 密钥。

        Args:
            provided_key: 请求中携带的 API 密钥。

        Returns:
            验证是否通过。未配置 api_key 时始终返回 True。
        """
        if not self._api_key:
            return True
        return provided_key == self._api_key

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _build_response_payload(
        self, response: PlatformResponse, target: str
    ) -> dict[str, Any]:
        """构建出站消息的 JSON 载荷。"""
        payload: dict[str, Any] = {
            "message_id": str(uuid.uuid4()),
            "target": target,
            "content": response.content,
            "message_type": response.message_type,
            "timestamp": time.time(),
        }
        if response.image_urls:
            payload["image_urls"] = response.image_urls
        if response.reply_to:
            payload["reply_to"] = response.reply_to
        if response.extra:
            payload["extra"] = response.extra
        return payload

    async def _push_callback(
        self, response_data: dict[str, Any], target: str
    ) -> bool:
        """通过 callback_url 将响应推送到外部系统。"""
        if not self._http_client:
            self._log("error", "message_failed", "HTTP 客户端未初始化")
            return False

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        retry_config = RetryConfig(
            max_retries=3,
            base_delay=1.0,
            max_delay=10.0,
            jitter=0.5,
            retryable_exceptions=(httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException),
        )

        async def _do_push() -> None:
            assert self._http_client is not None
            resp = await self._http_client.post(
                self._callback_url,
                json=response_data,
                headers=headers,
            )
            resp.raise_for_status()

        try:
            await async_retry(_do_push, config=retry_config)
            self._log(
                "info",
                "message_sent",
                f"消息已推送到回调 URL -> {target}: {response_data.get('content', '')[:50]}",
                details={"target": target, "callback_url": self._callback_url},
            )
            return True
        except Exception as e:
            logger.error(f"[rest_api] 回调推送失败: {e}")
            self._log(
                "error",
                "message_failed",
                f"回调推送失败，消息已转入队列: {e}",
                details={"error": str(e), "target": target},
            )
            # 推送失败时降级到队列
            self._enqueue_message(target, response_data)
            return False

    def _enqueue_message(self, user_id: str, response_data: dict[str, Any]) -> None:
        """将消息存入用户的轮询队列。"""
        queue = self._message_queues[user_id]
        if len(queue) >= self._max_queue_size:
            # 丢弃最旧的消息
            queue.pop(0)
            self._log(
                "warning",
                "queue_overflow",
                f"用户 {user_id} 消息队列已满，丢弃最旧消息",
                details={"user_id": user_id, "max_queue_size": self._max_queue_size},
            )
        queue.append(response_data)
        self._log(
            "info",
            "message_queued",
            f"消息已入队 -> {user_id} (队列长度: {len(queue)})",
            details={"user_id": user_id, "queue_size": len(queue)},
        )
