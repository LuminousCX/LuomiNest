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
)
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
        "qq.kick_group_member",
        "qq.set_group_whole_ban",
        "qq.delete_msg",
        "discord.delete_message",
        "discord.timeout_member",
        "wechat.revoke_msg",
    })


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
