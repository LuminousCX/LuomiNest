"""per-group 群配置表测试（分册10 §16.3）：默认保守、增量更新、@ 门槛接线。"""
import pytest

from app.runtime.platform.adapters.qq_onebot import LuomiNestQQOneBotAdapter
from app.runtime.platform.base import PlatformMessage
from app.runtime.platform.group_config import (
    DEFAULT_GROUP_CONFIG,
    get_group_config,
    reset_group_config,
    set_group_config,
)


@pytest.mark.usefixtures("_init_test_db")
def test_default_conservative():
    """无配置的群返回默认保守值：@ 才答、记忆开、不插话。"""
    cfg = get_group_config("inst_x", "888888")
    assert cfg == DEFAULT_GROUP_CONFIG
    assert cfg["enabled"] is True
    assert cfg["respond_mode"] == "at"
    assert cfg["memory_enabled"] is True
    assert cfg["interject_rate"] == 0.0


@pytest.mark.usefixtures("_init_test_db")
def test_set_get_roundtrip_and_validation():
    cfg = set_group_config("inst_x", "888888", {"respond_mode": "at_or_reply", "interject_rate": 2.0})
    assert cfg["respond_mode"] == "at_or_reply"
    assert cfg["interject_rate"] == 1.0  # 越界钳到 [0,1]
    # 未知字段被忽略
    cfg = set_group_config("inst_x", "888888", {"unknown_field": "x"})
    assert "unknown_field" not in cfg
    with pytest.raises(ValueError):
        set_group_config("inst_x", "888888", {"respond_mode": "every_message"})
    assert get_group_config("inst_x", "888888")["respond_mode"] == "at_or_reply"
    assert reset_group_config("inst_x", "888888") is True
    assert get_group_config("inst_x", "888888") == DEFAULT_GROUP_CONFIG


def _adapter_with_group(gid: str = "888888") -> LuomiNestQQOneBotAdapter:
    adapter = LuomiNestQQOneBotAdapter()
    adapter.set_instance_id("inst_gq")
    adapter.initialize({"ws_host": "127.0.0.1", "ws_port": 8080})
    adapter._self_id = "123456"
    return adapter


def _group_event(at_bot=True, reply_to=None):
    segments = []
    if reply_to:
        segments.append({"type": "reply", "data": {"id": reply_to}})
    if at_bot:
        segments.append({"type": "at", "data": {"qq": 123456}})
    segments.append({"type": "text", "data": {"text": " 灌水"}})
    return {
        "post_type": "message",
        "message_type": "group",
        "user_id": 10001,
        "group_id": 888888,
        "message_id": 42,
        "sender": {"nickname": "群友甲"},
        "message": segments,
    }


def _group_msg():
    return PlatformMessage(
        platform="qq_onebot", user_id="10001", content=" 灌水", session_id="888888",
        group_id="888888", sender_name="群友甲", is_group=True,
    )


@pytest.mark.usefixtures("_init_test_db")
def test_should_respond_per_group_modes():
    adapter = _adapter_with_group()
    msg = _group_msg()

    # 默认 at：无 @ 不答，有 @ 答
    assert adapter._should_respond(_group_event(at_bot=False), msg) is False
    assert adapter._should_respond(_group_event(at_bot=True), msg) is True

    # enabled=false：@ 也不答
    set_group_config("inst_gq", "888888", {"enabled": False})
    assert adapter._should_respond(_group_event(at_bot=True), msg) is False
    set_group_config("inst_gq", "888888", {"enabled": True})

    # at_or_reply：引用 bot 消息可答，引用别人的不答
    set_group_config("inst_gq", "888888", {"respond_mode": "at_or_reply"})
    adapter._remember_bot_message_id("90001")
    assert adapter._should_respond(_group_event(at_bot=False, reply_to="90001"), msg) is True
    assert adapter._should_respond(_group_event(at_bot=False, reply_to="99999"), msg) is False

    # all：纯灌水也答（慎用档）
    set_group_config("inst_gq", "888888", {"respond_mode": "all"})
    assert adapter._should_respond(_group_event(at_bot=False), msg) is True

    # 私聊不受群配置影响
    private_msg = PlatformMessage(
        platform="qq_onebot", user_id="10001", content="在吗", session_id="10001",
        sender_name="群友甲", is_group=False,
    )
    assert adapter._should_respond({"message": []}, private_msg) is True

@pytest.mark.usefixtures("_init_test_db")
def test_bot_message_ids_capped():
    adapter = _adapter_with_group()
    for i in range(300):
        adapter._remember_bot_message_id(str(i))
    assert len(adapter._bot_message_ids) == 256
    assert "299" in adapter._bot_message_ids and "0" not in adapter._bot_message_ids
