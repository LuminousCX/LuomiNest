"""REST API 适配器入站闭环测试（P0-5：入站/轮询死代码修复回归）。

覆盖：
- 适配器级完整通路：模拟入站消息 → 断言 Agent（message handler）被调用
  → 断言回复回写（callback 推送 / 轮询队列），mock Agent 层
- verify_api_key 常量时间比较语义
- HTTP 入站/轮询端点（POST/GET /platforms/instances/{id}/rest/messages）：
  api_key 校验、空消息拒绝、端到端「POST → Agent → 轮询拉取回复」
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

import app.api.v1.endpoints.platform as platform_endpoints
from app.api.v1.endpoints.platform import router as platform_router
from app.core.exceptions import LuomiNestError
from app.runtime.platform.adapters.rest_api import RESTPlatformAdapter
from app.runtime.platform.base import PlatformResponse


# ─── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def adapter() -> RESTPlatformAdapter:
    """已初始化、未配置回调（回复走轮询队列）的适配器实例。"""
    a = RESTPlatformAdapter()
    a.initialize({"callback_url": "", "api_key": "", "max_queue_size": 100})
    a.set_instance_id("inst-rest-1")
    return a


@pytest.fixture
def agent_recorder():
    """可编程的 mock Agent：记录收到的消息，返回可配置响应。"""
    holder: dict[str, Any] = {"response": PlatformResponse(content="agent reply"), "raise": None, "calls": []}

    async def handler(message, instance_id):
        holder["calls"].append((message, instance_id))
        if holder["raise"]:
            raise holder["raise"]
        return holder["response"]

    handler.holder = holder
    return handler


async def _drain_background(adapter: RESTPlatformAdapter) -> None:
    """等待适配器在途后台路由任务全部结束。"""
    tasks = [t for t in adapter._background_tasks]
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


# ─── verify_api_key 测试 ───────────────────────────────────────


class TestVerifyApiKey:
    def test_no_key_configured_allows_all(self, adapter: RESTPlatformAdapter) -> None:
        assert adapter.verify_api_key(None) is True
        assert adapter.verify_api_key("") is True
        assert adapter.verify_api_key("anything") is True

    def test_configured_key_match(self) -> None:
        a = RESTPlatformAdapter()
        a.initialize({"api_key": "secret-key"})
        assert a.verify_api_key("secret-key") is True
        assert a.verify_api_key("wrong") is False
        assert a.verify_api_key(None) is False
        assert a.verify_api_key("") is False


# ─── 适配器级入站闭环测试 ──────────────────────────────────────


class TestInboundLoop:
    """process_incoming_message 完整通路：入站消息 → Agent 被调用 → 回复回写。"""

    @pytest.mark.asyncio
    async def test_inbound_routes_to_agent_and_queues_reply(
        self, adapter: RESTPlatformAdapter, agent_recorder
    ) -> None:
        """模拟入站消息 → Agent 被调用 → 回复入轮询队列（无 callback_url 时）。"""
        adapter.set_message_handler(agent_recorder)

        msg = await adapter.process_incoming_message({
            "user_id": "user123",
            "content": "你好",
            "session_id": "sess456",
        })

        # 立即返回转换后的 PlatformMessage（含请求关联 id）
        assert msg.platform == "rest_api"
        assert msg.user_id == "user123"
        assert msg.content == "你好"
        assert msg.session_id == "sess456"
        assert msg.message_id
        assert msg.is_group is False

        # 等待后台路由任务结束后断言
        await _drain_background(adapter)

        # Agent 被调用（携带同一消息与实例 id）
        assert len(agent_recorder.holder["calls"]) == 1
        routed_msg, inst_id = agent_recorder.holder["calls"][0]
        assert routed_msg is msg
        assert inst_id == "inst-rest-1"

        # 回复回写：入轮询队列，user_id 为拉取键
        queued = adapter.poll_messages("user123")
        assert len(queued) == 1
        assert queued[0]["content"] == "agent reply"
        assert queued[0]["target"] == "user123"

    @pytest.mark.asyncio
    async def test_inbound_reply_pushed_via_callback(self, agent_recorder) -> None:
        """配置 callback_url 时回复主动推送，不进轮询队列。"""
        a = RESTPlatformAdapter()
        a.initialize({"callback_url": "https://caller.example.com/hook", "api_key": ""})
        a.set_instance_id("inst-rest-1")
        a.set_message_handler(agent_recorder)

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        a._http_client = AsyncMock()
        a._http_client.post = AsyncMock(return_value=mock_resp)

        await a.process_incoming_message({"user_id": "u1", "content": "hi"})
        await _drain_background(a)

        a._http_client.post.assert_called_once()
        call = a._http_client.post.call_args
        assert call[0][0] == "https://caller.example.com/hook"
        assert call[1]["json"]["content"] == "agent reply"
        assert call[1]["json"]["target"] == "u1"
        assert a.poll_messages("u1") == []

    @pytest.mark.asyncio
    async def test_agent_no_reply_no_writeback(self, adapter: RESTPlatformAdapter, agent_recorder) -> None:
        """Agent 无响应：不回写、队列为空，入站仍成功返回。"""
        agent_recorder.holder["response"] = None
        adapter.set_message_handler(agent_recorder)

        msg = await adapter.process_incoming_message({"user_id": "u1", "content": "hi"})
        await _drain_background(adapter)

        assert msg.message_id
        assert adapter.poll_messages("u1") == []

    @pytest.mark.asyncio
    async def test_agent_exception_swallowed_and_logged(self, adapter: RESTPlatformAdapter, agent_recorder) -> None:
        """Agent 抛异常：后台任务吞掉异常不炸，入站请求不受影响。"""
        agent_recorder.holder["raise"] = RuntimeError("agent exploded")
        adapter.set_message_handler(agent_recorder)

        msg = await adapter.process_incoming_message({"user_id": "u1", "content": "hi"})
        await _drain_background(adapter)

        assert msg.message_id
        assert adapter.poll_messages("u1") == []
        assert adapter._last_error is not None

    @pytest.mark.asyncio
    async def test_stop_cancels_pending_route_tasks(self, agent_recorder) -> None:
        """stop 终止在途路由任务（含阻塞中的 Agent 调用），不悬挂。"""
        a = RESTPlatformAdapter()
        a.initialize({})
        a.set_instance_id("inst-rest-1")

        release = asyncio.Event()

        async def blocking_handler(message, instance_id):
            await release.wait()
            return PlatformResponse(content="late reply")

        a.set_message_handler(blocking_handler)

        msg = await a.process_incoming_message({"user_id": "u1", "content": "hi"})
        assert msg.message_id
        await asyncio.sleep(0)  # 让后台任务启动并阻塞在 handler
        assert a._background_tasks

        await a.stop()
        assert a._background_tasks == set()
        assert a.poll_messages("u1") == []


# ─── HTTP 端点测试（POST/GET /instances/{id}/rest/messages）────


@pytest.fixture
def rest_app(adapter: RESTPlatformAdapter, monkeypatch) -> FastAPI:
    """最小化装配：platform 路由 + 注册表 get_instance 打桩 + 错误信封。"""
    inst = SimpleNamespace(adapter=adapter, adapter_type="rest_api")
    monkeypatch.setattr(
        platform_endpoints,
        "get_instance",
        lambda instance_id: inst if instance_id == "inst-rest-1" else None,
    )

    app = FastAPI()
    app.include_router(platform_router, prefix="/api/v1")

    @app.exception_handler(LuomiNestError)
    async def lumi_error_handler(request: Request, exc: LuomiNestError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": 1, "message": exc.message, "error": {"code": exc.code, "message": exc.message}, "data": None},
        )

    return app


@pytest.fixture
async def rest_client(rest_app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=rest_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestRestApiEndpoints:
    """REST API 入站/轮询端点测试（P0-5：入站端点缺失修复回归）。"""

    @pytest.mark.asyncio
    async def test_post_message_accepted(self, rest_client: AsyncClient, adapter: RESTPlatformAdapter, agent_recorder) -> None:
        adapter.set_message_handler(agent_recorder)

        resp = await rest_client.post(
            "/api/v1/platforms/instances/inst-rest-1/rest/messages",
            json={"user_id": "u1", "content": "你好"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["received"] is True
        assert body["data"]["messageId"]
        assert body["data"]["sessionId"] == "u1"

        await _drain_background(adapter)

        # Agent 收到消息，回复可从轮询端点拉取
        assert len(agent_recorder.holder["calls"]) == 1
        poll = await rest_client.get("/api/v1/platforms/instances/inst-rest-1/rest/messages", params={"user_id": "u1"})
        assert poll.status_code == 200
        messages = poll.json()["data"]["messages"]
        assert len(messages) == 1
        assert messages[0]["content"] == "agent reply"

    @pytest.mark.asyncio
    async def test_post_message_api_key_enforced(self, monkeypatch) -> None:
        """配置 api_key 后：无密钥 401，正确密钥通过。"""
        a = RESTPlatformAdapter()
        a.initialize({"api_key": "secret-key"})
        a.set_instance_id("inst-rest-1")
        a.set_message_handler(AsyncMock(return_value=PlatformResponse(content="ok")))

        inst = SimpleNamespace(adapter=a, adapter_type="rest_api")
        monkeypatch.setattr(
            platform_endpoints, "get_instance", lambda instance_id: inst if instance_id == "inst-rest-1" else None
        )
        app = FastAPI()
        app.include_router(platform_router, prefix="/api/v1")

        @app.exception_handler(LuomiNestError)
        async def err_handler(request: Request, exc: LuomiNestError):
            return JSONResponse(status_code=exc.status_code, content={"message": exc.message})

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            denied = await client.post(
                "/api/v1/platforms/instances/inst-rest-1/rest/messages",
                json={"user_id": "u1", "content": "hi"},
            )
            assert denied.status_code == 401

            ok_resp = await client.post(
                "/api/v1/platforms/instances/inst-rest-1/rest/messages",
                json={"user_id": "u1", "content": "hi"},
                headers={"X-API-Key": "secret-key"},
            )
            assert ok_resp.status_code == 200

            # Bearer 形式同样可用
            bearer = await client.post(
                "/api/v1/platforms/instances/inst-rest-1/rest/messages",
                json={"user_id": "u1", "content": "hi again"},
                headers={"Authorization": "Bearer secret-key"},
            )
            assert bearer.status_code == 200

            poll_denied = await client.get(
                "/api/v1/platforms/instances/inst-rest-1/rest/messages", params={"user_id": "u1"}
            )
            assert poll_denied.status_code == 401

    @pytest.mark.asyncio
    async def test_post_empty_message_rejected(self, rest_client: AsyncClient) -> None:
        resp = await rest_client.post(
            "/api/v1/platforms/instances/inst-rest-1/rest/messages",
            json={"user_id": "u1", "content": ""},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_post_image_only_message_accepted(self, rest_client: AsyncClient, adapter: RESTPlatformAdapter, agent_recorder) -> None:
        adapter.set_message_handler(agent_recorder)

        resp = await rest_client.post(
            "/api/v1/platforms/instances/inst-rest-1/rest/messages",
            json={"user_id": "u1", "content": "", "image_urls": ["https://example.com/a.png"]},
        )
        assert resp.status_code == 200
        await _drain_background(adapter)
        routed = agent_recorder.holder["calls"][0][0]
        assert routed.image_urls == ["https://example.com/a.png"]

    @pytest.mark.asyncio
    async def test_unknown_instance_404(self, rest_client: AsyncClient) -> None:
        resp = await rest_client.post(
            "/api/v1/platforms/instances/no-such-inst/rest/messages",
            json={"user_id": "u1", "content": "hi"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_poll_requires_user_id(self, rest_client: AsyncClient) -> None:
        resp = await rest_client.get("/api/v1/platforms/instances/inst-rest-1/rest/messages")
        assert resp.status_code == 422  # FastAPI 缺参校验
