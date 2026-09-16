"""users 轨道目录解析对群成员 user_key 形态的落点与防穿越回归（§8.5.10）。

覆盖：
- 群成员轨键 → memory/users/{user_key}/ 正确落点
- sanitize_track_key 对路径穿越/分隔符/纯点段/空串的拒绝
- group_member_user_key 任意脏输入产物均能通过轨道白名单
- MemoryStore.for_track / get_track_engine 对成员键的落点与行级隔离键
"""

import pytest

from app.core.domain_policy import TRACK_USERS, group_member_user_key
from app.engines.memory.memory_engine import get_track_engine
from app.engines.memory.store import MemoryStore, resolve_track_dir, sanitize_track_key


class TestResolveTrackDirMemberKeys:
    def test_member_key_lands_under_users(self, tmp_path):
        key = group_member_user_key("qq_onebot", "inst_1", "10001")
        track_dir = resolve_track_dir(TRACK_USERS, key, base_dir=tmp_path)
        assert track_dir == tmp_path / "users" / "qq_onebot_inst_1_10001"
        assert track_dir.parent == tmp_path / "users"

    def test_member_key_from_dirty_segments_lands_safely(self, tmp_path):
        # 特殊字符/穿越输入构造的键必须仍在 users/ 一级子目录内
        key = group_member_user_key("QQ Bot", "../../inst", "..")
        track_dir = resolve_track_dir(TRACK_USERS, key, base_dir=tmp_path)
        assert track_dir.parent == tmp_path / "users"
        assert track_dir == tmp_path / "users" / "qq_bot_.._.._inst__"

    def test_sanitize_track_key_rejects_traversal_and_separators(self):
        for bad in ("../evil", "a/b", "a\\b", "", ".", ".."):
            with pytest.raises(ValueError):
                sanitize_track_key(bad)

    def test_member_key_output_always_track_safe(self):
        # 任意脏输入经 group_member_user_key 清洗后必须能过轨道白名单
        nasty = [
            ("QQ OneBot", "../../inst", ".."),
            ("p", "i", "a/b\\c"),
            ("", "", "x"),
            ("p", "i", "../../etc/passwd"),
        ]
        for platform, identity, sender in nasty:
            key = group_member_user_key(platform, identity, sender)
            assert key
            assert sanitize_track_key(key) == key

    def test_for_track_store_dir_and_owner_key(self, tmp_path):
        key = group_member_user_key("qq", "inst1", "42")
        store = MemoryStore.for_track(TRACK_USERS, key, base_dir=tmp_path)
        assert store._path == tmp_path / "users" / "qq_inst1_42"
        # base_dir 在 DATA_DIR/memory 之外 → 属临时库模式，行级隔离键为 tmp:*

    def test_track_engine_uses_member_dir_under_users(self):
        engine = get_track_engine(TRACK_USERS, group_member_user_key("qq", "inst1", "42"))
        path = engine._store._path
        assert path.parent.name == "users"
        assert path.name == "qq_inst1_42"
        # 全局库模式（DATA_DIR/memory 下）行级隔离键：users:{user_key}
        assert engine._store.owner_key == "users:qq_inst1_42"
