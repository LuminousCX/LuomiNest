"""Telegram 适配器单元测试。"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.runtime.platform.adapters.telegram import (
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


# ─── handle_webhook 测试 ──────────────────────────────────────


class TestHandleWebhook:
    """Webhook 入口测试。"""

    @pytest.mark.asyncio
    async def test_handle_webhook_delegates(self, adapter: TelegramAdapter) -> None:
        update = make_telegram_update(text="webhook test")
        result = await adapter.handle_webhook(update)
        # handle_webhook 返回 None（它调用 handle_update 但不返回值）
        # 但 handle_update 内部返回了 PlatformMessage
        # handle_webhook 的签名是 async -> None，所以结果是 None
        assert result is None


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
