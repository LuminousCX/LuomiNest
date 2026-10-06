"""Telegram 适配器单元测试。"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.runtime.platform.adapters.telegram import (
    TELEGRAM_LONG_POLL_TIMEOUT,
    TELEGRAM_MAX_MESSAGE_LENGTH,
    TelegramAdapter,
)
from app.runtime.platform.base import AdapterStatus, PlatformResponse
from app.runtime.platform.infrastructure.truncation import TruncateMode


# ─── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def adapter() -> TelegramAdapter:
    """创建一个已初始化但未启动的适配器实例。"""
    a = TelegramAdapter()
    a.initialize({
        "bot_token": "test_token_123",
        "polling_interval": 1,
        "use_webhook": False,
        "webhook_url": "",
        "allowed_users": "",
    })
    return a


@pytest.fixture
def adapter_with_users() -> TelegramAdapter:
    """创建带用户白名单的适配器实例。"""
    a = TelegramAdapter()
    a.initialize({
        "bot_token": "test_token_123",
        "allowed_users": "111,222,333",
    })
    return a


def make_telegram_update(
    text: str = "",
    user_id: int = 100,
    chat_id: int = 100,
    chat_type: str = "private",
    message_id: int = 1,
    first_name: str = "Test",
    last_name: str = "User",
    photo: list[dict] | None = None,
    reply_to_message: dict | None = None,
    entities: list[dict] | None = None,
) -> dict[str, Any]:
    """构造 Telegram Update 对象。"""
    message: dict[str, Any] = {
        "message_id": message_id,
        "from": {
            "id": user_id,
            "first_name": first_name,
            "last_name": last_name,
            "is_bot": False,
        },
        "chat": {
            "id": chat_id,
            "type": chat_type,
        },
        "date": 1700000000,
    }
    if text:
        message["text"] = text
    if photo:
        message["photo"] = photo
    if reply_to_message:
        message["reply_to_message"] = reply_to_message
    if entities:
        message["entities"] = entities
    return {"update_id": 1, "message": message}


# ─── 配置测试 ──────────────────────────────────────────────────


class TestConfig:
    """配置模板和元数据测试。"""

    def test_config_template_has_all_keys(self) -> None:
        expected = {"bot_token", "polling_interval", "use_webhook", "webhook_url", "allowed_users"}
        assert set(TelegramAdapter.config_template.keys()) == expected

    def test_config_metadata_has_all_keys(self) -> None:
        expected = {"bot_token", "polling_interval", "use_webhook", "webhook_url", "allowed_users"}
        assert set(TelegramAdapter.config_metadata.keys()) == expected

    def test_bot_token_is_required(self) -> None:
        assert TelegramAdapter.config_metadata["bot_token"]["required"] is True

    def test_bot_token_is_sensitive(self) -> None:
        assert TelegramAdapter.config_metadata["bot_token"]["sensitive"] is True

    def test_polling_interval_default(self) -> None:
        assert TelegramAdapter.config_metadata["polling_interval"]["default"] == 1

    def test_platform_name(self) -> None:
        assert TelegramAdapter.platform_name == "telegram"


# ─── 初始化测试 ────────────────────────────────────────────────


class TestInitialize:
    """初始化逻辑测试。"""

    def test_initialize_sets_base_url(self, adapter: TelegramAdapter) -> None:
        assert adapter._base_url == "https://api.telegram.org/bottest_token_123"

    def test_initialize_parses_allowed_users(self, adapter_with_users: TelegramAdapter) -> None:
        assert adapter_with_users._allowed_users == {"111", "222", "333"}

    def test_initialize_empty_allowed_users(self, adapter: TelegramAdapter) -> None:
        assert adapter._allowed_users == set()


# ─── handle_update 测试 ────────────────────────────────────────


class TestHandleUpdate:
    """消息接收与转换测试。"""

    @pytest.mark.asyncio
    async def test_text_message_private(self, adapter: TelegramAdapter) -> None:
        update = make_telegram_update(text="hello", user_id=42, chat_type="private")
        msg = await adapter.handle_update(update)
        assert msg is not None
        assert msg.platform == "telegram"
        assert msg.user_id == "42"
        assert msg.content == "hello"
        assert msg.is_group is False
        assert msg.session_id == "42"
        assert msg.sender_name == "Test User"

    @pytest.mark.asyncio
    async def test_text_message_group(self, adapter: TelegramAdapter) -> None:
        update = make_telegram_update(
            text="hi group", user_id=42, chat_id=-100, chat_type="group"
        )
        # 群聊需要被 @ 或回复，否则返回 None
        msg = await adapter.handle_update(update)
        assert msg is None  # 没有被 @ 所以不响应

    @pytest.mark.asyncio
    async def test_no_message_returns_none(self, adapter: TelegramAdapter) -> None:
        update = {"update_id": 1}  # 没有 message 字段
        msg = await adapter.handle_update(update)
        assert msg is None

    @pytest.mark.asyncio
    async def test_empty_message_returns_none(self, adapter: TelegramAdapter) -> None:
        update = make_telegram_update(text="")
        msg = await adapter.handle_update(update)
        assert msg is None

    @pytest.mark.asyncio
    async def test_photo_message(self, adapter: TelegramAdapter) -> None:
        photo = [
            {"file_id": "small_id", "width": 90, "height": 90},
            {"file_id": "large_id", "width": 800, "height": 600},
        ]
        update = make_telegram_update(text="caption", photo=photo)
        msg = await adapter.handle_update(update)
        assert msg is not None
        assert len(msg.image_urls) == 1
        assert msg.image_urls[0] == "telegram_file://large_id"

    @pytest.mark.asyncio
    async def test_photo_only_no_text(self, adapter: TelegramAdapter) -> None:
        photo = [{"file_id": "pic_id", "width": 100, "height": 100}]
        update = make_telegram_update(text="", photo=photo)
        msg = await adapter.handle_update(update)
        assert msg is not None
        assert msg.content == ""
        assert msg.image_urls == ["telegram_file://pic_id"]

    @pytest.mark.asyncio
    async def test_user_whitelist_filter(self, adapter_with_users: TelegramAdapter) -> None:
        # 允许的用户
        update = make_telegram_update(text="ok", user_id=111)
        msg = await adapter_with_users.handle_update(update)
        assert msg is not None

        # 不允许的用户
        update = make_telegram_update(text="blocked", user_id=999)
        msg = await adapter_with_users.handle_update(update)
        assert msg is None

    @pytest.mark.asyncio
    async def test_group_reply_to_bot(self, adapter: TelegramAdapter) -> None:
        adapter._bot_id = "555"
        reply_to = {"from": {"id": 555}, "message_id": 10}
        update = make_telegram_update(
            text="reply to bot", chat_id=-100, chat_type="group",
            reply_to_message=reply_to,
        )
        msg = await adapter.handle_update(update)
        assert msg is not None
        assert msg.is_group is True
        assert msg.group_id == "-100"
        assert msg.session_id == "-100"

    @pytest.mark.asyncio
    async def test_group_reply_to_other_user(self, adapter: TelegramAdapter) -> None:
        adapter._bot_id = "555"
        reply_to = {"from": {"id": 999}, "message_id": 10}
        update = make_telegram_update(
            text="reply to other", chat_id=-100, chat_type="group",
            reply_to_message=reply_to,
        )
        msg = await adapter.handle_update(update)
        assert msg is None  # 回复的不是 bot

    @pytest.mark.asyncio
    async def test_voice_message_logged(self, adapter: TelegramAdapter) -> None:
        update = make_telegram_update(text="")
        update["message"]["voice"] = {"file_id": "voice_id", "duration": 5}
        # voice 只有、没有 text 和 photo 时返回 None
        msg = await adapter.handle_update(update)
        assert msg is None


# ─── send_message 测试 ─────────────────────────────────────────


class TestSendMessage:
    """消息发送测试。"""

    @pytest.mark.asyncio
    async def test_send_without_client_returns_false(self, adapter: TelegramAdapter) -> None:
        response = PlatformResponse(content="test")
        result = await adapter.send_message(response, "chat:123")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_text_message(self, adapter: TelegramAdapter) -> None:
        adapter._http_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"ok": True, "result": {}}
        mock_resp.raise_for_status = MagicMock()
        adapter._http_client.post = AsyncMock(return_value=mock_resp)

        response = PlatformResponse(content="hello world")
        result = await adapter.send_message(response, "chat:123")
        assert result is True
        adapter._http_client.post.assert_called_once()
        call_args = adapter._http_client.post.call_args
        assert call_args[0][0] == "sendMessage"
        assert call_args[1]["json"]["text"] == "hello world"
        assert call_args[1]["json"]["chat_id"] == "123"

    @pytest.mark.asyncio
    async def test_send_with_reply(self, adapter: TelegramAdapter) -> None:
        adapter._http_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"ok": True, "result": {}}
        mock_resp.raise_for_status = MagicMock()
        adapter._http_client.post = AsyncMock(return_value=mock_resp)

        response = PlatformResponse(content="reply", reply_to="42")
        result = await adapter.send_message(response, "chat:123")
        assert result is True
        call_args = adapter._http_client.post.call_args
        assert call_args[1]["json"]["reply_parameters"] == {"message_id": 42}

    @pytest.mark.asyncio
    async def test_send_photo(self, adapter: TelegramAdapter) -> None:
        adapter._http_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"ok": True, "result": {}}
        mock_resp.raise_for_status = MagicMock()
        adapter._http_client.post = AsyncMock(return_value=mock_resp)

        response = PlatformResponse(content="", image_urls=["https://example.com/img.png"])
        result = await adapter.send_message(response, "chat:123")
        assert result is True
        call_args = adapter._http_client.post.call_args
        assert call_args[0][0] == "sendPhoto"
        assert call_args[1]["json"]["photo"] == "https://example.com/img.png"

    @pytest.mark.asyncio
    async def test_send_telegram_file_photo(self, adapter: TelegramAdapter) -> None:
        adapter._http_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"ok": True, "result": {}}
        mock_resp.raise_for_status = MagicMock()
        adapter._http_client.post = AsyncMock(return_value=mock_resp)

        response = PlatformResponse(content="", image_urls=["telegram_file://abc123"])
        result = await adapter.send_message(response, "chat:123")
        assert result is True
        call_args = adapter._http_client.post.call_args
        assert call_args[1]["json"]["photo"] == "abc123"

    @pytest.mark.asyncio
    async def test_parse_target_with_prefix(self) -> None:
        assert TelegramAdapter._parse_target("chat:12345") == "12345"

    @pytest.mark.asyncio
    async def test_parse_target_plain(self) -> None:
        assert TelegramAdapter._parse_target("12345") == "12345"


# ─── 截断测试 ──────────────────────────────────────────────────


class TestTruncation:
    """消息截断测试。"""

    def test_short_text_not_truncated(self, adapter: TelegramAdapter) -> None:
        text = "hello"
        result = adapter._truncator.truncate(text, max_length=TELEGRAM_MAX_MESSAGE_LENGTH, mode=TruncateMode.UTF16)
        assert result == text

    def test_long_text_truncated(self, adapter: TelegramAdapter) -> None:
        text = "a" * 5000
        result = adapter._truncator.truncate(text, max_length=TELEGRAM_MAX_MESSAGE_LENGTH, mode=TruncateMode.UTF16)
        # 应该被截断并加上后缀
        assert len(result) < len(text)
        assert result.endswith("...")


# ─── API 请求测试 ──────────────────────────────────────────────


class TestApiRequest:
    """Telegram API 请求测试。"""

    @pytest.mark.asyncio
    async def test_api_request_no_client_raises(self, adapter: TelegramAdapter) -> None:
        with pytest.raises(RuntimeError, match="HTTP 客户端未初始化"):
            await adapter._api_request("getMe")

    @pytest.mark.asyncio
    async def test_api_request_success(self, adapter: TelegramAdapter) -> None:
        adapter._http_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"ok": True, "result": {"id": 123}}
        mock_resp.raise_for_status = MagicMock()
        adapter._http_client.post = AsyncMock(return_value=mock_resp)

        result = await adapter._api_request("getMe")
        assert result == {"id": 123}

    @pytest.mark.asyncio
    async def test_api_request_api_error(self, adapter: TelegramAdapter) -> None:
        adapter._http_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"ok": False, "description": "Bad Request"}
        mock_resp.raise_for_status = MagicMock()
        adapter._http_client.post = AsyncMock(return_value=mock_resp)

        with pytest.raises(RuntimeError, match="Bad Request"):
            await adapter._api_request("sendMessage", {"chat_id": 1, "text": "hi"})

    @pytest.mark.asyncio
    async def test_api_request_network_error(self, adapter: TelegramAdapter) -> None:
        import httpx
        adapter._http_client = AsyncMock()
        adapter._http_client.post = AsyncMock(side_effect=httpx.RequestError("connection failed"))

        with pytest.raises(RuntimeError, match="网络错误"):
            await adapter._api_request("getMe")


# ─── handle_webhook / 入站闭环测试 ────────────────────────────


def _mock_api_client(adapter: TelegramAdapter) -> AsyncMock:
    """给适配器挂一个返回 ok 的 mock Telegram API 客户端。"""
    adapter._http_client = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"ok": True, "result": {}}
    mock_resp.raise_for_status = MagicMock()
    adapter._http_client.post = AsyncMock(return_value=mock_resp)
    return adapter._http_client


async def _drain(adapter: TelegramAdapter) -> None:
    """等待适配器在途后台任务结束（rest_api 同款模式，telegram 当前无后台任务）。"""
    if adapter._poll_task:
        await asyncio.gather(adapter._poll_task, return_exceptions=True)


class TestHandleWebhook:
    """Webhook 入口完整闭环测试（P0-4：入站死路修复回归）。"""

    @pytest.mark.asyncio
    async def test_full_loop_agent_called_and_reply_sent(self, adapter: TelegramAdapter) -> None:
        """模拟入站消息 → 断言 Agent（message handler）被调用 → 断言回复回写 Telegram。"""
        received: list[tuple[Any, str]] = []

        async def fake_agent(message, instance_id):
            received.append((message, instance_id))
            return PlatformResponse(content="agent reply")

        adapter.set_instance_id("inst-tg-1")
        adapter.set_message_handler(fake_agent)
        client = _mock_api_client(adapter)

        update = make_telegram_update(
            text="hello bot", user_id=42, chat_id=42, chat_type="private", message_id=7,
        )
        handled = await adapter.handle_webhook(update)

        # Update 被接受处理
        assert handled is True
        # Agent 被调用，收到转换后的 PlatformMessage
        assert len(received) == 1
        msg, inst_id = received[0]
        assert msg.platform == "telegram"
        assert msg.content == "hello bot"
        assert msg.user_id == "42"
        assert msg.session_id == "42"
        assert msg.message_id == "7"
        assert inst_id == "inst-tg-1"
        # 回复回写 Telegram（sendMessage 到原 chat）
        client.post.assert_called_once()
        call = client.post.call_args
        assert call[0][0] == "sendMessage"
        assert call[1]["json"]["chat_id"] == "42"
        assert call[1]["json"]["text"] == "agent reply"

    @pytest.mark.asyncio
    async def test_filtered_update_returns_false_and_skips_agent(self, adapter_with_users: TelegramAdapter) -> None:
        """白名单外用户的消息被过滤：Agent 不被调用，回写不发生。"""
        handler = AsyncMock(return_value=PlatformResponse(content="should not"))
        adapter_with_users.set_message_handler(handler)
        client = _mock_api_client(adapter_with_users)

        update = make_telegram_update(text="blocked", user_id=999)
        handled = await adapter_with_users.handle_webhook(update)

        assert handled is False
        handler.assert_not_awaited()
        client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_group_message_without_mention_filtered(self, adapter: TelegramAdapter) -> None:
        """群聊消息未被 @ 也未回复 bot：过滤，Agent 不被调用。"""
        handler = AsyncMock(return_value=None)
        adapter.set_message_handler(handler)

        update = make_telegram_update(text="普通群聊", chat_id=-100, chat_type="group")
        assert await adapter.handle_webhook(update) is False
        handler.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_agent_no_response_no_writeback(self, adapter: TelegramAdapter) -> None:
        """Agent 无响应（handler 返回 None）：不回写。"""
        handler = AsyncMock(return_value=None)
        adapter.set_message_handler(handler)
        client = _mock_api_client(adapter)

        update = make_telegram_update(text="hello", user_id=1)
        assert await adapter.handle_webhook(update) is True
        handler.assert_awaited_once()
        client.post.assert_not_called()


# ─── get_target 测试 ─────────────────────────────────────────


class TestGetTarget:
    """get_target 静态方法测试。"""

    def test_get_target_private_chat(self) -> None:
        update = make_telegram_update(text="hi", user_id=42, chat_id=42, chat_type="private")
        target = TelegramAdapter.get_target(update)
        assert target == "chat:42"

    def test_get_target_group_chat(self) -> None:
        update = make_telegram_update(text="hi", chat_id=-100123, chat_type="group")
        target = TelegramAdapter.get_target(update)
        assert target == "chat:-100123"

    def test_get_target_no_message(self) -> None:
        update = {"update_id": 1}
        target = TelegramAdapter.get_target(update)
        assert target == ""

    def test_get_target_no_chat_id(self) -> None:
        update = {"update_id": 1, "message": {"message_id": 1, "from": {"id": 1}}}
        target = TelegramAdapter.get_target(update)
        assert target == ""


# ─── download_image 测试 ─────────────────────────────────────


class TestDownloadImage:
    """download_image 方法测试。"""

    @pytest.mark.asyncio
    async def test_download_image_success(self, adapter: TelegramAdapter) -> None:
        adapter._http_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "ok": True,
            "result": {"file_id": "abc123", "file_path": "photos/file_0.jpg"},
        }
        mock_resp.raise_for_status = MagicMock()
        adapter._http_client.post = AsyncMock(return_value=mock_resp)

        url = await adapter.download_image("abc123")
        assert url is not None
        assert "photos/file_0.jpg" in url
        assert adapter._bot_token in url

    @pytest.mark.asyncio
    async def test_download_image_empty_file_path(self, adapter: TelegramAdapter) -> None:
        adapter._http_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"ok": True, "result": {"file_id": "abc123", "file_path": ""}}
        mock_resp.raise_for_status = MagicMock()
        adapter._http_client.post = AsyncMock(return_value=mock_resp)

        url = await adapter.download_image("abc123")
        assert url is None

    @pytest.mark.asyncio
    async def test_download_image_api_error(self, adapter: TelegramAdapter) -> None:
        adapter._http_client = AsyncMock()
        adapter._http_client.post = AsyncMock(side_effect=RuntimeError("API error"))

        url = await adapter.download_image("abc123")
        assert url is None

    @pytest.mark.asyncio
    async def test_download_image_no_client(self, adapter: TelegramAdapter) -> None:
        url = await adapter.download_image("abc123")
        assert url is None


# ─── 长轮询入站测试 ────────────────────────────────────────────


class TestPollingLoop:
    """getUpdates 长轮询入站闭环测试（P0-4：全仓无轮询调 getUpdates 修复回归）。"""

    @pytest.mark.asyncio
    async def test_polling_processes_updates_and_advances_offset(self, adapter: TelegramAdapter) -> None:
        """轮询拿到 Update → Agent 被调用 → 回复回写；offset 推进到最大 update_id+1。"""
        received: list[Any] = []

        async def fake_agent(message, instance_id):
            received.append(message)
            return PlatformResponse(content=f"reply:{message.content}")

        adapter.set_instance_id("inst-tg-1")
        adapter.set_message_handler(fake_agent)
        client = _mock_api_client(adapter)

        update1 = make_telegram_update(text="first", user_id=42, chat_id=42, message_id=1)
        update1["update_id"] = 101
        update2 = make_telegram_update(text="second", user_id=42, chat_id=42, message_id=2)
        update2["update_id"] = 102

        api_calls: list[tuple[str, dict | None]] = []
        real_api_request = adapter._api_request

        async def fake_api_request(method, params=None, timeout=None):
            api_calls.append((method, params))
            if method == "getUpdates":
                if len(api_calls) == 1:
                    return [update1, update2]
                adapter._stop_polling.set()
                return []
            # 出站（sendMessage 等）走真实实现，落在 mock http 客户端上
            return await real_api_request(method, params, timeout=timeout)

        adapter._api_request = AsyncMock(side_effect=fake_api_request)

        adapter._stop_polling.clear()
        await adapter._polling_loop()

        # Agent 被调用两次，回复依次回写
        assert [m.content for m in received] == ["first", "second"]
        sent_texts = [c[0][0] for c in client.post.call_args_list]
        assert sent_texts == ["sendMessage", "sendMessage"]
        first_call = client.post.call_args_list[0]
        assert first_call[1]["json"]["text"] == "reply:first"
        assert first_call[1]["json"]["chat_id"] == "42"

        # offset 确认：第二次 getUpdates 只拉取 update_id > 102 的更新
        assert adapter._update_offset == 103
        assert api_calls[0][0] == "getUpdates"
        assert api_calls[0][1]["offset"] == 0
        assert api_calls[0][1]["timeout"] == TELEGRAM_LONG_POLL_TIMEOUT
        second_get = [c for c in api_calls if c[0] == "getUpdates"][1]
        assert second_get[1]["offset"] == 103
        # 长轮询请求侧超时需大于服务端挂起时长
        assert adapter._api_request.call_args_list[0].kwargs.get("timeout", None) == TELEGRAM_LONG_POLL_TIMEOUT + 10.0

    @pytest.mark.asyncio
    async def test_polling_survives_handler_exception(self, adapter: TelegramAdapter) -> None:
        """单条 Update 处理失败只记日志：后续 Update 继续处理，循环不断路。"""
        calls = {"n": 0}

        async def flaky_agent(message, instance_id):
            calls["n"] += 1
            if message.content == "boom":
                raise RuntimeError("agent exploded")
            return PlatformResponse(content=f"reply:{message.content}")

        adapter.set_message_handler(flaky_agent)
        client = _mock_api_client(adapter)

        bad = make_telegram_update(text="boom", user_id=42, chat_id=42)
        bad["update_id"] = 1
        good = make_telegram_update(text="fine", user_id=42, chat_id=42)
        good["update_id"] = 2

        api_calls: list[str] = []
        real_api_request = adapter._api_request

        async def fake_api_request(method, params=None, timeout=None):
            api_calls.append(method)
            if method == "getUpdates":
                if len(api_calls) == 1:
                    return [bad, good]
                adapter._stop_polling.set()
                return []
            return await real_api_request(method, params, timeout=timeout)

        adapter._api_request = AsyncMock(side_effect=fake_api_request)
        adapter._stop_polling.clear()
        await adapter._polling_loop()

        # 两条都被投递给 Agent（异常不影响后续处理）
        assert calls["n"] == 2
        # 只有 good 拿到回复
        sent = [c[1]["json"]["text"] for c in client.post.call_args_list]
        assert sent == ["reply:fine"]

    @pytest.mark.asyncio
    async def test_polling_retries_after_network_error(self, adapter: TelegramAdapter) -> None:
        """getUpdates 网络异常：退避后重试，循环不断路。"""
        adapter._polling_interval = 0.01  # 加快退避，避免拖慢用例
        api_calls: list[str] = []

        async def fake_api_request(method, params=None, timeout=None):
            api_calls.append(method)
            if len(api_calls) == 1:
                raise RuntimeError("Telegram API 网络错误: timeout")
            adapter._stop_polling.set()
            return []

        adapter._api_request = AsyncMock(side_effect=fake_api_request)
        adapter._stop_polling.clear()
        await asyncio.wait_for(adapter._polling_loop(), timeout=5)

        assert api_calls.count("getUpdates") == 2


# ─── 生命周期与入站调度模式测试 ────────────────────────────────


class TestLifecycleScheduling:
    """start/stop 的入站调度（长轮询 vs Webhook）测试。"""

    @pytest.mark.asyncio
    async def test_start_polling_mode_starts_poll_task(self, adapter: TelegramAdapter) -> None:
        adapter._http_client = AsyncMock()
        api_methods: list[str] = []

        async def fake_api_request(method, params=None, timeout=None):
            api_methods.append(method)
            if method == "getUpdates":
                adapter._stop_polling.set()
                return []
            return {"id": 555, "username": "test_bot"}

        adapter._api_request = AsyncMock(side_effect=fake_api_request)

        await adapter.start()
        assert adapter._status == AdapterStatus.RUNNING
        assert adapter._poll_task is not None
        # 长轮询模式启动前清掉残留 webhook，避免 getUpdates 409
        assert "deleteWebhook" in api_methods

        # 让轮询任务跑完一轮（fake getUpdates 置位 stop 事件）
        await _drain(adapter)
        assert "getUpdates" in api_methods

        await adapter.stop()
        assert adapter._poll_task is None
        assert adapter._status == AdapterStatus.STOPPED

    @pytest.mark.asyncio
    async def test_start_webhook_mode_registers_and_skips_polling(self) -> None:
        a = TelegramAdapter()
        a.initialize({
            "bot_token": "test_token_123",
            "use_webhook": True,
            "webhook_url": "https://example.com/tg/hook",
        })
        a._http_client = AsyncMock()
        api_calls: list[tuple[str, dict | None]] = []

        async def fake_api_request(method, params=None, timeout=None):
            api_calls.append((method, params))
            if method == "getMe":
                return {"id": 555, "username": "test_bot"}
            return {}

        a._api_request = AsyncMock(side_effect=fake_api_request)

        await a.start()
        assert a._status == AdapterStatus.RUNNING
        # Webhook 模式：注册 setWebhook，不启动长轮询
        set_calls = [c for c in api_calls if c[0] == "setWebhook"]
        assert len(set_calls) == 1
        assert set_calls[0][1]["url"] == "https://example.com/tg/hook"
        assert a._poll_task is None

        await a.stop()
        # 停止时注销 webhook
        assert any(c[0] == "deleteWebhook" for c in api_calls)
        assert a._webhook_registered is False

    @pytest.mark.asyncio
    async def test_execute_platform_tools_use_api_request(self, adapter: TelegramAdapter) -> None:
        """三个平台工具走 _api_request（P0-4：未定义的 _call_api 修复回归）。"""
        adapter._http_client = AsyncMock()
        adapter._api_request = AsyncMock(return_value={})

        cases = [
            ("telegram.send_message", {"chat_id": "42", "text": "hi"}, "sendMessage"),
            ("telegram.delete_message", {"chat_id": "42", "message_id": "1"}, "deleteMessage"),
            ("telegram.pin_message", {"chat_id": "42", "message_id": "2"}, "pinChatMessage"),
        ]
        for tool_name, args, expected_method in cases:
            result = await adapter.execute_platform_tool(tool_name, args)
            assert result["success"] is True, f"{tool_name} 应成功: {result}"
            assert adapter._api_request.call_args[0][0] == expected_method
