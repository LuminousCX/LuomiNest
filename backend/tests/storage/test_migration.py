"""Phase 7 测试: JSON→SQLite 迁移幂等性 + 空库 + 有数据迁移。

测试场景：
1. 空库迁移（无 JSON 文件 → 全部标记已迁移，0 records）
2. 有数据迁移（创建样例 JSON → 迁移 → 验证 DB 数据正确）
3. 幂等性（再跑一次 → 全部 0，数据不变）
4. _migration_meta 表正确标记
5. 字段名转换（marketplace_stats camelCase → snake_case）
6. 双格式对话迁移（merged dict + per-file）
"""
import os
import sys
import json
import tempfile
import asyncio
import shutil

TEMP_DATA = tempfile.mkdtemp(prefix="luominest_test_mig_")
os.environ["DATA_DIR"] = TEMP_DATA
os.environ["SECRET_KEY"] = "test-key-not-for-production-use"
sys.path.insert(0, r"d:\Projects\Project\LuomiNest\backend")

from app.infrastructure.database import init_db, dispose_db
asyncio.run(init_db())

passed = 0
failed = 0


def check(name: str, cond: bool, detail: str = ""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        print(f"  FAIL: {name}" + (f" ({detail})" if detail else ""))


def write_json(rel_path: str, data):
    """在 TEMP_DATA 下写 JSON 文件。"""
    full = os.path.join(TEMP_DATA, rel_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


from app.infrastructure.database.migration import migrate_all_json_to_sqlite
from app.infrastructure.database.facades.json_store_facade import (
    agents_store, groups_store, platforms_store, repo_sources_store,
)
from app.infrastructure.database.facades.marketplace_stats_store import marketplace_stats_store
from app.infrastructure.database.config_store import luominest_config_store
from app.infrastructure.database.usage_store import usage_store
from app.infrastructure.database.conversation_store import conversation_store
from app.infrastructure.database.facades.main_agent_config import (
    load_luominest_main_agent_config, save_luominest_main_agent_config,
)
from app.infrastructure.database.models.migration_meta import MigrationMeta
from app.infrastructure.database.session import sync_session_factory


def get_migration_meta(source: str):
    with sync_session_factory() as session:
        return session.get(MigrationMeta, source)


# ════════════════════════════════════════════════════
# 1. 空库迁移（无 JSON 文件）
# ════════════════════════════════════════════════════
print("\n=== 1. 空库迁移（无 JSON 文件）===")
results1 = asyncio.run(migrate_all_json_to_sqlite())
print(f"  迁移结果: {results1}")

# 所有数据源应返回 0（无文件 → 标记已迁移）
for source_name in ["agents", "groups", "platforms", "repo_sources",
                     "marketplace_stats", "usage_records", "user_config",
                     "main_agent", "model_config", "conversations"]:
    check(f"空库 {source_name} returns 0", results1.get(source_name) == 0,
          f"got={results1.get(source_name)}")

# _migration_meta 应全部标记
for source_name in ["agents", "groups", "platforms", "repo_sources",
                     "marketplace_stats", "usage_records", "user_config",
                     "main_agent", "model_config", "conversations"]:
    meta = get_migration_meta(source_name)
    check(f"_migration_meta[{source_name}] marked", meta is not None)


# ════════════════════════════════════════════════════
# 2. 有数据迁移
# ════════════════════════════════════════════════════
print("\n=== 2. 有数据迁移 ===")

# 先清空 _migration_meta 以模拟未迁移状态
from sqlalchemy import delete as sa_delete
with sync_session_factory() as session:
    session.execute(sa_delete(MigrationMeta))
    session.commit()

# 创建样例 JSON 文件
# agents.json — JsonStore dict 格式
write_json("store/agents.json", {
    "agent-mig-1": {
        "id": "agent-mig-1",
        "name": "迁移测试Agent",
        "description": "从 JSON 迁移",
        "model": "gpt-4o",
        "provider": "openai",
        "is_active": True,
        "is_main": False,
    },
    "agent-mig-2": {
        "id": "agent-mig-2",
        "name": "第二个Agent",
        "is_main": True,
    },
})

# groups.json
write_json("store/groups.json", {
    "group-mig-1": {
        "id": "group-mig-1",
        "name": "迁移测试群组",
        "members": [{"agent_id": "a", "type": "agent"}],
    },
})

# platforms.json
write_json("store/platforms.json", {
    "plat-mig-1": {
        "id": "plat-mig-1",
        "name": "QQ迁移",
        "adapter_type": "qq",
        "config": {"qq": 12345},
    },
})

# repo_sources.json
write_json("store/repo_sources.json", {
    "repo-mig-1": {
        "id": "repo-mig-1",
        "name": "迁移仓库",
        "url": "https://github.com/test/repo.git",
        "type": "git",
    },
})

# marketplace_stats.json — camelCase 字段
write_json("store/marketplace_stats.json", {
    "plugin-mig-1": {
        "downloadCount": 42,
        "likeCount": 3,
        "type": "plugin",
        "__likes__": {"liked_ids": ["user-a", "user-b"]},
    },
    "__user_likes__": {"liked_ids": ["user-a"]},
})

# usage_records.json — JSON 数组
write_json("store/usage_records.json", [
    {"timestamp": "2026-01-01T00:00:00+00:00", "provider": "openai", "model": "gpt-4o",
     "prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    {"timestamp": "2026-01-02T00:00:00+00:00", "provider": "anthropic", "model": "claude",
     "prompt_tokens": 200, "completion_tokens": 100, "total_tokens": 300},
])

# user_config.json — flat KV（__updated_at 为后缀格式，迁移时跳过）
write_json("config/user_config.json", {
    "llm.default_provider": "openai",
    "ui.theme": "dark",
    "llm.default_provider__updated_at": "2026-01-01T00:00:00+00:00",
})

# main_agent.json
write_json("main_agent.json", {
    "provider": "openai",
    "model": "gpt-4o",
    "system_prompt": "你是主Agent",
    "temperature": 0.7,
    "max_tokens": 4096,
})

# model_config.json
write_json("model_config.json", {
    "default_provider": "openai",
    "default_model": "gpt-4o-mini",
    "default_temperature": 0.8,
    "default_max_tokens": 8192,
    "default_top_p": 0.9,
})

# conversations — per-file 格式
write_json("conversations/conv-mig-1.json", {
    "id": "conv-mig-1",
    "title": "迁移对话1",
    "agent_id": "agent-mig-1",
    "model": "gpt-4o",
    "provider": "openai",
    "messages": [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好！"},
    ],
})
write_json("conversations/_index.json", {
    "conv-mig-1": {"title": "迁移对话1", "agent_id": "agent-mig-1"},
})

# 执行迁移
results2 = asyncio.run(migrate_all_json_to_sqlite())
print(f"  迁移结果: {results2}")

# 验证迁移数量
check("agents migrated 2", results2.get("agents") == 2, f"got={results2.get('agents')}")
check("groups migrated 1", results2.get("groups") == 1)
check("platforms migrated 1", results2.get("platforms") == 1)
check("repo_sources migrated 1", results2.get("repo_sources") == 1)
check("marketplace_stats migrated 1", results2.get("marketplace_stats") == 1)
check("usage_records migrated 2", results2.get("usage_records") == 2)
check("user_config migrated 2 (skips __updated_at)",
      results2.get("user_config") == 2, f"got={results2.get('user_config')}")
check("main_agent migrated 1", results2.get("main_agent") == 1)
check("model_config migrated 1", results2.get("model_config") == 1)
check("conversations migrated 1", results2.get("conversations") == 1)

# ════════════════════════════════════════════════════
# 3. 验证迁移后的数据
# ════════════════════════════════════════════════════
print("\n=== 3. 验证迁移后数据 ===")

# agents
agent = agents_store.get("agent-mig-1")
check("agent migrated correctly", agent is not None and agent["name"] == "迁移测试Agent")

# groups
group = groups_store.get("group-mig-1")
check("group migrated correctly", group is not None and group["name"] == "迁移测试群组")

# platforms
plat = platforms_store.get("plat-mig-1")
check("platform migrated correctly", plat is not None and plat["adapter_type"] == "qq")

# repo_sources
repo = repo_sources_store.get("repo-mig-1")
check("repo_source migrated correctly", repo is not None and repo["name"] == "迁移仓库")

# marketplace_stats — 字段名转换
stat = marketplace_stats_store.get("plugin-mig-1")
check("marketplace_stat download_count (from downloadCount)",
      stat is not None and stat["download_count"] == 42, f"got={stat}")
check("marketplace_stat like_count (from likeCount)", stat["like_count"] == 3)
check("marketplace_stat liked_by (from __likes__.liked_ids)",
      stat["liked_by"] == ["user-a", "user-b"], f"got={stat.get('liked_by')}")

# usage_records
usage_recs = usage_store.get_records()
check("usage_records migrated 2 entries", len(usage_recs) == 2, f"count={len(usage_recs)}")
check("usage_records first provider", usage_recs[0]["provider"] in ("openai", "anthropic"))

# user_config (写入 luominest_config_store)
check("user_config llm.default_provider migrated",
      luominest_config_store.get("llm.default_provider") == "openai")
check("user_config ui.theme migrated", luominest_config_store.get("ui.theme") == "dark")
check("user_config __updated_at NOT migrated",
      luominest_config_store.get("llm.default_provider__updated_at") is None)

# main_agent
main_agent = load_luominest_main_agent_config()
check("main_agent provider migrated", main_agent.get("provider") == "openai")
check("main_agent model migrated", main_agent.get("model") == "gpt-4o")
check("main_agent system_prompt migrated", main_agent.get("system_prompt") == "你是主Agent")

# model_config
model_cfg = luominest_config_store.get("model_config")
check("model_config migrated as dict", isinstance(model_cfg, dict))
check("model_config default_provider", model_cfg.get("default_provider") == "openai")
check("model_config default_model", model_cfg.get("default_model") == "gpt-4o-mini")

# conversations
conv = conversation_store.get("conv-mig-1")
check("conversation migrated", conv is not None and conv["title"] == "迁移对话1")
check("conversation messages migrated", len(conv["messages"]) == 2)

# _migration_meta 表
for source_name in ["agents", "groups", "platforms", "repo_sources",
                     "marketplace_stats", "usage_records", "user_config",
                     "main_agent", "model_config", "conversations"]:
    meta = get_migration_meta(source_name)
    check(f"_migration_meta[{source_name}] has record_count > 0",
          meta is not None and meta.record_count > 0, f"meta={meta}")


# ════════════════════════════════════════════════════
# 4. 幂等性 — 再跑一次
# ════════════════════════════════════════════════════
print("\n=== 4. 幂等性 ===")
results3 = asyncio.run(migrate_all_json_to_sqlite())
print(f"  二次迁移结果: {results3}")

for source_name in ["agents", "groups", "platforms", "repo_sources",
                     "marketplace_stats", "usage_records", "user_config",
                     "main_agent", "model_config", "conversations"]:
    check(f"幂等 {source_name} returns 0", results3.get(source_name) == 0,
          f"got={results3.get(source_name)}")

# 数据不变
check("agents data unchanged after re-migrate",
      agents_store.get("agent-mig-1") is not None)
check("marketplace_stats data unchanged",
      marketplace_stats_store.get("plugin-mig-1")["download_count"] == 42)
check("usage_records not duplicated",
      len(usage_store.get_records()) == 2)
check("conversations not duplicated",
      len(conversation_store.list_conversations()) == 1)


# ════════════════════════════════════════════════════
# 清理
# ════════════════════════════════════════════════════
asyncio.run(dispose_db())
shutil.rmtree(TEMP_DATA, ignore_errors=True)

print(f"\n{'=' * 60}")
print(f"test_migration 结果: {passed} passed, {failed} failed")
print(f"{'=' * 60}")
sys.exit(0 if failed == 0 else 1)
