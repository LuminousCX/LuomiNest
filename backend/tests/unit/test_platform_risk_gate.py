"""W3-3 平台风险闸门单元测试。

覆盖：
- HIGH_RISK_PLATFORM_TOOLS 高风险清单内容
- filter_tools_by_risk 注入面过滤/放行
- _execute_platform_tool 执行侧兜底拦截（mock 适配器，实例开关关/开）

参考 test_qq_anti_ban.py 的构造方式（AsyncMock 模拟适配器）。
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.runtime.platform.base import (
    HIGH_RISK_PLATFORM_TOOLS,
    HIGH_RISK_TOOL_BLOCKED_MESSAGE,
    filter_tools_by_risk,
    get_high_risk_tools_for_platform,
)
from app.runtime.platform.briefings import get_platform_briefing
from app.services.platform_router import LuomiNestPlatformRouter
import app.services.platform_router as platform_router_module


def _tool(name: str) -> dict:
    """构造 OpenAI function schema 格式的工具项。"""
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": f"mock tool {name}",
            "parameters": {"type": "object", "properties": {}},
        },
    }


ALL_QQ_TOOLS = [
    _tool("qq.poke"),
    _tool("qq.kick_group_member"),
    _tool("qq.set_group_whole_ban"),
    _tool("qq.delete_msg"),
    _tool("qq.send_msg"),
]


# ─── 高风险清单 ───


def test_high_risk_set_contents():
    assert isinstance(HIGH_RISK_PLATFORM_TOOLS, frozenset)
    assert HIGH_RISK_PLATFORM_TOOLS == frozenset({
        # qq_onebot（群管理类从全员禁言到精华全覆盖）
        "qq.kick_group_member",
        "qq.set_group_whole_ban",
        "qq.set_group_ban",
        "qq.delete_msg",
        "qq.set_group_card",
        "qq.set_group_special_title",
        "qq.set_essence_msg",
        "qq.delete_essence_msg",
        # discord
        "discord.delete_message",
        "discord.timeout_member",
        # wechat_personal
        "wechat.revoke_msg",
        # telegram
        "telegram.delete_message",
        # minecraft（execute_command 可达 kick/ban/op/stop，最高危）
        "mc.execute_command",
        "mc.attack",
        "mc.mine_block",
    })


# ─── 按平台分组（每个平台风险面不同）───


def test_per_platform_risk_lists_are_isolated():
    # Minecraft 的高风险与 QQ 互不混用，防上下文紊乱
    mc = get_high_risk_tools_for_platform("minecraft")
    assert "mc.execute_command" in mc and "mc.attack" in mc and "mc.mine_block" in mc
    assert not any(n.startswith("qq.") for n in mc)
    qq = get_high_risk_tools_for_platform("qq_onebot")
    assert "qq.set_group_ban" in qq and "qq.kick_group_member" in qq
    assert not any(n.startswith("mc.") for n in qq)
    # 无风险面的平台返回空集；未知平台同样空集
    assert get_high_risk_tools_for_platform("mqtt_terminal") == frozenset()
    assert get_high_risk_tools_for_platform("nonexistent") == frozenset()
    assert get_high_risk_tools_for_platform(None) == frozenset()


# ─── 平台 briefing：上下文按平台隔离 ───


def test_briefing_per_platform_isolation():
    qq_brief = get_platform_briefing("qq_onebot", risk_enabled=False, tool_names=["qq.poke", "qq.send_msg"])
    assert "<platform_briefing>" in qq_brief
    assert "qq.poke" in qq_brief and "NapCat" in qq_brief
    # 风险关闭时：状态行说明被关闭，且不出现其他平台的工具
    assert "已被主人关闭" in qq_brief
    assert "mc." not in qq_brief and "discord." not in qq_brief

    mc_brief = get_platform_briefing("minecraft", risk_enabled=False, tool_names=["mc.say"])
    assert "Minecraft" in mc_brief and "mc.execute_command" in mc_brief
    assert "拍一拍" not in mc_brief  # MC 的 briefing 不该混入 QQ 概念


def test_briefing_risk_enabled_line():
    brief = get_platform_briefing("discord", risk_enabled=True, tool_names=["discord.send_message"])
    assert "已由主人在设置页开启" in brief

    # wechat 反幻觉声明：明确写出没有拍一拍/群管理
    wx = get_platform_briefing("wechat_personal", risk_enabled=False, tool_names=["wechat.send_text_message"])
    assert "没有" in wx and "拍一拍" in wx


def test_briefing_unknown_platform_fallback():
    brief = get_platform_briefing("some_new_platform", risk_enabled=False, tool_names=[])
    assert "some_new_platform" in brief
    assert "（无平台专属工具）" in brief
    assert get_platform_briefing(None) == ""


# ─── 注入面：filter_tools_by_risk ───


def test_filter_removes_high_risk_by_default():
    filtered = filter_tools_by_risk(ALL_QQ_TOOLS, risk_enabled=False)
    names = [t["function"]["name"] for t in filtered]
    assert names == ["qq.poke", "qq.send_msg"]


def test_filter_passthrough_when_risk_enabled():
    filtered = filter_tools_by_risk(ALL_QQ_TOOLS, risk_enabled=True)
    assert filtered is ALL_QQ_TOOLS  # 开启时原样返回
    assert len(filtered) == 5


def test_filter_keeps_low_risk_and_order():
    tools = [_tool("discord.send_message"), _tool("discord.timeout_member"), _tool("wechat.send_text_message")]
    filtered = filter_tools_by_risk(tools, risk_enabled=False)
    names = [t["function"]["name"] for t in filtered]
    assert names == ["discord.send_message", "wechat.send_text_message"]


def test_filter_empty_list():
    assert filter_tools_by_risk([], risk_enabled=False) == []


def test_filter_tolerates_malformed_entries():
    tools = [{"type": "function"}, {"function": "not-a-dict"}, None, _tool("qq.delete_msg")]
    filtered = filter_tools_by_risk(tools, risk_enabled=False)
    assert filtered == [{"type": "function"}, {"function": "not-a-dict"}, None]


# ─── 执行侧：_execute_platform_tool 兜底拦截 ───


class _StubInstance:
    """模拟 PlatformInstance（dataclass，config 为 dict）。"""

    def __init__(self, config: dict):
        self.config = config


def _patch_instance(monkeypatch, config: dict):
    """将 platform_router 命名空间内的 get_instance 替换为返回固定配置的桩。"""
    monkeypatch.setattr(
        platform_router_module,
        "get_instance",
        lambda instance_id: _StubInstance(config),
    )


@pytest.fixture
def router():
    return LuomiNestPlatformRouter()


@pytest.fixture
def mock_adapter():
    adapter = SimpleNamespace()
    adapter.execute_platform_tool = AsyncMock(return_value={"success": True, "output": "ok", "error": ""})
    return adapter


@pytest.mark.asyncio
async def test_execute_blocks_high_risk_when_disabled(router, mock_adapter, monkeypatch):
    _patch_instance(monkeypatch, {"platform_tools_risk_enabled": False})
    result = await router._execute_platform_tool(
        "qq.kick_group_member", {"group_id": "1", "user_id": "2"}, mock_adapter,
        instance_id="inst_test",
    )
    assert result == {"success": False, "output": "", "error": HIGH_RISK_TOOL_BLOCKED_MESSAGE}
    mock_adapter.execute_platform_tool.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_blocks_escaped_high_risk_name(router, mock_adapter, monkeypatch):
    """LLM 转义名（qq__kick_group_member）归一化后同样命中拦截。"""
    _patch_instance(monkeypatch, {})
    result = await router._execute_platform_tool(
        "qq__kick_group_member", {}, mock_adapter, instance_id="inst_test",
    )
    assert result["success"] is False
    assert result["error"] == HIGH_RISK_TOOL_BLOCKED_MESSAGE
    mock_adapter.execute_platform_tool.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_blocks_when_config_missing(router, mock_adapter, monkeypatch):
    """实例无该配置键 / 实例不存在（get_instance 返回 None）→ 默认拦截。"""
    _patch_instance(monkeypatch, {"memory_write": True})
    result = await router._execute_platform_tool(
        "discord.timeout_member", {}, mock_adapter, instance_id="inst_test",
    )
    assert result["error"] == HIGH_RISK_TOOL_BLOCKED_MESSAGE

    monkeypatch.setattr(platform_router_module, "get_instance", lambda _: None)
    result2 = await router._execute_platform_tool(
        "wechat.revoke_msg", {}, mock_adapter, instance_id="inst_test",
    )
    assert result2["error"] == HIGH_RISK_TOOL_BLOCKED_MESSAGE


@pytest.mark.asyncio
async def test_execute_allows_high_risk_when_enabled(router, mock_adapter, monkeypatch):
    _patch_instance(monkeypatch, {"platform_tools_risk_enabled": True})
    result = await router._execute_platform_tool(
        "qq.kick_group_member", {"group_id": "1", "user_id": "2"}, mock_adapter,
        instance_id="inst_test",
    )
    assert result["success"] is True
    mock_adapter.execute_platform_tool.assert_awaited_once_with(
        "qq.kick_group_member", {"group_id": "1", "user_id": "2"},
    )


@pytest.mark.asyncio
async def test_execute_allows_low_risk_when_disabled(router, mock_adapter, monkeypatch):
    """低风险工具不受闸门影响（开关关闭仍可执行）。"""
    _patch_instance(monkeypatch, {})
    result = await router._execute_platform_tool(
        "qq.poke", {"group_id": "1", "user_id": "2"}, mock_adapter, instance_id="inst_test",
    )
    assert result["success"] is True
    mock_adapter.execute_platform_tool.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_reads_dict_shaped_instance(router, mock_adapter, monkeypatch):
    """实例为 dict 形态（部分持久化路径）时同样稳妥取值。"""
    monkeypatch.setattr(
        platform_router_module,
        "get_instance",
        lambda _: {"config": {"platform_tools_risk_enabled": True}},
    )
    result = await router._execute_platform_tool(
        "qq.delete_msg", {"message_id": "9"}, mock_adapter, instance_id="inst_test",
    )
    assert result["success"] is True
    mock_adapter.execute_platform_tool.assert_awaited_once()
