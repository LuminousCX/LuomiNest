"""wechat_personal P0-2 三连修复测试。

覆盖审查报告 03-平台对接链路.md P0-2 的三个问题：
1. webhook 零鉴权 → 共享密钥校验（缺省强制要求，Fail-Closed）；
2. 群消息无 @ 门槛 → 默认 @ 才响应（per-group 群配置 respond_mode 可放开）；
3. 自消息过滤必然失效（比对缺省随机 app_id，且群消息 from_user 是群 ID）
   → 真实 self wxid + 本机发送 newMsgId 回显过滤，杜绝双 bot 死循环。
"""
import time

import httpx
import pytest

from app.runtime.platform.adapters.wechat_personal import LuomiNestWeChatPersonalAdapter
from app.runtime.platform.base import AdapterStatus, PlatformResponse
from app.runtime.platform.group_config import reset_group_config, set_group_config

WEBHOOK_TOKEN = "shared-secret-123"
SELF_WXID = "wxid_bot_real"
GROUP_ID = "12345678@chatroom"
INSTANCE_ID = "inst_wx_p02"


def _add_msg(
    from_user: str = GROUP_ID,
    to_user: str = SELF_WXID,
    content: str = "wxid_user123:\n大家好",
    msg_type: int = 1,
    new_msg_id: int | str = 88888,
    at_list: list | None = None,
    msg_source: str = "",
    token: str | None = WEBHOOK_TOKEN,
) -> dict:
    """构造 Gewechat AddMsg 推送体（token=None 表示不带密钥字段）。"""
    data: dict = {
        "FromUserName": {"string": from_user},
        "ToUserName": {"string": to_user},
        "Content": {"string": content},
        "MsgType": msg_type,
        "NewMsgId": new_msg_id,
    }
    if at_list is not None:
        data["AtUserList"] = at_list
    if msg_source:
        data["MsgSource"] = msg_source
    body: dict = {"TypeName": "AddMsg", "Data": data}
    if token is not None:
        body["Token"] = token
    return body


def _adapter(**extra) -> LuomiNestWeChatPersonalAdapter:
    adapter = LuomiNestWeChatPersonalAdapter()
    adapter.set_instance_id(INSTANCE_ID)
    config = {
        "api_url": "http://127.0.0.1:2531/v2/api",
        "token": "gewe-token",
        "app_id": "wx_app_dev",
        "webhook_token": WEBHOOK_TOKEN,
        "self_wxid": SELF_WXID,
        "mock_mode": True,  # 发送走模拟分支，不触网
        "typing_delay_enabled": False,
        "rate_limit_per_minute": 100,
    }
    config.update(extra)
    adapter.initialize(config)
    return adapter


def _attach_handler(adapter) -> list:
    """挂接收集型消息处理器，返回收到的消息列表。"""
    received: list = []

    async def handler(msg, instance_id: str):
        received.append(msg)
        return PlatformResponse(content="ok")

    adapter.set_message_handler(handler)
    return received


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def json(self) -> dict:
        return self._payload


# ---------------------------------------------------------------------------
# 修复 1：webhook 共享密钥鉴权（Fail-Closed）
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_webhook_fail_closed_when_token_unconfigured():
    """未配置 webhook_token：一切推送拒绝处理（缺省强制要求）。"""
    adapter = _adapter(webhook_token="")
    received = _attach_handler(adapter)

    res = await adapter.handle_webhook(_add_msg(token=WEBHOOK_TOKEN))
    assert res["status"] == "unauthorized"
    # 无密钥字段的推送同样拒绝
    res = await adapter.handle_webhook(_add_msg(token=None))
    assert res["status"] == "unauthorized"
    assert received == []


@pytest.mark.asyncio
async def test_webhook_rejects_wrong_or_missing_token():
    """已配置 webhook_token：密钥不匹配/缺失一律拒绝，消息不进 Agent。"""
    adapter = _adapter()
    received = _attach_handler(adapter)

    for token in ("wrong-token", None):
        res = await adapter.handle_webhook(_add_msg(token=token))
        assert res["status"] == "unauthorized"
    assert received == []


@pytest.mark.asyncio
async def test_webhook_accepts_valid_token_and_login_event():
    """正确密钥放行；LoginEvent 同样要求鉴权且登录成功会学习自身 wxid。"""
    adapter = _adapter(self_wxid="")
    received = _attach_handler(adapter)

    res = await adapter.handle_webhook(_add_msg(at_list=[SELF_WXID]))
    assert res["status"] == "processed"
    assert len(received) == 1

    # webhook_token / token 备选字段名同样认可
    body = _add_msg(token=None, at_list=[SELF_WXID], new_msg_id=88889)
    body["webhook_token"] = WEBHOOK_TOKEN
    res = await adapter.handle_webhook(body)
    assert res["status"] == "processed"
    assert len(received) == 2

    login_body = {
        "TypeName": "LoginEvent",
        "Token": WEBHOOK_TOKEN,
        "Data": {"status": 2, "wxid": SELF_WXID},
    }
    res = await adapter.handle_webhook(login_body)
    assert res["status"] == "ok"
    assert adapter._self_wxid == SELF_WXID
    assert adapter.get_status()["status"] == AdapterStatus.RUNNING.value

    # 未鉴权的 LoginEvent 不得改变适配器状态
    adapter2 = _adapter(self_wxid="")
    bad_login = {"TypeName": "LoginEvent", "Data": {"status": 2, "wxid": SELF_WXID}}
    res = await adapter2.handle_webhook(bad_login)
    assert res["status"] == "unauthorized"
    assert adapter2.get_status()["status"] != AdapterStatus.RUNNING.value


# ---------------------------------------------------------------------------
# 修复 2：群聊 @ 唤醒门槛（默认 at 才答，私聊不受限）
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_group_message_requires_at_by_default():
    """默认 respond_mode=at：群消息无 @ 不响应，@ 机器人才响应。"""
    adapter = _adapter()
    received = _attach_handler(adapter)

    # 无 @：忽略
    res = await adapter.handle_webhook(_add_msg(at_list=None))
    assert res["status"] == "ignored"
    assert received == []

    # @ 了别人：忽略
    res = await adapter.handle_webhook(_add_msg(at_list=["wxid_other_member"]))
    assert res["status"] == "ignored"

    # @ 机器人：响应且解析出发言人与内容
    res = await adapter.handle_webhook(_add_msg(at_list=[SELF_WXID], content="wxid_user123:\n@Bot 你在吗"))
    assert res["status"] == "processed"
    assert len(received) == 1
    assert received[0].user_id == "wxid_user123"
    assert received[0].content == "@Bot 你在吗"
    assert received[0].is_group is True


@pytest.mark.asyncio
async def test_group_at_detection_paths():
    """AtUserList / MsgSource XML / 文本兜底三条 @ 识别路径。"""
    adapter = _adapter()
    received = _attach_handler(adapter)

    # MsgSource XML 的 atuserlist 命中
    res = await adapter.handle_webhook(_add_msg(msg_source=f"<msg><atuserlist>{SELF_WXID},wxid_a</atuserlist></msg>"))
    assert res["status"] == "processed"

    # 结构化字段全缺失时的文本兜底：微信 @ 提及带 U+2005
    res = await adapter.handle_webhook(_add_msg(at_list=None, content="wxid_user123:\n@Bot\u2005在吗"))
    assert res["status"] == "processed"

    assert len(received) == 2


@pytest.mark.usefixtures("_init_test_db")
@pytest.mark.asyncio
async def test_group_respond_mode_switch():
    """per-group 群配置开关：respond_mode=all 放开门槛，enabled=false 全拒。"""
    adapter = _adapter()
    received = _attach_handler(adapter)
    try:
        # all：无 @ 也响应
        set_group_config(INSTANCE_ID, GROUP_ID, {"respond_mode": "all"})
        res = await adapter.handle_webhook(_add_msg(at_list=None, new_msg_id=90001))
        assert res["status"] == "processed"

        # enabled=false：@ 也不响应
        set_group_config(INSTANCE_ID, GROUP_ID, {"enabled": False})
        res = await adapter.handle_webhook(_add_msg(at_list=[SELF_WXID], new_msg_id=90002))
        assert res["status"] == "ignored"
    finally:
        reset_group_config(INSTANCE_ID, GROUP_ID)
    assert len(received) == 1


@pytest.mark.asyncio
async def test_private_message_not_gated():
    """私聊不受 @ 门槛限制，无 @ 直接响应。"""
    adapter = _adapter()
    received = _attach_handler(adapter)

    res = await adapter.handle_webhook(
        _add_msg(from_user="wxid_friend", to_user=SELF_WXID, content="在吗", at_list=None)
    )
    assert res["status"] == "processed"
    assert len(received) == 1
    assert received[0].is_group is False


# ---------------------------------------------------------------------------
# 修复 3：自消息过滤（防双 bot 死循环）
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_group_self_echo_filtered_by_real_wxid():
    """群内自己消息的回显（发言人在 content 前缀）被过滤——旧实现对群聊
    比对的是群 ID，必然漏过；现在按真实 self wxid 比对 content 前缀发言人。"""
    adapter = _adapter()
    received = _attach_handler(adapter)

    res = await adapter.handle_webhook(
        _add_msg(at_list=[SELF_WXID], content=f"{SELF_WXID}:\n这是我刚才的回复回显")
    )
    assert res["status"] == "ignored"
    assert received == []


@pytest.mark.asyncio
async def test_self_wxid_learned_from_group_then_echo_filtered():
    """未显式配置 self_wxid 时：首条群消息从 ToUserName 学习自身 wxid，
    随后自己的回显即被识别——死循环在第一轮回复处即被斩断。"""
    adapter = _adapter(self_wxid="")
    received = _attach_handler(adapter)

    # 他人的 @ 消息：正常响应，同时从 ToUserName 学到自身 wxid
    res = await adapter.handle_webhook(_add_msg(at_list=[SELF_WXID], new_msg_id=70001))
    assert res["status"] == "processed"
    assert adapter._self_wxid == SELF_WXID
    assert len(received) == 1

    # 机器人回复后的回显：发言人前缀 = 自身 wxid → 过滤
    res = await adapter.handle_webhook(
        _add_msg(at_list=[SELF_WXID], content=f"{SELF_WXID}:\nok", new_msg_id=70002)
    )
    assert res["status"] == "ignored"
    assert len(received) == 1


@pytest.mark.asyncio
async def test_private_self_and_appid_echo_filtered():
    """私聊自身回显：from_user 命中真实 self wxid 或 app_id 均过滤。"""
    adapter = _adapter()
    received = _attach_handler(adapter)

    res = await adapter.handle_webhook(
        _add_msg(from_user=SELF_WXID, to_user="wxid_friend", content="hi", at_list=None)
    )
    assert res["status"] == "ignored"

    res = await adapter.handle_webhook(
        _add_msg(from_user="wx_app_dev", to_user="wxid_friend", content="hi", at_list=None)
    )
    assert res["status"] == "ignored"
    assert received == []


@pytest.mark.asyncio
async def test_sent_message_id_echo_filtered():
    """NewMsgId 命中本机 API 发送记录 → 自己回复的回显（wxid 未知时的兜底）。"""
    adapter = _adapter(self_wxid="")  # 不给 wxid，只靠发送记录识别
    received = _attach_handler(adapter)
    adapter._record_sent_message("wxid_friend", {"newMsgId": "777777"})

    res = await adapter.handle_webhook(
        _add_msg(from_user="wxid_friend", to_user="wxid_friend", content="hi", new_msg_id=777777)
    )
    assert res["status"] == "ignored"
    assert received == []

    # 未记录的 id 不受影响
    res = await adapter.handle_webhook(
        _add_msg(from_user="wxid_friend", to_user=SELF_WXID, content="hi", new_msg_id=777778)
    )
    assert res["status"] == "processed"


# ---------------------------------------------------------------------------
# 附属修复：登录二维码不再静默降级 mock（仅显式 mock_mode 允许）
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_qr_network_error_no_silent_mock_fallback(monkeypatch):
    """真实模式下 Gewechat 网络异常返回 error 状态，不再伪造演示二维码。"""
    adapter = _adapter(mock_mode=False)

    async def raise_connect_error(self, url, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx.AsyncClient, "post", raise_connect_error)
    res = await adapter.fetch_login_qrcode()
    assert res["status"] == "error"
    assert res["qr_data"] == ""


@pytest.mark.asyncio
async def test_qr_mock_mode_still_returns_mock():
    """显式 mock_mode 下仍允许模拟二维码（沙盒演练用途保留）。"""
    adapter = _adapter(mock_mode=True)
    res = await adapter.fetch_login_qrcode()
    assert res["status"] == "waiting_scan"
    assert "data:image/svg+xml" in res["qr_data"]


@pytest.mark.asyncio
async def test_check_login_learns_self_wxid(monkeypatch):
    """checkLogin 登录成功回执携带 wxid 时学习自身真实 wxid。"""
    adapter = _adapter(mock_mode=False, self_wxid="")
    adapter._current_qr = {
        "uuid": "qr_test",
        "qr_data": "http://example/qr",
        "status": "waiting_scan",
        "created_at": time.time(),
        "expired_at": time.time() + 180,
    }

    async def fake_post(self, url, headers=None, json=None):
        return _FakeResponse({"ret": 200, "data": {"status": 2, "wxid": SELF_WXID}})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    res = await adapter.check_login_status("qr_test")
    assert res["status"] == "logged_in"
    assert adapter._self_wxid == SELF_WXID
