"""平台命令体系与会话策略测试（2026-10-12 拍板：命令制会话管理）。

覆盖：
- parse_command 命令形态判定（合法名/未知名/路径文本/中文消息不误伤）；
- /help /new /memory 三命令的短路行为（不进 LLM）与回复内容；
- 会话策略：私聊每人一会、群聊一群一会、/new 重建映射且标题可读（无 unknown）；
- /memory 群聊隐私边界：只展示 scope=global，私聊专属（private）不进群；
- 历史垃圾会话清理：default- 前缀 + unknown 平台 + 空会话三条件幂等清理。
"""
import pytest

import app.runtime.platform.session as session_module
import app.engines.memory as memory_pkg
from app.engines.memory.models import FactItem
from app.runtime.platform.base import PlatformMessage
from app.runtime.platform.commands import (
    CommandContext,
    dispatch_platform_command,
    iter_commands,
    parse_command,
)
from app.runtime.platform.session import (
    create_new_conversation,
    get_conversation_id,
    get_or_create_conversation,
    remove_platform_session,
)


def _ctx(
    content: str = "你好",
    user_id: str = "u10001",
    session_id: str = "",
    is_group: bool = False,
    instance_id: str = "inst_cmd",
    sender_name: str = "测试用户",
) -> CommandContext:
    return CommandContext(
        message=PlatformMessage(
            platform="qq_onebot",
            user_id=user_id,
            content=content,
            session_id=session_id or ("g888" if is_group else user_id),
            group_id="g888" if is_group else "",
            sender_name=sender_name,
            is_group=is_group,
            message_id="m1",
        ),
        instance_id=instance_id,
        session_id=session_id or ("g888" if is_group else user_id),
        agent_name="小汐",
    )


# ------------------------------------------------------------------
# 1. parse_command：命令形态判定
# ------------------------------------------------------------------


def test_parse_known_commands():
    assert parse_command("/new") == ("new", "")
    assert parse_command("/NEW") == ("new", "")  # 命令名不区分大小写
    assert parse_command("  /help  ") == ("help", "")
    assert parse_command("/memory 帮我看看") == ("memory", "帮我看看")


def test_parse_non_command_texts():
    assert parse_command("你好呀") is None
    assert parse_command("") is None
    assert parse_command("/") is None
    # 路径文本与中文斜杠开头不视为命令，照常进 LLM
    assert parse_command("/usr/local/bin") is None
    assert parse_command("/帮助") is None
    # 首字符非字母（/123、/_x）不是合法命令名
    assert parse_command("/123") is None


def test_iter_commands_contains_decided_three():
    names = {c["name"] for c in iter_commands()}
    assert {"help", "new", "memory"} <= names


# ------------------------------------------------------------------
# 2. 命令短路行为（不进 LLM 的部分由 router 层保证，这里验证回复）
# ------------------------------------------------------------------


async def test_non_command_returns_none():
    assert await dispatch_platform_command(_ctx("今天天气不错")) is None


async def test_unknown_command_replies_guidance():
    resp = await dispatch_platform_command(_ctx("/status"))
    assert resp is not None
    assert "未知命令 /status" in resp.content
    assert "/help" in resp.content


async def test_help_lists_commands():
    resp = await dispatch_platform_command(_ctx("/help"))
    assert resp is not None
    for cmd in ("help", "new", "memory"):
        assert f"/{cmd}" in resp.content


# ------------------------------------------------------------------
# 3. /new：会话策略（私聊每人一会、群聊一群一会、/new 重建映射）
# ------------------------------------------------------------------


@pytest.mark.usefixtures("_init_test_db")
async def test_private_one_conversation_per_user():
    """同一私聊用户反复发消息只映射一个 conversation（每人一会）。"""
    inst = "inst_priv"
    c1 = await get_or_create_conversation(inst, "u10001", "qq_onebot", "测试用户")
    c2 = await get_or_create_conversation(inst, "u10001", "qq_onebot", "测试用户")
    assert c1 == c2
    # 不同用户各自一会
    c3 = await get_or_create_conversation(inst, "u10002", "qq_onebot", "另一位")
    assert c3 != c1
    remove_platform_session(inst, "u10001")
    remove_platform_session(inst, "u10002")


@pytest.mark.usefixtures("_init_test_db")
async def test_group_one_conversation_per_group():
    """群里不同成员发言共享同一个群会话（一群一会，不因单人发言增会话）。"""
    inst = "inst_grp"
    m1 = await get_or_create_conversation(inst, "g888", "qq_onebot", "群888", is_group=True)
    m2 = await get_or_create_conversation(inst, "g888", "qq_onebot", "群888", is_group=True)
    assert m1 == m2
    remove_platform_session(inst, "g888")


@pytest.mark.usefixtures("_init_test_db")
async def test_new_command_rebuilds_mapping_with_readable_title():
    """/new 重建映射：新 conversation、旧映射被替换、标题含平台名（不回退 unknown）。"""
    inst = "inst_new"
    old_id = await get_or_create_conversation(inst, "u10001", "qq_onebot", "测试用户")

    ctx = _ctx("/new", instance_id=inst)
    resp = await dispatch_platform_command(ctx)
    assert resp is not None and "新对话" in resp.content

    new_id = await get_conversation_id(inst, "u10001")
    assert new_id and new_id != old_id
    from app.infrastructure.database.conversation_store import conversation_store
    conv = conversation_store.get(new_id)
    assert conv is not None
    assert "qq_onebot" in conv["title"]
    assert "unknown" not in conv["title"]
    remove_platform_session(inst, "u10001")


@pytest.mark.usefixtures("_init_test_db")
async def test_new_without_prior_mapping_still_readable():
    """映射缺失时（存量边缘） /new 直接以消息侧元数据建会话，标题不出现 unknown。"""
    inst = "inst_new_fresh"
    ctx = _ctx("/new", instance_id=inst, user_id="u20002")
    resp = await dispatch_platform_command(ctx)
    assert resp is not None and "新对话" in resp.content
    from app.infrastructure.database.conversation_store import conversation_store
    conv_id = await get_conversation_id(inst, "u20002")
    conv = conversation_store.get(conv_id)
    assert conv is not None and "unknown" not in conv["title"]
    remove_platform_session(inst, "u20002")


# ------------------------------------------------------------------
# 4. /memory：用户轨读取 + 群聊隐私边界
# ------------------------------------------------------------------


class _FakeFactManager:
    def __init__(self, facts):
        self._facts = facts

    def get_facts(self, category=None, include_expired=False):
        return list(self._facts)


class _FakeEngine:
    def __init__(self, facts):
        self.fact_manager = _FakeFactManager(facts)


def _patch_track_engine(monkeypatch, facts):
    seen_keys = []

    def fake_get_track_engine(track, user_key=""):
        seen_keys.append((track, user_key))
        return _FakeEngine(facts)

    monkeypatch.setattr(memory_pkg, "get_track_engine", fake_get_track_engine)
    return seen_keys


async def test_memory_private_shows_all_facts(monkeypatch):
    facts = [
        FactItem(content="喜欢甜食", category="偏好"),
        FactItem(content="住在杭州", category="context", scope="private"),
    ]
    seen = _patch_track_engine(monkeypatch, facts)

    resp = await dispatch_platform_command(_ctx("/memory"))
    assert resp is not None
    assert "喜欢甜食" in resp.content and "住在杭州" in resp.content
    assert seen == [("users", "qq_onebot_u10001")]


async def test_memory_group_hides_private_facts(monkeypatch):
    """群聊 /memory 只展示全局画像：私聊专属秘密不得泄露到群里。"""
    facts = [
        FactItem(content="公开的爱好", category="兴趣", scope="global"),
        FactItem(content="私密事项", category="context", scope="private"),
    ]
    _patch_track_engine(monkeypatch, facts)

    resp = await dispatch_platform_command(_ctx("/memory", is_group=True))
    assert resp is not None
    assert "公开的爱好" in resp.content
    assert "私密事项" not in resp.content
    assert "仅展示公开记忆" in resp.content


async def test_memory_empty_track(monkeypatch):
    _patch_track_engine(monkeypatch, [])
    resp = await dispatch_platform_command(_ctx("/memory"))
    assert resp is not None and "还没有记住" in resp.content


async def test_memory_missing_user_id(monkeypatch):
    _patch_track_engine(monkeypatch, [])
    ctx = _ctx("/memory", user_id="  ")
    ctx.message.user_id = ""
    resp = await dispatch_platform_command(ctx)
    assert resp is not None and "无法识别" in resp.content


# ------------------------------------------------------------------
# 5. 历史垃圾会话清理（default- 前缀 + unknown 平台 + 空会话）
# ------------------------------------------------------------------


@pytest.mark.usefixtures("_init_test_db")
async def test_garbage_session_cleanup(monkeypatch):
    from app.infrastructure.database.config_store import luominest_config_store
    from app.infrastructure.database.conversation_store import conversation_store

    # 种入垃圾映射（手动新建端点的典型产物）+ 正常映射
    garbage_conv = {"id": "plat-garbage1", "title": "unknown 私聊 default-1b8a44b1", "messages": []}
    real_conv = {"id": "plat-real1", "title": "[qq_onebot] 私聊 测试用户", "messages": []}
    await conversation_store.set_async("plat-garbage1", garbage_conv)
    await conversation_store.set_async("plat-real1", real_conv)
    luominest_config_store.set("platform.sessions.inst_gc:default-1b8a44b1", {
        "conversation_id": "plat-garbage1", "instance_id": "inst_gc",
        "session_id": "default-1b8a44b1", "platform_name": "unknown",
        "sender_name": "", "is_group": False,
    })
    luominest_config_store.set("platform.sessions.inst_gc:u10001", {
        "conversation_id": "plat-real1", "instance_id": "inst_gc",
        "session_id": "u10001", "platform_name": "qq_onebot",
        "sender_name": "测试用户", "is_group": False,
    })

    # 跳过迁移标记 + 复位进程内标记，强制清理执行
    import app.infrastructure.database.migration.json_to_sqlite_migrator as migrator
    monkeypatch.setattr(migrator, "_is_migrated", lambda source: False)
    marked = []
    monkeypatch.setattr(migrator, "_mark_migrated", lambda source, count: marked.append(source))
    monkeypatch.setattr(session_module, "_cleanup_done", False)

    session_module._cleanup_garbage_sessions()

    # 垃圾：映射与空 conversation 一并删除；正常映射保留
    assert luominest_config_store.get("platform.sessions.inst_gc:default-1b8a44b1") is None
    assert conversation_store.get("plat-garbage1") is None
    assert luominest_config_store.get("platform.sessions.inst_gc:u10001") is not None
    assert conversation_store.get("plat-real1") is not None
    assert marked == [session_module._CLEANUP_SOURCE]

    remove_platform_session("inst_gc", "u10001")


@pytest.mark.usefixtures("_init_test_db")
async def test_garbage_cleanup_keeps_nonempty_conversation(monkeypatch):
    """有消息的疑似垃圾仅解除映射，不删用户数据（防御性）。"""
    from app.infrastructure.database.config_store import luominest_config_store
    from app.infrastructure.database.conversation_store import conversation_store

    conv = {"id": "plat-garbage2", "title": "unknown 私聊 default-abc", "messages": [{"role": "user", "content": "hi"}]}
    await conversation_store.set_async("plat-garbage2", conv)
    luominest_config_store.set("platform.sessions.inst_gc2:default-abc", {
        "conversation_id": "plat-garbage2", "instance_id": "inst_gc2",
        "session_id": "default-abc", "platform_name": "unknown",
        "sender_name": "", "is_group": False,
    })

    import app.infrastructure.database.migration.json_to_sqlite_migrator as migrator
    monkeypatch.setattr(migrator, "_is_migrated", lambda source: False)
    monkeypatch.setattr(migrator, "_mark_migrated", lambda source, count: None)
    monkeypatch.setattr(session_module, "_cleanup_done", False)

    session_module._cleanup_garbage_sessions()

    assert luominest_config_store.get("platform.sessions.inst_gc2:default-abc") is None
    assert conversation_store.get("plat-garbage2") is not None
    conversation_store.delete("plat-garbage2")
