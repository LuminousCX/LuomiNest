"""M4 云路由单元测试（不打真实网络）。

覆盖三块契约：
- CloudTokenStore：set/get/clear/configured 语义、非法 routingMode 归一化、
  多线程并发 set/get/clear 不炸且快照一致
- CloudProxyProvider：_build_headers 每请求实时取最新 token（两次注入不同令牌
  → 两次请求头不同）、X-LMC-Request-Id 每请求唯一、base_url 实时跟随注入值、
  embed 抛业务异常、上游 429 错误体 errCode/message 透传为 ProviderError
  （非流式与 SSE 流式均验证；用 httpx.MockTransport，零网络）
- LLMAdapter 路由钩子：mode=off / 未注入 → 原 provider；mode=all + 已注入
  → 共享 CloudProxyProvider；embed 路由不接云网关

注：所有用例经 autouse 夹具隔离 CloudTokenStore 全局单例与
CloudProxyProvider 模块级单例，测试后恢复原状，不污染其它用例。
"""
from __future__ import annotations

import threading
from collections.abc import AsyncIterator

import httpx
import pytest

from app.core.exceptions import ProviderError
from app.runtime.provider.llm.adapters import cloud_proxy as cloud_proxy_module
from app.runtime.provider.llm.adapters.cloud_proxy import CloudProxyProvider, get_cloud_proxy_provider
from app.runtime.provider.llm.adapters.common import classify_error
from app.runtime.provider.llm.cloud_store import CloudTokenStore, cloud_token_store
from app.runtime.provider.llm.types import LLMRequest, LLMResponse, StreamEvent

# ── 隔离夹具 ───────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _isolated_cloud_state():
    """每条用例前后清空全局 token store 与 cloud proxy 模块级单例。"""
    cloud_token_store.clear()
    cloud_proxy_module._cloud_proxy_singleton = None
    yield
    cloud_token_store.clear()
    cloud_proxy_module._cloud_proxy_singleton = None


# ── 测试替身 ───────────────────────────────────────────────────────────────────

class _FakeProvider:
    """记录调用的假 provider（直接可调用对象，避开 ABC 强制实现）。"""

    provider_name = "fake"
    default_model = "deepseek-chat"

    def __init__(self):
        self.chat_calls: list[LLMRequest] = []
        self.stream_calls: list[LLMRequest] = []
        self.embed_calls: list[str] = []

    async def chat(self, request: LLMRequest) -> LLMResponse:
        self.chat_calls.append(request)
        return LLMResponse(content=f"echo:{request.model}")

    async def chat_stream(self, request: LLMRequest) -> AsyncIterator[StreamEvent]:
        self.stream_calls.append(request)
        yield StreamEvent("content", {"content": "chunk"})

    async def embed(self, text: str) -> list[float]:
        self.embed_calls.append(text)
        return [0.1, 0.2]

    async def aclose(self) -> None:
        ...


def _make_adapter_with_fake() -> tuple:
    """构造跳过 DB 懒加载的 LLMAdapter，注入记录型假 provider。"""
    from app.runtime.provider.llm.adapter import LLMAdapter

    adapter = LLMAdapter()
    adapter._loaded = True  # 跳过 ensure_providers_loaded 的 DB 加载
    fake = _FakeProvider()
    adapter.providers["fake"] = fake
    adapter.default_provider = "fake"
    return adapter, fake


# ── CloudTokenStore ────────────────────────────────────────────────────────────

class TestCloudTokenStore:
    def test_default_state(self):
        store = CloudTokenStore()
        assert store.configured is False
        assert store.get() == {"accessToken": "", "cloudBaseUrl": "", "routingMode": "off"}

    def test_set_get_clear_roundtrip(self):
        store = CloudTokenStore()
        store.set("cloud_fake_token_abcd", "http://127.0.0.1:18999/", "all")
        assert store.configured is True
        snap = store.get()
        assert snap["accessToken"] == "cloud_fake_token_abcd"
        # 尾部斜杠被归一化掉
        assert snap["cloudBaseUrl"] == "http://127.0.0.1:18999"
        assert snap["routingMode"] == "all"

        store.clear()
        assert store.configured is False
        assert store.get()["accessToken"] == ""
        assert store.get()["routingMode"] == "off"

    def test_invalid_routing_mode_normalized_to_off(self):
        store = CloudTokenStore()
        store.set("t", "http://127.0.0.1:18999", "bogus")
        assert store.get()["routingMode"] == "off"

    def test_configured_requires_both_fields(self):
        store = CloudTokenStore()
        store.set("token-only", "", "all")
        assert store.configured is False
        store.set("", "http://127.0.0.1:18999", "all")
        assert store.configured is False

    def test_concurrent_set_get_clear_no_error(self):
        """多线程并发 set/get/clear：无异常、无死锁，快照三字段相互一致。"""
        store = CloudTokenStore()
        errors: list[Exception] = []

        def worker(i: int):
            try:
                for j in range(200):
                    mode = "all" if (j % 3 == 0) else "off"
                    store.set(f"tok-{i}-{j}", f"http://host-{i}:{18000 + j}", mode)
                    snap = store.get()
                    assert snap["routingMode"] in ("off", "all")
                    assert isinstance(snap["accessToken"], str)
                    _ = store.configured
                    if j % 50 == 0:
                        store.clear()
            except Exception as e:  # pragma: no cover - 仅在线程异常时触发
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert errors == []
        store.set("final-token-7777", "http://127.0.0.1:18999", "all")
        assert store.configured is True
        assert store.get()["accessToken"] == "final-token-7777"


# ── CloudProxyProvider ─────────────────────────────────────────────────────────

def _make_proxy_with_transport(handler) -> CloudProxyProvider:
    """构造挂在 MockTransport 上的 CloudProxyProvider（保留错误透传 hook）。"""
    store = CloudTokenStore()
    store.set("cloud_fake_first_token_1111", "http://127.0.0.1:18999", "all")
    provider = CloudProxyProvider(store=store)
    provider._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        event_hooks={"response": [provider._raise_for_cloud_error]},
    )
    return provider


class TestCloudProxyProvider:
    def test_base_url_follows_store_live(self):
        store = CloudTokenStore()
        store.set("t", "http://127.0.0.1:18999", "all")
        provider = CloudProxyProvider(store=store)
        assert provider.base_url == "http://127.0.0.1:18999/api/v1/llm"
        # 重新注入新地址后实时跟随（不固化）
        store.set("t2", "http://127.0.0.1:19001", "all")
        assert provider.base_url == "http://127.0.0.1:19001/api/v1/llm"

    def test_build_headers_take_latest_token(self):
        """两次注入不同 token → _build_headers 返回不同 Authorization（实时取，不固化）。"""
        store = CloudTokenStore()
        provider = CloudProxyProvider(store=store)

        store.set("cloud_fake_aaaa_token_1111", "http://127.0.0.1:18999", "all")
        headers_1 = provider._build_headers()
        assert headers_1["Authorization"] == "Bearer cloud_fake_aaaa_token_1111"
        rid_1 = headers_1["X-LMC-Request-Id"]

        store.set("cloud_fake_bbbb_token_2222", "http://127.0.0.1:18999", "all")
        headers_2 = provider._build_headers()
        assert headers_2["Authorization"] == "Bearer cloud_fake_bbbb_token_2222"
        assert headers_1["Authorization"] != headers_2["Authorization"]
        # 幂等键每请求唯一
        assert headers_2["X-LMC-Request-Id"] != rid_1
        assert len(headers_2["X-LMC-Request-Id"]) == 36  # uuid4

    def test_build_headers_raises_without_token(self):
        store = CloudTokenStore()
        provider = CloudProxyProvider(store=store)
        with pytest.raises(ProviderError) as ei:
            provider._build_headers()
        assert ei.value.code == "CLOUD_TOKEN_MISSING"

    async def test_embed_unsupported(self):
        provider = CloudProxyProvider(store=CloudTokenStore())
        with pytest.raises(ProviderError) as ei:
            await provider.embed("hello")
        assert ei.value.code == "CLOUD_EMBED_UNSUPPORTED"

    async def test_chat_sends_live_auth_and_request_id(self):
        """端到端（mock 服务端）：两次请求使用两次注入的不同 token，服务端各见其头。"""
        seen_headers: list[dict] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen_headers.append(dict(request.headers))
            assert request.url.path == "/api/v1/llm/chat/completions"
            return httpx.Response(200, json={
                "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
            })

        provider = _make_proxy_with_transport(handler)
        try:
            resp = await provider.chat(LLMRequest(messages=[{"role": "user", "content": "hi"}], model="deepseek-chat"))
            assert resp.content == "ok"

            # 模拟 30 分钟轮换：重新注入不同 token
            provider._store.set("cloud_fake_rotated_token_9999", "http://127.0.0.1:18999", "all")
            await provider.chat(LLMRequest(messages=[{"role": "user", "content": "hi"}], model="deepseek-chat"))
        finally:
            await provider._client.aclose()

        assert len(seen_headers) == 2
        assert seen_headers[0]["authorization"] == "Bearer cloud_fake_first_token_1111"
        assert seen_headers[1]["authorization"] == "Bearer cloud_fake_rotated_token_9999"
        assert seen_headers[0]["x-lmc-request-id"] != seen_headers[1]["x-lmc-request-id"]

    async def test_chat_error_passthrough_429(self):
        """上游 429 QUOTA_EXCEEDED → ProviderError 携带 errCode/message，且不可重试。"""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json={"errCode": "QUOTA_EXCEEDED", "message": "今日免费额度已用尽"})

        provider = _make_proxy_with_transport(handler)
        try:
            with pytest.raises(ProviderError) as ei:
                await provider.chat(LLMRequest(messages=[{"role": "user", "content": "hi"}], model="deepseek-chat"))
        finally:
            await provider._client.aclose()

        assert ei.value.status_code == 429
        assert ei.value.code == "CLOUD_UPSTREAM_ERROR"
        assert "QUOTA_EXCEEDED" in ei.value.message
        assert "今日免费额度已用尽" in ei.value.message
        # 确定性额度错误不应被 classify_error 判为可重试（避免重复触发计费预检）
        retriable, _ = classify_error(ei.value)
        assert retriable is False

    async def test_chat_stream_error_passthrough_429(self):
        """SSE 流式：上游 429 在流建立阶段抛 ProviderError（含 errCode）。"""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json={"errCode": "QUOTA_EXCEEDED", "message": "今日免费额度已用尽"})

        provider = _make_proxy_with_transport(handler)
        try:
            with pytest.raises(ProviderError) as ei:
                async for _ in provider.chat_stream(
                    LLMRequest(messages=[{"role": "user", "content": "hi"}], model="deepseek-chat")
                ):
                    pass
        finally:
            await provider._client.aclose()

        assert ei.value.status_code == 429
        assert "QUOTA_EXCEEDED" in ei.value.message

    async def test_chat_stream_success(self):
        """SSE 流式成功路径：content 事件与 done 事件正常透出。"""
        sse_body = (
            b'data: {"choices":[{"delta":{"content":"hello"}}]}\n\n'
            b"data: [DONE]\n\n"
        )

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.headers["authorization"] == "Bearer cloud_fake_first_token_1111"
            return httpx.Response(200, content=sse_body)

        provider = _make_proxy_with_transport(handler)
        try:
            events = [
                (e.type, e.data)
                async for e in provider.chat_stream(
                    LLMRequest(messages=[{"role": "user", "content": "hi"}], model="deepseek-chat")
                )
            ]
        finally:
            await provider._client.aclose()

        types = [t for t, _ in events]
        assert "content" in types
        assert types[-1] == "done"
        content = next(d for t, d in events if t == "content")
        assert content["content"] == "hello"

    def test_lazy_singleton_identity_and_live_store(self):
        """共享单例懒建且幂等；base_url 实时跟随全局 store 重新注入。"""
        assert cloud_proxy_module._cloud_proxy_singleton is None
        p1 = get_cloud_proxy_provider()
        p2 = get_cloud_proxy_provider()
        assert p1 is p2

        cloud_token_store.set("t", "http://127.0.0.1:18999", "all")
        assert p1.base_url == "http://127.0.0.1:18999/api/v1/llm"
        cloud_token_store.set("t", "http://127.0.0.1:19001", "all")
        assert p1.base_url == "http://127.0.0.1:19001/api/v1/llm"


# ── LLMAdapter 路由钩子 ────────────────────────────────────────────────────────

@pytest.fixture()
def fake_cloud_factory(monkeypatch):
    """把 adapter 命名空间里的共享单例工厂替换为记录型假 provider 工厂。"""
    fake_cloud = _FakeProvider()
    calls = {"count": 0}

    def factory():
        calls["count"] += 1
        return fake_cloud

    monkeypatch.setattr("app.runtime.provider.llm.adapter.get_cloud_proxy_provider", factory)
    return fake_cloud, calls


class TestAdapterCloudRouting:
    async def test_mode_off_uses_original_provider(self, fake_cloud_factory):
        """未注入（默认 off）→ 原路由不动，云工厂不被调用。"""
        adapter, fake = _make_adapter_with_fake()
        fake_cloud, calls = fake_cloud_factory

        result = await adapter.chat([{"role": "user", "content": "hi"}])
        assert result == "echo:deepseek-chat"
        assert len(fake.chat_calls) == 1
        assert calls["count"] == 0

        chunks = [c async for c in adapter.chat_stream([{"role": "user", "content": "hi"}])]
        assert chunks[0].type == "content"
        assert len(fake.stream_calls) == 1
        assert calls["count"] == 0

    async def test_mode_off_with_token_uses_original_provider(self, fake_cloud_factory):
        """已注入但 mode=off → 仍走原 provider。"""
        cloud_token_store.set("cloud_fake_token_abcd", "http://127.0.0.1:18999", "off")
        adapter, fake = _make_adapter_with_fake()
        _, calls = fake_cloud_factory

        await adapter.chat([{"role": "user", "content": "hi"}])
        assert len(fake.chat_calls) == 1
        assert calls["count"] == 0

    async def test_mode_all_routes_chat_to_cloud_proxy(self, fake_cloud_factory):
        """mode=all + 已注入 → chat 换共享 CloudProxyProvider（工厂产出的替身），model 沿用。"""
        cloud_token_store.set("cloud_fake_token_abcd", "http://127.0.0.1:18999", "all")
        adapter, fake = _make_adapter_with_fake()
        fake_cloud, calls = fake_cloud_factory

        result = await adapter.chat([{"role": "user", "content": "hi"}])
        assert result == "echo:deepseek-chat"  # 假云 provider 的 default_model 同为 deepseek-chat
        assert len(fake.chat_calls) == 0
        assert calls["count"] == 1
        assert len(fake_cloud.chat_calls) == 1
        assert fake_cloud.chat_calls[0].model == "deepseek-chat"

        # 显式指定 model 时同样透传给云端
        await adapter.chat([{"role": "user", "content": "hi"}], model="custom-model")
        assert fake_cloud.chat_calls[-1].model == "custom-model"

    async def test_mode_all_routes_stream_to_cloud_proxy(self, fake_cloud_factory):
        """mode=all + 已注入 → chat_stream 同样换云 provider（SSE 链路）。"""
        cloud_token_store.set("cloud_fake_token_abcd", "http://127.0.0.1:18999", "all")
        adapter, fake = _make_adapter_with_fake()
        fake_cloud, calls = fake_cloud_factory

        chunks = [c async for c in adapter.chat_stream([{"role": "user", "content": "hi"}])]
        assert chunks[0].type == "content"
        assert len(fake.stream_calls) == 0
        assert calls["count"] == 1
        assert len(fake_cloud.stream_calls) == 1

    async def test_embed_not_routed_to_cloud(self, fake_cloud_factory):
        """embed 路由不接云网关：mode=all 时仍走原 provider。"""
        cloud_token_store.set("cloud_fake_token_abcd", "http://127.0.0.1:18999", "all")
        adapter, fake = _make_adapter_with_fake()
        _, calls = fake_cloud_factory

        vec = await adapter.embed("hello")
        assert vec == [0.1, 0.2]
        assert len(fake.embed_calls) == 1
        assert calls["count"] == 0


# ── API 端点（注入 / 状态）─────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def cloud_app():
    """最小化装配：仅 cloud 路由（认证由中间件层负责，不在本用例范围）。"""
    from fastapi import FastAPI

    from app.api.v1.endpoints.cloud import router as cloud_router

    app = FastAPI()
    app.include_router(cloud_router, prefix="/api/v1")
    return app


class TestCloudEndpoints:
    async def test_put_token_then_status(self, cloud_app):
        from httpx import ASGITransport, AsyncClient

        token = "cloud_fake_secret_token_4321"
        async with AsyncClient(transport=ASGITransport(app=cloud_app), base_url="http://test") as client:
            resp = await client.put("/api/v1/cloud/token", json={
                "accessToken": token,
                "cloudBaseUrl": "http://127.0.0.1:18999",
                "routingMode": "all",
            })
            assert resp.status_code == 200
            body = resp.json()
            assert body["code"] == 0
            assert body["data"]["configured"] is True

            status = await client.get("/api/v1/cloud/status")
            assert status.status_code == 200
            data = status.json()["data"]
            assert data["configured"] is True
            assert data["routingMode"] == "all"
            assert data["cloudBaseUrl"] == "http://127.0.0.1:18999"
            assert data["tokenTail4"] == "4321"
            # 绝不回显完整 token
            assert token not in status.text

    async def test_status_default_when_not_configured(self, cloud_app):
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(transport=ASGITransport(app=cloud_app), base_url="http://test") as client:
            status = await client.get("/api/v1/cloud/status")
            data = status.json()["data"]
            assert data["configured"] is False
            assert data["routingMode"] == "off"
            assert data["cloudBaseUrl"] is None
            assert data["tokenTail4"] is None

    async def test_put_token_overwrites(self, cloud_app):
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(transport=ASGITransport(app=cloud_app), base_url="http://test") as client:
            await client.put("/api/v1/cloud/token", json={
                "accessToken": "cloud_fake_old_token_aaaa",
                "cloudBaseUrl": "http://127.0.0.1:18999",
                "routingMode": "all",
            })
            await client.put("/api/v1/cloud/token", json={
                "accessToken": "cloud_fake_new_token_bbbb",
                "cloudBaseUrl": "http://127.0.0.1:19001",
                "routingMode": "off",
            })
            data = (await client.get("/api/v1/cloud/status")).json()["data"]
            assert data["tokenTail4"] == "bbbb"
            assert data["cloudBaseUrl"] == "http://127.0.0.1:19001"
            assert data["routingMode"] == "off"

    async def test_put_token_rejects_invalid_mode(self, cloud_app):
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(transport=ASGITransport(app=cloud_app), base_url="http://test") as client:
            resp = await client.put("/api/v1/cloud/token", json={
                "accessToken": "t",
                "cloudBaseUrl": "http://127.0.0.1:18999",
                "routingMode": "sometimes",
            })
            assert resp.status_code == 422
            assert cloud_token_store.configured is False
