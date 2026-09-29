"""platform_user_key 统一人键接线验收（分册10 §16.1，假事件注入最小闭环）。

验收链路：OneBot 11 假事件 → _convert_onebot_to_platform（字段解析）
→ _should_respond（@ 唤醒）→ platform_user_key 归一（domain_policy fallback
与 _collect_group_members 群友画像）→ 群聊/私聊同人同键。
全链"记忆命中→回发"需真实 LLM 通道与 NapCat（M3 联调），此处锁单测可证段。
"""
import pytest
from types import SimpleNamespace

from app.core.domain_policy import platform_user_key, resolve_domain_policy
from app.runtime.platform.adapters.qq_onebot import LuomiNestQQOneBotAdapter
from app.runtime.platform.base import PlatformMessage
from app.runtime.platform.session import _build_user_key
from app.services.platform_router import LuomiNestPlatformRouter


def _group_event(uid: int = 10001, gid: int = 888888, at_bot: bool = True) -> dict:
    segments = [{"type": "text", "data": {"text": " 大家好"}}]
    if at_bot:
        segments = [{"type": "at", "data": {"qq": 123456}}] + segments
    return {
        "post_type": "message",
        "message_type": "group",
        "user_id": uid,
        "group_id": gid,
        "message_id": 42,
        "sender": {"nickname": "群友甲", "card": "甲卡"},
        "message": segments,
    }


def _private_event(uid: int = 10001) -> dict:
    return {
        "post_type": "message",
        "message_type": "private",
        "user_id": uid,
        "message_id": 43,
        "sender": {"nickname": "群友甲"},
        "message": [{"type": "text", "data": {"text": "在吗"}}],
    }


def _adapter() -> LuomiNestQQOneBotAdapter:
    adapter = LuomiNestQQOneBotAdapter()
    adapter.set_instance_id("inst_qq_test")
    adapter.initialize({"ws_host": "127.0.0.1", "ws_port": 8080})
    adapter._self_id = 123456
    return adapter


# ─── 1. 假事件 → PlatformMessage 字段解析 ───


def test_group_event_conversion():
    adapter = _adapter()
    event = _group_event()
    msg = adapter._convert_onebot_to_platform(event)
    assert msg is not None
    assert msg.platform == "qq_onebot"
    assert msg.user_id == "10001"
    assert msg.group_id == "888888"
    assert msg.session_id == "888888"  # 群聊 session_id = group_id
    assert msg.is_group is True
    assert msg.sender_name == "群友甲"  # 现状 nickname 优先；AstrBot 方法为 card>nickname，留待产品定夺
    assert "@123456" in msg.content or "大家好" in msg.content


def test_private_event_conversion():
    adapter = _adapter()
    msg = adapter._convert_onebot_to_platform(_private_event())
    assert msg is not None
    assert msg.is_group is False
    assert msg.user_id == "10001"
    assert msg.session_id == "10001"  # 私聊 session_id = user_id


@pytest.mark.usefixtures("_init_test_db")
def test_group_event_without_at_not_responded():
    adapter = _adapter()
    msg = adapter._convert_onebot_to_platform(_group_event(at_bot=False))
    assert msg is not None
    assert adapter._should_respond(_group_event(at_bot=False), msg) is False
    assert adapter._should_respond(_group_event(at_bot=True), msg) is True


# ─── 2. 归一：群聊/私聊同人同键 ───


def test_same_person_same_key_group_and_private():
    """核心验收：同一 uid 在群聊与私聊解析出同一把用户轨键。"""
    adapter = _adapter()
    group_msg = adapter._convert_onebot_to_platform(_group_event())
    # 群聊路径（platform_router 接线后）：platform_user_key(platform, sender_id)
    group_key = platform_user_key(group_msg.platform, group_msg.user_id)
    # 私聊路径：session._build_user_key 生成 conv.user_key
    private_key = _build_user_key("qq_onebot", "10001", is_group=False)
    assert group_key == private_key == "qq_onebot_10001"
    # domain_policy sender_id fallback 同样归一（无 instance 段）
    policy = resolve_domain_policy(
        "platform:inst_qq_test", sender_id="10001", platform_name="qq_onebot"
    )
    assert policy.track_user_key == "qq_onebot_10001"


def test_domain_policy_group_track_no_instance_segment():
    """旧三段键 qq_onebot_inst1_10001 不再出现于策略解析结果。"""
    policy = resolve_domain_policy(
        "platform:任意实例id", sender_id="20002", platform_name="qq_onebot"
    )
    assert policy.memory_track == "users"
    assert policy.track_user_key == "qq_onebot_20002"
    assert "任意实例id" not in policy.track_user_key


# ─── 3. 群友画像块统一键 ───


def test_collect_group_members_uses_unified_key():
    msg = PlatformMessage(
        platform="qq_onebot",
        user_id="10001",
        content="大家好",
        session_id="888888",
        group_id="888888",
        sender_name="群友甲",
        is_group=True,
    )
    conv = {
        "messages": [
            {"role": "user", "platform": {"is_group": True, "user_id": "20002", "sender_name": "群友乙"}},
            {"role": "assistant", "content": "你好"},
            {"role": "user", "platform": {"is_group": True, "user_id": "30003", "sender_name": "群友丙"}},
        ]
    }
    members = LuomiNestPlatformRouter._collect_group_members(conv, msg, "inst_qq_test")
    keys = {m["sender_id"]: m["user_key"] for m in members}
    assert keys["20002"] == "qq_onebot_20002"
    assert keys["30003"] == "qq_onebot_30003"
    assert "inst_qq_test" not in keys["20002"]  # 不再叠 instance 段
