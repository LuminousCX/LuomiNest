"""Minecraft RCON 命令注入防护单测（汇总报告 P0-3 target_player 注入面回归）。

覆盖：
1. target_player 白名单（[A-Za-z0-9_]{1,16}）：合法名正常构造命令，
   恶意玩家名（选择器/引号/换行/超长等注入载荷）被拒绝且不触达 RCON
2. send_message 对非法目标 fail-closed：不发送、不降级广播、不回落 WS 模组
3. say 文本控制字符中和（换行折叠空格）与 tellraw 引号转义仍生效
4. _build_say_command 纵深防御：非法目标直接 raise，任何调用方都拿不到命令
"""
from unittest.mock import AsyncMock

import pytest

from app.runtime.platform.adapters.minecraft import (
    LuomiNestMinecraftAdapter,
    _MC_PLAYER_NAME_PATTERN,
    _sanitize_mc_text,
)
from app.runtime.platform.base import PlatformResponse


VALID_NAMES = ["Steve", "Alex_123", "a", "x" * 16]
# 典型 RCON 注入载荷：选择器越权、引号逃逸、换行拼接命令、空字节、超长名
INJECTION_PAYLOADS = [
    "@a",                       # 选择器冒充：把私聊变全服广播
    '@a["cmd"]',                # 带参数选择器
    'Steve" ; say hacked',      # 引号逃逸追加命令
    "Steve\nsay pwned",         # 换行拼接
    "Steve\rtell @a hacked",    # 回车拼接
    "Steve\x00say pwned",       # 空字节截断
    "Chinese玩家名",             # 非 ASCII
    "x" * 17,                   # 超长（17 位）
    "Steve space",              # 含空格
    "",                         # 空串（经 truthiness 过滤后不会走到校验，但白名单也应拒绝）
]


def _make_adapter(message_format: str = "tellraw") -> LuomiNestMinecraftAdapter:
    adapter = LuomiNestMinecraftAdapter()
    adapter.set_instance_id("inst_mc_inject")
    adapter.initialize({
        "rcon_host": "127.0.0.1",
        "rcon_port": 25575,
        "rcon_password": "test",
        "ws_enabled": False,
        "bot_name": "TestBot",  # 显式指定，断言不依赖环境的主 Agent 配置
        "message_format": message_format,
    })
    return adapter


# ------------------------------------------------------------------
# 1. 玩家名白名单本体
# ------------------------------------------------------------------


@pytest.mark.parametrize("name", VALID_NAMES)
def test_player_name_pattern_accepts_official_charset(name):
    assert _MC_PLAYER_NAME_PATTERN.fullmatch(name)


@pytest.mark.parametrize("name", INJECTION_PAYLOADS)
def test_player_name_pattern_rejects_injection_payloads(name):
    assert not _MC_PLAYER_NAME_PATTERN.fullmatch(name)


# ------------------------------------------------------------------
# 2. _build_say_command 纵深防御
# ------------------------------------------------------------------


def test_build_say_command_valid_target_tellraw():
    adapter = _make_adapter("tellraw")
    cmd = adapter._build_say_command("你好", "Steve")
    assert cmd == 'tellraw Steve {"text":"[TestBot] 你好","color":"aqua"}'


def test_build_say_command_valid_target_tell_format():
    adapter = _make_adapter("tell")
    cmd = adapter._build_say_command("hi", "Alex_123")
    assert cmd == "tell Alex_123 [TestBot] hi"


@pytest.mark.parametrize("name", ["@a", 'Steve" ; say hacked', "Steve\nsay pwned", "x" * 17])
def test_build_say_command_raises_on_invalid_target(name):
    adapter = _make_adapter()
    with pytest.raises(ValueError):
        adapter._build_say_command("hi", name)


def test_build_say_command_sanitizes_control_chars_in_text():
    adapter = _make_adapter("tell")
    # 换行/回车折叠为空格，无法借文本追加第二段命令
    cmd = adapter._build_say_command("hi\nsay pwned", "Steve")
    assert "\n" not in cmd
    assert cmd == "tell Steve [TestBot] hi say pwned"


def test_build_say_command_tellraw_escapes_quotes_in_text():
    adapter = _make_adapter("tellraw")
    cmd = adapter._build_say_command('evil" } say hacked', "Steve")
    # 引号被转义后仍留在 JSON 字符串值内，无法闭合 JSON 逃逸出命令
    assert '\\"' in cmd
    assert cmd.startswith('tellraw Steve {"text":"')
    assert cmd.endswith('"}')


# ------------------------------------------------------------------
# 3. send_message fail-closed：非法目标不发送、不降级广播、不回落 WS
# ------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["@a", 'Steve"; say hacked', "x" * 17, "Steve\nsay pwned"])
async def test_send_message_rejects_invalid_target_without_sending(name):
    adapter = _make_adapter()
    adapter._rcon = AsyncMock()
    adapter._ws_connections = {}  # 无 WS 模组可回落

    sent = await adapter.send_message(PlatformResponse(content="hello"), name)

    assert sent is False, "非法目标必须整体拒绝（fail-closed，不得降级广播）"
    adapter._rcon.send_command.assert_not_called()


@pytest.mark.asyncio
async def test_send_message_invalid_target_does_not_reach_ws_mod_fallback():
    adapter = _make_adapter()
    adapter._rcon = None  # 无 RCON，逼出 WS 回落路径
    dispatch_spy = AsyncMock(return_value={"success": True})
    adapter.dispatch_mod_action = dispatch_spy  # type: ignore[method-assign]

    sent = await adapter.send_message(PlatformResponse(content="hello"), "@a[cmd]")

    assert sent is False
    dispatch_spy.assert_not_called()


@pytest.mark.asyncio
async def test_send_message_broadcast_still_works():
    adapter = _make_adapter()
    adapter._rcon = AsyncMock()
    adapter._rcon.send_command.return_value = "ok"

    sent = await adapter.send_message(PlatformResponse(content="hello"), "broadcast")

    assert sent is True
    cmd = adapter._rcon.send_command.call_args[0][0]
    assert cmd.startswith("tellraw @a ")


@pytest.mark.asyncio
@pytest.mark.parametrize("name", VALID_NAMES)
async def test_send_message_valid_target_builds_targeted_command(name):
    adapter = _make_adapter()
    adapter._rcon = AsyncMock()
    adapter._rcon.send_command.return_value = "ok"

    sent = await adapter.send_message(PlatformResponse(content="hello"), name)

    assert sent is True
    cmd = adapter._rcon.send_command.call_args[0][0]
    assert cmd.startswith(f"tellraw {name} ")


# ------------------------------------------------------------------
# 4. mc.say 工具入口同样受白名单保护
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mc_say_tool_rejects_injected_target_player():
    adapter = _make_adapter()
    adapter._rcon = None
    adapter._ws_connections = {}

    res = await adapter.execute_platform_tool(
        "mc.say", {"message": "hi", "target_player": '@a"; say hacked'}
    )

    assert res.get("success") is not True, "工具入口的非法 target_player 必须被拒绝"


@pytest.mark.asyncio
async def test_mc_say_tool_dispatches_for_valid_target():
    adapter = _make_adapter()
    adapter._rcon = AsyncMock()
    adapter._rcon.send_command.return_value = "ok"

    # dispatch_mod_action 的 RCON 回退按 player 参数定目标，须同时传入
    res = await adapter.execute_platform_tool(
        "mc.say", {"message": "hi", "target_player": "Steve", "player": "Steve"}
    )

    assert res.get("success") is True
    cmd = adapter._rcon.send_command.call_args[0][0]
    assert cmd.startswith("tellraw Steve ")
