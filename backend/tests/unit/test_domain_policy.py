"""DomainPolicy 群成员轨（§8.5.10 本期实现）回归测试。

覆盖：
- 群聊 + sender_id → {platform}_{identity}_{sender_id} 成员轨（按「人」不按「群」）
- 无 sender_id 群消息维持现状（不建用户轨，开关开着也不写）
- platform_memory_write 开关对写的闸门（读不受限）
- 段清洗：小写化、特殊字符替换、路径穿越尝试、"."/".." 段防御、段长上限
- 向后兼容：workbench / agent:{id} / 私聊路径行为不变
"""

from app.core.domain_policy import (
    KIND_PLATFORM,
    TRACK_OWNER,
    TRACK_USERS,
    DomainPolicy,
    group_member_user_key,
    resolve_domain_policy,
    sanitize_key_segment,
)


class TestGroupMemberUserKey:
    def test_format_platform_identity_sender(self):
        assert group_member_user_key("qq_onebot", "inst_1", "10001") == "qq_onebot_inst_1_10001"

    def test_same_person_same_track_across_groups(self):
        # 按「人」不按「群」：identity 是平台实例标识，与群 id 无关
        a = group_member_user_key("qq_onebot", "inst_1", "10001")
        b = group_member_user_key("qq_onebot", "inst_1", "10001")
        assert a == b

    def test_different_instance_different_track(self):
        assert group_member_user_key("qq_onebot", "inst_1", "10001") != (
            group_member_user_key("qq_onebot", "inst_2", "10001")
        )

    def test_empty_sender_id_returns_empty(self):
        assert group_member_user_key("qq_onebot", "inst_1", "") == ""
        assert group_member_user_key("qq_onebot", "inst_1", "   ") == ""

    def test_lowercase_and_special_chars_replaced(self):
        assert group_member_user_key("QQ OneBot", "Inst#1", "User@01") == "qq_onebot_inst_1_user_01"

    def test_path_traversal_neutralized(self):
        key = group_member_user_key("qq", "i", "../../etc/passwd")
        assert "/" not in key and "\\" not in key
        assert key == "qq_i_.._.._etc_passwd"

    def test_dot_segment_guard(self):
        assert sanitize_key_segment(".") == "_"
        assert sanitize_key_segment("..") == "_"
        assert sanitize_key_segment("") == "_"

    def test_segments_capped_within_track_whitelist_length(self):
        key = group_member_user_key("p" * 100, "i" * 100, "s" * 100)
        assert len(key) <= 128  # 与 store.sanitize_track_key 白名单长度上限一致


class TestResolveDomainPolicyGroupMember:
    DOMAIN = "platform:inst_1"

    def test_group_with_sender_id_builds_member_track(self):
        policy = resolve_domain_policy(self.DOMAIN, sender_id="10001", platform_name="qq_onebot")
        assert policy.kind == KIND_PLATFORM
        assert policy.memory_read is True
        assert policy.memory_track == TRACK_USERS
        assert policy.track_user_key == "qq_onebot_inst_1_10001"
        # 写开关默认关
        assert policy.memory_write is False

    def test_group_write_gated_by_platform_switch(self):
        off = resolve_domain_policy(
            self.DOMAIN, sender_id="10001", platform_name="qq_onebot", platform_memory_write=False,
        )
        on = resolve_domain_policy(
            self.DOMAIN, sender_id="10001", platform_name="qq_onebot", platform_memory_write=True,
        )
        assert off.memory_write is False
        assert on.memory_write is True
        # 开关只闸写，不闸读/轨道归属
        assert on.memory_read is True and off.memory_read is True
        assert on.memory_track == TRACK_USERS == off.memory_track

    def test_group_without_sender_id_keeps_status_quo(self):
        policy = resolve_domain_policy(self.DOMAIN, user_key="")
        assert policy.memory_read is True
        assert policy.memory_track is None
        assert policy.track_user_key == ""
        assert policy.memory_write is False

    def test_group_without_sender_id_no_write_even_with_switch(self):
        policy = resolve_domain_policy(self.DOMAIN, user_key="", platform_memory_write=True)
        assert policy.memory_write is False

    def test_platform_name_falls_back_to_instance_id(self):
        policy = resolve_domain_policy(self.DOMAIN, sender_id="42")
        assert policy.track_user_key == "inst_1_inst_1_42"

    def test_private_chat_user_key_unchanged(self):
        policy = resolve_domain_policy(self.DOMAIN, user_key="qq_onebot_10001")
        assert policy.memory_track == TRACK_USERS
        assert policy.track_user_key == "qq_onebot_10001"
        assert policy.memory_write is False

    def test_explicit_user_key_takes_precedence_over_sender_id(self):
        policy = resolve_domain_policy(
            self.DOMAIN, user_key="qq_onebot_10001", sender_id="10001", platform_name="qq_onebot",
        )
        assert policy.track_user_key == "qq_onebot_10001"


class TestResolveDomainPolicyBackwardCompat:
    def test_workbench_owner_track(self):
        policy = resolve_domain_policy("workbench")
        assert policy.memory_track == TRACK_OWNER
        assert policy.memory_write is True
        assert policy.track_user_key == ""

    def test_workbench_by_main_agent_fallback(self):
        policy = resolve_domain_policy("", agent_id="luominest_main_agent")
        assert policy.memory_track == TRACK_OWNER

    def test_agent_domain_no_memory(self):
        policy = resolve_domain_policy("agent:helper")
        assert policy.memory_read is False
        assert policy.memory_write is False
        assert policy.memory_track is None

    def test_unknown_domain_conservative(self):
        policy = resolve_domain_policy("weird:domain")
        assert policy.memory_read is False
        assert policy.memory_write is False

    def test_domain_policy_new_field_defaults_empty(self):
        # 新增 track_user_key 字段带默认值：既有构造方式不被破坏
        policy = DomainPolicy(KIND_PLATFORM, True, False, None, "standard")
        assert policy.track_user_key == ""
