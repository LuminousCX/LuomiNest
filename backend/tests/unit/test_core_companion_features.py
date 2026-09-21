"""针对 LuomiNest 陪伴中心大模型对接与核心工具增强的单元测试。

覆盖：
1. 基础伴侣工具（get_current_time, query_weather）
2. Mem0 记忆显式工具（memory_add, memory_forget, memory_update, memory_search 权限绕过）
3. 工具探索分类过滤（explore_tools category）
4. 浏览器只读标签页与截图工具格式化
5. AgentRunner 多模态截图注入
6. 平台工具扩展与跨平台桥接（platform_invoke）
7. MQTT IoT 传感器遥测与硬件控制工具
"""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.tools.builtin.basic_tools import GetCurrentTimeTool, QuickWeatherTool
from app.core.tools.builtin.memory_tools import MemoryAddTool, MemoryForgetTool, MemoryUpdateTool
from app.core.tools.builtin.memory_search_tool import LuomiNestMemorySearchTool
from app.core.tools.builtin.explore_tools import ToolExploreTool
from app.core.tools.registry import tool_registry
from app.core.tools.builtin.browser_automation import (
    BROWSER_ACTION_SPECS,
    _format_output,
    get_luominest_browser_automation_tools,
)
from app.core.tools.builtin.platform_bridge_tool import PlatformInvokeTool
from app.core.tools.builtin.mqtt_iot_tool import IoTGetSensorDataTool, IoTSendCommandTool
from app.core.agents.middleware.base import AgentContext
from app.core.agents.middleware.pipeline import MiddlewarePipeline
from app.core.agents.middleware.runner import AgentRunner


@pytest.mark.asyncio
async def test_basic_tools():
    # 1. 时间查询
    time_tool = GetCurrentTimeTool()
    res = await time_tool.execute({})
    assert res.success is True
    assert "当前时间" in res.output or "星期" in res.output

    # 2. 天气查询（mock httpx 网络请求）
    weather_tool = QuickWeatherTool()
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "晴 +22°C, 湿度: 55%, 风力: 12km/h"
        mock_get.return_value = mock_resp
        w_res = await weather_tool.execute({"city": "北京"})
        assert w_res.success is True
        assert "北京" in w_res.output
        assert "22°C" in w_res.output


@pytest.mark.asyncio
async def test_tool_explore_category_filter():
    explore = ToolExploreTool()
    # 注册测试工具以供探索
    tool_registry.register(MemoryAddTool())
    tool_registry.register(GetCurrentTimeTool())

    # 分类查看 memory
    res_mem = await explore.execute({"category": "memory"})
    assert res_mem.success is True
    assert "memory_add" in res_mem.output

    # 全览
    res_all = await explore.execute({})
    assert res_all.success is True
    assert "日常轻量工具" in res_all.output
    assert "记忆系统工具" in res_all.output


@pytest.mark.asyncio
async def test_memory_tools():
    # 测试 memory_search 在未设置 contextvar 时不抛出权限拒绝
    search_tool = LuomiNestMemorySearchTool()
    mock_engine = MagicMock()
    mock_fact = MagicMock()
    mock_fact.id = "f1"
    mock_fact.content = "主人喜欢喝乌龙茶"
    mock_fact.category = "preference"
    mock_fact.confidence = 0.9
    mock_fact.pinned = False
    mock_fact.is_latest = True
    mock_fact.created_at = "2026-09-21"
    mock_fact.expired_at = None
    mock_fact.expires_at = None

    mock_scored = MagicMock()
    mock_scored.fact_id = "f1"
    mock_scored.score = 0.95

    mock_engine.vector_retrieve = AsyncMock(return_value=[mock_scored])
    mock_data = MagicMock()
    mock_data.facts = [mock_fact]
    mock_engine.load_data.return_value = mock_data

    with patch("app.engines.memory.get_track_engine", return_value=mock_engine):
        res = await search_tool.execute({"query": "乌龙茶"})
        assert res.success is True
        assert "乌龙茶" in res.output

    # 测试 memory_add / memory_forget / memory_update
    mock_engine.write_lock = asyncio.Lock()
    mock_engine.remember_fact = AsyncMock()
    mock_engine.remove_fact = MagicMock(return_value=True)
    mock_engine.update_fact = MagicMock(return_value=True)
    mock_engine.forget_fact_vector = AsyncMock()
    mock_engine.sync_fact_vector = AsyncMock()
    mock_engine.update_data = MagicMock(return_value=True)

    with patch("app.core.tools.builtin.memory_tools._get_engine", return_value=mock_engine):
        add_tool = MemoryAddTool()
        res_add = await add_tool.execute({"content": "测试记忆", "category": "fact"})
        assert res_add.success is True
        assert "测试记忆" in res_add.output

        upd_tool = MemoryUpdateTool()
        res_upd = await upd_tool.execute({"fact_id": "f1", "content": "更新后的记忆"})
        assert res_upd.success is True

        forget_tool = MemoryForgetTool()
        res_del = await forget_tool.execute({"fact_id": "f1"})
        assert res_del.success is True


def test_browser_automation_specs_and_formatter():
    tools = get_luominest_browser_automation_tools()
    tool_names = [t.name for t in tools]
    assert "browser_visit" in tool_names
    assert "browser_screenshot" in tool_names
    assert "browser_get_tabs" in tool_names
    assert "browser_switch_tab" in tool_names

    # 标签页列表格式化
    tabs_data = {
        "tabs": [
            {"id": "tab1", "title": "Bilibili", "url": "https://www.bilibili.com", "active": True},
            {"id": "tab2", "title": "GitHub", "url": "https://github.com", "active": False},
        ]
    }
    fmt = _format_output("browser_get_tabs", tabs_data)
    assert "Bilibili" in fmt
    assert "GitHub" in fmt
    assert "(当前激活)" in fmt


@pytest.mark.asyncio
async def test_platform_bridge_and_adapters():
    # 测试 PlatformInvokeTool 在未找到平台实例时的友好提示
    bridge = PlatformInvokeTool()
    with patch("app.runtime.platform.registry.list_instances", return_value=[]):
        res = await bridge.execute({
            "platform": "qq_onebot",
            "action": "qq.poke",
            "arguments": {"target_type": "friend", "user_id": 12345},
        })
        assert res.success is False
        assert "未检测到正在运行的 [qq_onebot] 平台连接" in res.error

    # 测试当平台实例运行时正常调用
    mock_adapter = MagicMock()
    mock_adapter.execute_platform_tool = AsyncMock(return_value={"success": True, "output": "拍一拍成功"})
    mock_inst = MagicMock()
    mock_inst.name = "QQBot"
    mock_inst.adapter_type = "qq_onebot"
    mock_inst.status.value = "running"
    mock_inst.adapter = mock_adapter

    with patch("app.runtime.platform.registry.list_instances", return_value=[mock_inst]):
        res_ok = await bridge.execute({
            "platform": "qq_onebot",
            "action": "qq.poke",
            "arguments": {"target_type": "friend", "user_id": 12345},
        })
        assert res_ok.success is True
        assert "拍一拍成功" in res_ok.output


@pytest.mark.asyncio
async def test_mqtt_telemetry_and_tools():
    from app.runtime.platform.adapters.mqtt_terminal import MQTTTerminalAdapter

    adapter = MQTTTerminalAdapter()
    # 模拟接收传感器遥测状态上报
    sensor_payload = json.dumps({
        "state": "online",
        "temperature": 24.5,
        "humidity": 60.2,
        "battery": 95,
    }).encode("utf-8")

    await adapter._handle_status("esp32_sensor_01", sensor_payload)
    telemetry = adapter.get_telemetry("esp32_sensor_01")
    assert telemetry["online"] is True
    assert telemetry["telemetry"]["temperature"] == 24.5
    assert telemetry["telemetry"]["humidity"] == 60.2

    # 测试 iot_get_sensor_data 工具
    sensor_tool = IoTGetSensorDataTool()
    mock_inst = MagicMock()
    mock_inst.adapter_type = "mqtt_terminal"
    mock_inst.status.value = "running"
    mock_inst.adapter = adapter

    with patch("app.runtime.platform.registry.list_instances", return_value=[mock_inst]):
        res = await sensor_tool.execute({"device_id": "esp32_sensor_01"})
        assert res.success is True
        data = json.loads(res.output)
        assert data["telemetry"]["temperature"] == 24.5


@pytest.mark.asyncio
async def test_agent_runner_vision_screenshot_injection():
    # 测试 AgentRunner 在工具返回截图时，自动注入 user 视觉多模态消息
    pipeline = MiddlewarePipeline([])
    fake_tool_result = {
        "role": "tool",
        "tool_call_id": "call_1",
        "name": "browser_visit",
        "content": "已导航到页面",
        "metadata": {"screenshot": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg=="},
    }

    execute_fn = AsyncMock(return_value=fake_tool_result)
    runner = AgentRunner(pipeline=pipeline, max_iterations=2, execute_fn=execute_fn)

    ctx = AgentContext(
        messages=[{"role": "user", "content": "看下这个页面"}],
        extra={"supports_vision": True},
    )

    # 模拟非流式 LLM 调用：第 1 轮产生 tool_call，第 2 轮结束
    call_count = 0
    async def mock_llm_call(context):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "browser_visit", "arguments": "{}"},
                    }
                ],
            }
        else:
            return {"content": "我看到了页面画面。"}

    res_state = await runner.run_non_stream(ctx, mock_llm_call)
    assert res_state["content"] == "我看到了页面画面。"

    # 验证 messages 中是否注入了视觉图片消息
    user_vision_msgs = [
        m for m in ctx.messages
        if m.get("role") == "user" and isinstance(m.get("content"), list)
    ]
    assert len(user_vision_msgs) == 1
    content_parts = user_vision_msgs[0]["content"]
    assert any(p.get("type") == "image_url" for p in content_parts)
    assert content_parts[1]["image_url"]["url"] == "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg=="
