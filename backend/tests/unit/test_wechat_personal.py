import asyncio
import json
import pytest
from unittest.mock import AsyncMock, patch

from app.runtime.platform.adapters.wechat_personal import LuomiNestWeChatPersonalAdapter
from app.runtime.platform.base import AdapterStatus, PlatformMessage, PlatformResponse


@pytest.fixture
def wechat_adapter():
    adapter = LuomiNestWeChatPersonalAdapter()
    adapter.set_instance_id("inst_wx_test")
    adapter.initialize({
        "api_url": "http://127.0.0.1:2531/v2/api",
        "token": "",
        "app_id": "test_wx_app",
        "mock_mode": True,  # 测试使用模拟沙盒模式
        "typing_delay_enabled": False,
        "rate_limit_per_minute": 10,
    })
    return adapter


@pytest.mark.asyncio
async def test_wechat_qr_lifecycle(wechat_adapter):
    # 1. 获取登录二维码
    qr_res = await wechat_adapter.fetch_login_qrcode()
    assert qr_res["status"] == "waiting_scan"
    assert "data:image/svg+xml" in qr_res["qr_data"]
    assert qr_res["uuid"].startswith("qr_")

    # 2. 检查扫码状态 (初始为 waiting_scan)
    status_res = await wechat_adapter.check_login_status(qr_res["uuid"])
    assert status_res["status"] == "waiting_scan"


@pytest.mark.asyncio
async def test_wechat_send_message_mock(wechat_adapter):
    resp = PlatformResponse(content="你好，微信！")
    success = await wechat_adapter.send_message(resp, "filehelper")
    assert success is True


@pytest.mark.asyncio
async def test_wechat_webhook_handling(wechat_adapter):
    received_msgs = []

    async def mock_handler(msg: PlatformMessage, instance_id: str):
        received_msgs.append(msg)
        return PlatformResponse(content="收到！")

    wechat_adapter.set_message_handler(mock_handler)

    # 模拟群消息回调
    mock_webhook_body = {
        "TypeName": "AddMsg",
        "Data": {
            "FromUserName": {"string": "12345678@chatroom"},
            "ToUserName": {"string": "wxid_bot"},
            "Content": {"string": "wxid_user123:\n大家好！"},
            "MsgType": 1,
            "NewMsgId": 88888,
        },
    }

    res = await wechat_adapter.handle_webhook(mock_webhook_body)
    assert res.get("status") == "processed"
    assert len(received_msgs) == 1
    assert received_msgs[0].is_group is True
    assert received_msgs[0].user_id == "wxid_user123"
    assert received_msgs[0].content == "大家好！"


@pytest.mark.asyncio
async def test_wechat_tools(wechat_adapter):
    tools = wechat_adapter.available_tools
    tool_names = [t["function"]["name"] for t in tools]
    assert "wechat.send_image" in tool_names
    assert "wechat.revoke_msg" in tool_names

    res = await wechat_adapter.execute_platform_tool("wechat.send_image", {"target": "filehelper", "image_url": "http://img.png"})
    assert res["success"] is True
