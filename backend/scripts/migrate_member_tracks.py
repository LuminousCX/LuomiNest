"""三段键 → 统一人键 一次性迁移脚本（分册10 §16.1 接线的存量收尾）。

背景：platform_router/domain_policy 曾以 group_member_user_key 生成
``users:{platform}_{instance_id}_{sender_id}`` 三段键；接线 platform_user_key
后新写入统一为 ``users:{platform}_{sender_id}``。本脚本把旧三段键的记忆行
（memory_profiles / memory_facts / memory_summaries / memory_knowledge /
memory_daily / memory_vectors + memory_facts_fts 影子表）并入统一人键。

解析规则：旧键 = ``users:{platform}_{instance_id}_{sender_id}``。
instance_id 可能含下划线、sender_id 也可能含下划线，不能按分隔符盲拆，
必须用 platform_instances 表里的真实 instance_id 做最长前缀匹配；
匹配不上的键**不动**、只报告（宁漏勿错）。站内群聊 social 键不在平台
名单内，天然跳过。

用法（backend 目录下，建议停应用后执行）：
    python scripts/migrate_member_tracks.py            # dry-run，只打印计划
    python scripts/migrate_member_tracks.py --apply    # 备份后执行迁移
    python scripts/migrate_member_tracks.py --selftest # 内置解析用例自检
"""
import argparse
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 平台名清单（adapters platform_name 全集；前缀匹配按最长优先）
_KNOWN_PLATFORMS = [
    "qq_onebot", "qq_official", "game_websocket", "home_assistant",
    "mqtt_terminal", "rest_api", "telegram", "discord", "minecraft", "wechat",
]
_OLD_KEY_RE = re.compile(
    r"^users:(?P<platform>" + "|".join(sorted(_KNOWN_PLATFORMS, key=len, reverse=True)) + r")_(?P<rest>.+)$"
)

_OWNER_KEY_TABLES = [
    "memory_profiles",      # PK(owner_key, conversation_id) → 撞键跳过
    "memory_facts",         # PK(id) 全表唯一，改 owner_key 不涉 id
    "memory_summaries",     # PK(owner_key, conversation_id, section) → 撞键跳过
    "memory_knowledge",     # PK(owner_key, conversation_id) → 撞键跳过
    "memory_daily",         # PK(id autoincrement) → 直接改
    "memory_vectors",       # PK(fact_id) 与 facts.id 同步，无独立冲突面
]
# 复合主键含 owner_key 的表：目标行已存在时跳过该行（报人工复核）
_COMPOSITE_PK_TABLES = {"memory_profiles", "memory_summaries", "memory_knowledge"}
# 各表主键中除 owner_key 外的列（撞行检测只比对主键，不比对整行）
_COMPOSITE_PK_OTHER_COLS = {
    "memory_profiles": ["conversation_id"],
    "memory_summaries": ["conversation_id", "section"],
    "memory_knowledge": ["conversation_id"],
}


def load_instance_ids(conn: sqlite3.Connection) -> list[str]:
    """platform_instances 真实实例清单（历史遗留键可能引用已删实例，漏网仅报告）。"""
    try:
        rows = conn.execute("SELECT id FROM platform_instances").fetchall()
        return sorted({str(r[0]) for r in rows if r[0]}, key=len, reverse=True)
    except sqlite3.OperationalError:
        return []


def split_old_key(old_owner_key: str, instance_ids: list[str]) -> str | None:
    """users:{platform}_{inst}_{sender} → users:{platform}_{sender}；不可信解析返回 None。

    inst 取真实实例清单最长前缀匹配；sender 为其余部分（可含下划线）。
    """
    m = _OLD_KEY_RE.match(old_owner_key)
    if not m:
        return None
    rest = m.group("rest")
    for inst in sorted(instance_ids, key=len, reverse=True):
        if rest.startswith(f"{inst}_") and len(rest) > len(inst) + 1:
            return f"users:{m.group('platform')}_{rest[len(inst) + 1:]}"
    return None


def migrate(conn: sqlite3.Connection, apply: bool) -> int:
    instance_ids = load_instance_ids(conn)
    if not instance_ids:
        print("[!] platform_instances 表为空/不存在：无法可信拆分三段键，仅报告。")

    # 1. 收集全部 owner_key，解析出 old→new 映射
    all_keys: set[str] = set()
    for table in _OWNER_KEY_TABLES:
        try:
            rows = conn.execute(f"SELECT DISTINCT owner_key FROM {table}").fetchall()
        except sqlite3.OperationalError as e:
            print(f"[!] {table} 不可读，跳过: {e}")
            continue
        all_keys.update(str(r[0]) for r in rows)

    mapping: dict[str, str] = {}
    unparseable: list[str] = []
    for key in sorted(all_keys):
        new_key = split_old_key(key, instance_ids) if instance_ids else None
        if new_key:
            mapping[key] = new_key
        elif _OLD_KEY_RE.match(key):
            unparseable.append(key)

    print(f"发现旧三段键 {len(mapping)} 把，不可解析仅报告 {len(unparseable)} 把")
    for key in unparseable:
        print(f"  [人工复核] {key}")
    if not mapping:
        print("无待迁移数据，结束。")
        return 0
    for old, new in sorted(mapping.items()):
        print(f"  {old}  ->  {new}")

    if not apply:
        print("\n(dry-run 未改库；确认后加 --apply 执行)")
        return 0

    # 2. 逐映射迁移（单事务）；facts 撞 id 改号，复合主键撞行跳过
    migrated_rows = 0
    try:
        for old, new in mapping.items():
            fact_id_map: dict[str, str] = {}  # 原 fact_id → 当前 fact_id（改键不改号）
            for table in _OWNER_KEY_TABLES:
                rows = conn.execute(
                    f"SELECT rowid, * FROM {table} WHERE owner_key = ?", (old,)
                ).fetchall()
                if not rows:
                    continue
                cols = ["rowid"] + [
                    d[0] for d in conn.execute(f"SELECT * FROM {table} LIMIT 0").description
                ]
                for row in rows:
                    rowdict = dict(zip(cols, row))
                    rowid = rowdict.pop("rowid")
                    if table in _COMPOSITE_PK_TABLES:
                        pk_cols = _COMPOSITE_PK_OTHER_COLS[table]
                        where = " AND ".join(f"{k} = ?" for k in pk_cols)
                        clash = conn.execute(
                            f"SELECT 1 FROM {table} WHERE owner_key = ? AND {where}",
                            (new, *(rowdict[k] for k in pk_cols)),
                        ).fetchone()
                        if clash:
                            print(f"  [跳过·目标行已存在] {table} rowid={rowid} → 人工复核")
                            continue
                    if table == "memory_facts":
                        fact_id_map[rowdict["id"]] = rowdict["id"]
                    sets = ", ".join(f"{k} = ?" for k in rowdict if k != "owner_key")
                    params = [rowdict[k] for k in rowdict if k != "owner_key"]
                    conn.execute(
                        f"UPDATE {table} SET owner_key = ?, {sets} WHERE rowid = ?",
                        (new, *params, rowid),
                    )
                    migrated_rows += 1
            # FTS 影子表：被移动的 fact 全部删旧插新（纯派生物，按主库现值重建行）
            try:
                for fact_id, _cur in fact_id_map.items():
                    src = conn.execute(
                        "SELECT content, conversation_id FROM memory_facts WHERE id = ?",
                        (fact_id,),
                    ).fetchone()
                    if not src:
                        continue
                    conn.execute("DELETE FROM memory_facts_fts WHERE fact_id = ?", (fact_id,))
                    conn.execute(
                        "INSERT INTO memory_facts_fts"
                        "(content, fact_id, owner_key, conversation_id) VALUES (?, ?, ?, ?)",
                        (src[0], fact_id, new, src[1]),
                    )
            except sqlite3.OperationalError as e:
                # FTS5 不可用的库没有该虚表；BM25 腿可重建，不影响主存储
                print(f"  [!] FTS 影子表更新跳过: {e}")
        conn.commit()
        print(f"迁移完成：共改写 {migrated_rows} 行（备份见 .bak）")
    except Exception:
        conn.rollback()
        raise
    return migrated_rows


def _selftest() -> None:
    cases = [
        # (旧键, 实例清单, 期望)
        ("users:qq_onebot_inst1_10001", ["inst1"], "users:qq_onebot_10001"),
        ("users:qq_onebot_inst_1_10001", ["inst_1"], "users:qq_onebot_10001"),
        ("users:rest_api_webui_10001", ["webui"], "users:rest_api_10001"),
        ("users:qq_onebot_i1_user_99", ["i1"], "users:qq_onebot_user_99"),
        ("users:qq_onebot_10001", ["inst1"], None),          # 已是新键，不动
        ("users:qq_onebot_ghost_1", ["inst1"], None),        # 未知实例，报告不动
        ("owner:main", ["inst1"], None),                     # 非平台键
        ("tmp:abc", ["inst1"], None),
    ]
    for old, insts, expect in cases:
        got = split_old_key(old, insts)
        assert got == expect, f"split_old_key({old!r}, {insts}) = {got!r}, 期望 {expect!r}"
    print("selftest OK")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="实际执行（默认 dry-run）")
    parser.add_argument("--selftest", action="store_true", help="运行内置解析用例")
    args = parser.parse_args()
    if args.selftest:
        _selftest()
        return

    from app.core.config import settings

    db_path = re.sub(r"^sqlite(\+\w+)?:///", "", settings.DATABASE_URL)
    src = Path(db_path)
    if not src.exists():
        print(f"[!] 数据库不存在: {src}")
        return
    bak = src.with_suffix(src.suffix + ".pre-member-migration.bak")
    conn = sqlite3.connect(src)
    if args.apply:
        conn.backup(sqlite3.connect(bak))
        print(f"已备份: {bak}")
    try:
        migrate(conn, apply=args.apply)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
