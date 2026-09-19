import asyncio
import json
import pytest
from unittest.mock import AsyncMock

from app.runtime.platform.adapters.minecraft import LuomiNestMinecraftAdapter
from app.runtime.platform.base import PlatformMessage, PlatformResponse


@pytest.fixture
def mc_adapter():
    adapter = LuomiNestMinecraftAdapter()
    adapter.set_instance_id("inst_mc_test")
    adapter.initialize({
        "rcon_host": "127.0.0.1",
        "rcon_port": 25575,
        "rcon_password": "",  # 测试无 RCON 模式
        "ws_enabled": True,
        "ws_port": 8081,
        "screenshot_enabled": True,
    })
    return adapter


@pytest.mark.asyncio
async def test_mc_adapter_telemetry_and_tools(mc_adapter):
    tools = mc_adapter.available_tools
    tool_names = [t["function"]["name"] for t in tools]
    assert "mc.navigate" in tool_names
    assert "mc.mine_block" in tool_names
    assert "mc.place_block" in tool_names
    assert "mc.attack" in tool_names
    assert "mc.use_item" in tool_names
    assert "mc.craft" in tool_names
    assert "mc.say" in tool_names
    assert "mc.get_player_state" in tool_names
    assert "mc.request_screenshot" in tool_names


@pytest.mark.asyncio
async def test_mc_telemetry_event_handling(mc_adapter):
    telemetry_data = {
        "type": "telemetry",
        "player": "Steve",
        "position": [100.0, 64.0, 200.0],
        "health": 18,
        "hunger": 20,
        "looking_at": "minecraft:iron_ore",
        "nearby_entities": [{"type": "minecraft:zombie", "distance": 5.0}],
    }
    await mc_adapter._handle_ws_event(telemetry_data)

    state = mc_adapter._player_states.get("Steve")
    assert state is not None
    assert state["health"] == 18
    assert state["position"] == [100.0, 64.0, 200.0]

    # 查询状态工具
    state_tool_res = await mc_adapter.execute_platform_tool("mc.get_player_state", {"player": "Steve"})
    assert state_tool_res["success"] is True
    assert "iron_ore" in state_tool_res["output"]


@pytest.mark.asyncio
async def test_mc_chat_augmentation_with_telemetry(mc_adapter):
    # 先上报环境遥测
    mc_adapter._player_states["Steve"] = {
        "position": [100, 64, 200],
        "health": 20,
        "hunger": 18,
        "looking_at": "minecraft:diamond_ore",
        "nearby_entities": [{"type": "minecraft:zombie"}],
    }

    emitted_msgs = []

    async def mock_handler(msg: PlatformMessage, instance_id: str):
        emitted_msgs.append(msg)
        return PlatformResponse(content="收到，我来帮你！")

    mc_adapter.set_message_handler(mock_handler)

    chat_event = {
        "type": "chat",
        "player": "Steve",
        "message": "帮我看看现在安全吗？",
    }
    await mc_adapter._handle_ws_event(chat_event)

    assert len(emitted_msgs) == 1
    content = emitted_msgs[0].content
    # 验证上下文已被游戏实时环境增强（注入了坐标、注视方块、附近生物）
    assert "游戏实时环境" in content
    assert "diamond_ore" in content
    assert "zombie" in content
    assert "帮我看看现在安全吗？" in content


@pytest.mark.asyncio
async def test_mc_action_dispatch(mc_adapter):
    mock_ws = AsyncMock()
    mc_adapter._ws_connections[123] = mock_ws

    # 模拟下发具身动作
    res = await mc_adapter.execute_platform_tool("mc.navigate", {"x": 100, "y": 64, "z": 200, "player": "Steve"})
    assert res["success"] is True

    sent_raw = mock_ws.send.call_args[0][0]
    payload = json.loads(sent_raw)
    assert payload["type"] == "action"
    assert payload["action"] == "navigate"
    assert payload["params"]["x"] == 100
    assert payload["params"]["y"] == 64
