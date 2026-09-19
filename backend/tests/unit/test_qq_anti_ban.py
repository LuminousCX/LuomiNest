import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.runtime.platform.adapters.qq_onebot import LuomiNestQQOneBotAdapter
from app.runtime.platform.base import PlatformMessage, PlatformResponse


@pytest.fixture
def qq_adapter():
    adapter = LuomiNestQQOneBotAdapter()
    adapter.set_instance_id("inst_qq_test")
    adapter.initialize({
        "ws_host": "127.0.0.1",
        "ws_port": 8080,
        "anti_ban_enabled": True,
        "typing_delay_enabled": False,  # 单元测试禁用实际 sleep 加速执行
        "rate_limit_per_minute": 5,
        "send_input_status": True,
    })
    return adapter


@pytest.mark.asyncio
async def test_qq_adapter_init(qq_adapter):
    assert qq_adapter.platform_name == "qq_onebot"
    assert qq_adapter._anti_ban_enabled is True
    assert qq_adapter._rate_limit_per_minute == 5
    assert len(qq_adapter.available_tools) == 5


@pytest.mark.asyncio
async def test_qq_adapter_rate_limit(qq_adapter):
    target = "12345678"
    # 前 5 次应该通过
    for _ in range(5):
        assert qq_adapter._check_rate_limit(target) is True
    # 第 6 次应该被限流拒绝
    assert qq_adapter._check_rate_limit(target) is False


@pytest.mark.asyncio
async def test_qq_adapter_available_tools(qq_adapter):
    tools = qq_adapter.available_tools
    tool_names = [t["function"]["name"] for t in tools]
    assert "qq.poke" in tool_names
    assert "qq.delete_msg" in tool_names
    assert "qq.set_group_ban" in tool_names
    assert "qq.send_like" in tool_names
    assert "qq.get_group_member_list" in tool_names


@pytest.mark.asyncio
async def test_qq_adapter_call_action_echo(qq_adapter):
    # 模拟 WebSocket 连接
    mock_ws = AsyncMock()
    qq_adapter._connections["test_conn"] = mock_ws

    async def simulate_response():
        await asyncio.sleep(0.05)
        # 查找发出的 echo
        sent_call = mock_ws.send.call_args
        assert sent_call is not None
        payload = json.loads(sent_call[0][0])
        echo = payload.get("echo")
        # 模拟 OneBot 回执
        await qq_adapter._handle_onebot_event({"status": "ok", "retcode": 0, "data": {"user_id": 123}, "echo": echo}, mock_ws)

    task = asyncio.create_task(simulate_response())
    res = await qq_adapter.call_action("get_login_info", {})
    await task
    assert res.get("status") == "ok"
    assert res.get("retcode") == 0


@pytest.mark.asyncio
async def test_qq_adapter_execute_tools(qq_adapter):
    # Mock call_action
    qq_adapter.call_action = AsyncMock(return_value={"status": "ok", "retcode": 0, "data": []})

    # 测试拍一拍
    poke_res = await qq_adapter.execute_platform_tool("qq.poke", {"target_type": "group", "group_id": "111", "user_id": "222"})
    assert poke_res["success"] is True
    qq_adapter.call_action.assert_called_with("group_poke", {"group_id": 111, "user_id": 222})

    # 测试禁言
    ban_res = await qq_adapter.execute_platform_tool("qq.set_group_ban", {"group_id": "111", "user_id": "222", "duration": 120})
    assert ban_res["success"] is True
    qq_adapter.call_action.assert_called_with("set_group_ban", {"group_id": 111, "user_id": 222, "duration": 120})

    # 测试撤回
    del_res = await qq_adapter.execute_platform_tool("qq.delete_msg", {"message_id": "999"})
    assert del_res["success"] is True
    qq_adapter.call_action.assert_called_with("delete_msg", {"message_id": 999})
