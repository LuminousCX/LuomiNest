"""群友画像块（build_group_members_block）与群聊注入回归（§8.5.10 本期实现）。

覆盖：
- 多成员读取与「[群友] 昵称(sender_id)：」格式
- 每人事实条数截断（取最近 top N）、成员数截断、总长限幅
- exclude_keys 排除说话成员、空轨/非法键跳过
- inject_memory 平台域叠加画像块（platform_memory_write 关闭时照常注入）
- GroupChatManager 成员轨键收集（仅人类发言者、去重、按群命名空间）
"""

from unittest.mock import MagicMock

import pytest

from app.core.domain_policy import (
    MAIN_AGENT_ID,
    TRACK_USERS,
    group_member_user_key,
    resolve_domain_policy,
)
from app.engines.memory import get_track_engine
from app.engines.memory.memory_engine import build_group_members_block
from app.engines.memory.models import FactItem
from app.services import context_service as context_service_module
from app.services.context_service import ContextService


@pytest.fixture
def seeded_keys(_init_test_db):
    """记录测试中播种过的成员轨键，结束后清空数据避免注册表串扰。

    成员轨走全局库（DATA_DIR/memory/users/），依赖 _init_test_db 先建表。
    """
    keys: list[str] = []
    yield keys
    for key in keys:
        try:
            get_track_engine(TRACK_USERS, key).reset_all()
        except Exception:
            pass


def _seed_member_track(keys: list[str], user_key: str, contents: list[str]) -> None:
    engine = get_track_engine(TRACK_USERS, user_key)
    keys.append(user_key)
    data = engine.load_data()
    for i, content in enumerate(contents):
        data.facts.append(FactItem(
            content=content,
            category="preference",
            confidence=0.9,
            created_at=f"2026-01-01T00:{i:02d}:00+00:00",
        ))
    engine.save_data(data)


class TestBuildGroupMembersBlock:
    def test_formats_members_with_facts(self, seeded_keys):
        k1 = group_member_user_key("qq", "inst1", "10001")
        k2 = group_member_user_key("qq", "inst1", "20002")
        _seed_member_track(seeded_keys, k1, ["喜欢咖啡", "住在杭州"])
        _seed_member_track(seeded_keys, k2, ["是程序员"])

        block = build_group_members_block([
            {"sender_id": "10001", "sender_name": "小明", "user_key": k1},
            {"sender_id": "20002", "sender_name": "小红", "user_key": k2},
        ])
        assert "[群友] 小明(10001)：" in block
        assert "- 喜欢咖啡" in block
        assert "- 住在杭州" in block
        assert "[群友] 小红(20002)：" in block
        assert "- 是程序员" in block

    def test_facts_per_member_cap_keeps_latest(self, seeded_keys):
        key = group_member_user_key("qq", "inst1", "10001")
        _seed_member_track(seeded_keys, key, [f"事实-{i:02d}" for i in range(12)])

        block = build_group_members_block(
            [{"sender_id": "10001", "sender_name": "小明", "user_key": key}],
            facts_per_member=8,
        )
        member_lines = [ln for ln in block.splitlines() if ln.startswith("- ")]
        assert len(member_lines) == 8
        # 取最近 8 条：最早的 4 条被截掉，最新一条保留
        assert "- 事实-11" in block
        assert "- 事实-04" in block
        assert "- 事实-03" not in block

    def test_members_count_cap(self, seeded_keys):
        members = []
        for i in range(12):
            key = group_member_user_key("qq", "inst1", str(10000 + i))
            _seed_member_track(seeded_keys, key, [f"成员{i}的事实"])
            members.append({"sender_id": str(10000 + i), "sender_name": f"成员{i}", "user_key": key})

        block = build_group_members_block(members, max_members=10)
        assert block.count("[群友]") == 10

    def test_total_chars_cap(self, seeded_keys):
        k1 = group_member_user_key("qq", "inst1", "10001")
        k2 = group_member_user_key("qq", "inst1", "20002")
        _seed_member_track(seeded_keys, k1, ["喜欢咖啡", "住在杭州"])
        _seed_member_track(seeded_keys, k2, ["是程序员"])

        # 限幅只够第一条 → 只保留第一个成员
        block = build_group_members_block([
            {"sender_id": "10001", "sender_name": "小明", "user_key": k1},
            {"sender_id": "20002", "sender_name": "小红", "user_key": k2},
        ], max_chars=40)
        assert "小明(10001)" in block
        assert "小红(20002)" not in block

        # 限幅小于首个成员段 → 整块为空
        assert build_group_members_block(
            [{"sender_id": "10001", "sender_name": "小明", "user_key": k1}], max_chars=5,
        ) == ""

    def test_exclude_keys_skips_speaker(self, seeded_keys):
        k1 = group_member_user_key("qq", "inst1", "10001")
        k2 = group_member_user_key("qq", "inst1", "20002")
        _seed_member_track(seeded_keys, k1, ["说话人的事实"])
        _seed_member_track(seeded_keys, k2, ["旁观者的事实"])

        block = build_group_members_block(
            [
                {"sender_id": "10001", "sender_name": "小明", "user_key": k1},
                {"sender_id": "20002", "sender_name": "小红", "user_key": k2},
            ],
            exclude_keys={k1},
        )
        assert "小明(10001)" not in block
        assert "小红(20002)" in block

    def test_empty_or_invalid_tracks_skipped(self, seeded_keys):
        members = [
            {"sender_id": "10001", "sender_name": "无轨", "user_key": group_member_user_key("qq", "inst1", "10001")},
            {"sender_id": "10002", "sender_name": "坏键", "user_key": "../evil"},
            {"sender_id": "10003", "sender_name": "空键", "user_key": ""},
        ]
        assert build_group_members_block(members) == ""

    def test_dedup_same_user_key(self, seeded_keys):
        key = group_member_user_key("qq", "inst1", "10001")
        _seed_member_track(seeded_keys, key, ["唯一事实"])
        block = build_group_members_block(
            [
                {"sender_id": "10001", "sender_name": "小明", "user_key": key},
                {"sender_id": "10001", "sender_name": "小明", "user_key": key},
            ],
        )
        assert block.count("[群友]") == 1


class TestInjectMemoryGroupMembers:
    @pytest.fixture
    def clean_owner_engine(self, _init_test_db):
        from app.engines.memory.memory_engine import get_memory_engine

        engine = get_memory_engine(MAIN_AGENT_ID)
        engine.reset_all()
        yield engine
        engine.reset_all()

    async def test_platform_inject_appends_member_block(
        self, clean_owner_engine, seeded_keys, monkeypatch,
    ):
        # 哨兵：注入全程不应触发 embedding
        get_provider = MagicMock()
        monkeypatch.setattr(context_service_module.llm_adapter, "get_provider", get_provider)

        speaker_key = group_member_user_key("qq_onebot", "inst1", "10001")
        other_key = group_member_user_key("qq_onebot", "inst1", "20002")
        _seed_member_track(seeded_keys, speaker_key, ["说话人喜欢咖啡"])
        _seed_member_track(seeded_keys, other_key, ["小红是程序员"])

        # 写开关默认关：读注入不受影响
        policy = resolve_domain_policy("platform:inst1", user_key=speaker_key)
        assert policy.memory_write is False and policy.memory_read is True

        svc = ContextService()
        messages = [{"role": "user", "content": "小明: 大家好"}]
        out = await svc.inject_memory(
            messages, MAIN_AGENT_ID, "openai", thread_id="conv-group", llm_adapter=None,
            domain="platform:inst1", scene="platform", user_key=speaker_key,
            group_members=[{"sender_id": "20002", "sender_name": "小红", "user_key": other_key}],
        )

        content = out[0]["content"]
        assert out[0]["role"] == "system"
        assert "<user_memory>" in content
        # 说话成员轨完整注入
        assert "[当前用户记忆]" in content
        assert "说话人喜欢咖啡" in content
        # 群友画像块叠加在场成员，且说话成员不重复出现
        assert "[群友画像]" in content
        assert "[群友] 小红(20002)：" in content
        assert "小红是程序员" in content
        assert content.count("[群友]") == 1
        assert get_provider.call_count == 0
        # 原消息保留
        assert out[1] == messages[0]

    async def test_platform_inject_without_members_unchanged(
        self, clean_owner_engine, seeded_keys,
    ):
        speaker_key = group_member_user_key("qq_onebot", "inst1", "10001")
        _seed_member_track(seeded_keys, speaker_key, ["说话人喜欢咖啡"])

        svc = ContextService()
        messages = [{"role": "user", "content": "小明: 大家好"}]
        out = await svc.inject_memory(
            messages, MAIN_AGENT_ID, "openai", thread_id="conv-group2", llm_adapter=None,
            domain="platform:inst1", scene="platform", user_key=speaker_key,
        )
        content = out[0]["content"]
        assert "[当前用户记忆]" in content
        assert "说话人喜欢咖啡" in content
        assert "[群友画像]" not in content


class TestGroupChatMemberTracks:
    def test_collect_member_tracks_humans_only_dedup(self):
        from app.domains.social.group_chat import GroupChatManager

        msgs = [
            {"sender_id": "user", "sender_type": "user", "content": "早", "sender_name": "阿明"},
            {"sender_id": "agent_a", "sender_type": "agent", "content": "早呀"},
            {"sender_id": "user", "sender_type": "user", "content": "在吗", "sender_name": "阿明"},
            {"senderId": "guest1", "senderType": "user", "content": "camelCase"},
        ]
        members = GroupChatManager._collect_member_tracks(msgs, group_id="g1")
        assert len(members) == 2
        assert members[0]["user_key"] == "social_g1_guest1"  # 最近发言优先
        assert members[1]["user_key"] == "social_g1_user"
        assert members[1]["sender_name"] == "阿明"

    def test_collect_member_tracks_empty_and_cap(self):
        from app.domains.social.group_chat import GroupChatManager

        assert GroupChatManager._collect_member_tracks([], group_id="g1") == []
        assert GroupChatManager._collect_member_tracks(None, group_id="g1") == []

        msgs = [
            {"sender_id": f"u{i}", "sender_type": "user", "content": "hi"}
            for i in range(15)
        ]
        members = GroupChatManager._collect_member_tracks(msgs, group_id="g1")
        assert len(members) == 10  # 默认成员数上限
