"""Phase 7 测试: Repository 层 CRUD + AES 加密 + 原子增。

覆盖 8 个 Repository：
- ConfigRepository: KV + AES 加密 + namespace + list_all 脱敏
- AgentRepository: CRUD + get_all_non_main + exists_by_name + mutate
- GroupRepository: CRUD
- PlatformInstanceRepository: CRUD
- RepoSourceRepository: CRUD
- MarketplaceStatRepository: get_or_create + increment_download + toggle_like + get_liked_items
- UsageRepository: record + get_records + trim + bulk_import + get_summary
- ConversationRepository: save(自动 search_text) + list_meta + search + soft_delete + restore + rename
"""
import os
import sys
import tempfile
import asyncio
import shutil

TEMP_DATA = tempfile.mkdtemp(prefix="luominest_test_repo_")
os.environ["DATA_DIR"] = TEMP_DATA
os.environ["SECRET_KEY"] = "test-key-not-for-production-use"
sys.path.insert(0, r"D:/Projects/My_Projects/LuomiNest/backend")

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


# ════════════════════════════════════════════════════
# 1. ConfigRepository — KV + AES 加密 + namespace
# ════════════════════════════════════════════════════
print("\n=== 1. ConfigRepository ===")
from app.infrastructure.database.repositories import ConfigRepository

config_repo = ConfigRepository()

# 基本 KV
config_repo.set("test.str", "hello")
check("set/get string", config_repo.get("test.str") == "hello")

config_repo.set("test.dict", {"a": 1, "b": [2, 3]})
check("set/get dict", config_repo.get("test.dict") == {"a": 1, "b": [2, 3]})

config_repo.set("test.list", [1, "x", True])
check("set/get list", config_repo.get("test.list") == [1, "x", True])

config_repo.set("test.int", 42)
check("set/get int", config_repo.get("test.int") == 42)

check("get default for missing", config_repo.get("nonexistent", "default") == "default")

# delete
check("delete existing", config_repo.delete("test.str") is True)
check("get after delete returns default", config_repo.get("test.str", None) is None)
check("delete missing returns False", config_repo.delete("nonexistent") is False)

# AES 加密：llm.providers.*.api_key 自动加解密
config_repo.set("llm.providers.openai.api_key", "sk-secret-key-123")
decrypted = config_repo.get("llm.providers.openai.api_key")
check("AES decrypt api_key", decrypted == "sk-secret-key-123", f"got={decrypted!r}")

# list_all 应脱敏（返回 "***" 而非明文）
all_cfg = config_repo.list_all()
check("list_all masks encrypted api_key", all_cfg.get("llm.providers.openai.api_key") == "***",
      f"got={all_cfg.get('llm.providers.openai.api_key')!r}")

# namespace
config_repo.set("llm.providers.openai.name", "OpenAI")
config_repo.set("llm.providers.ollama.api_key", "ollama")
config_repo.set("llm.providers.ollama.name", "Ollama")
ns = config_repo.get_namespace("llm.providers.")
check("get_namespace returns all keys under prefix",
      "llm.providers.openai.api_key" in ns and "llm.providers.ollama.name" in ns,
      f"keys={list(ns.keys())}")
check("get_namespace decrypts api_key",
      ns.get("llm.providers.openai.api_key") == "sk-secret-key-123")
check("get_namespace decrypts ollama api_key",
      ns.get("llm.providers.ollama.api_key") == "ollama")

# delete_namespace
deleted_count = config_repo.delete_namespace("llm.providers.")
check("delete_namespace removes all prefixed keys", deleted_count >= 4, f"count={deleted_count}")
remaining_ns = config_repo.get_namespace("llm.providers.")
check("namespace empty after delete_namespace", len(remaining_ns) == 0)


# ════════════════════════════════════════════════════
# 2. AgentRepository — CRUD + 扩展方法
# ════════════════════════════════════════════════════
print("\n=== 2. AgentRepository ===")
from app.infrastructure.database.repositories import AgentRepository

agent_repo = AgentRepository()

agent_data = {
    "name": "测试Agent",
    "description": "测试用",
    "system_prompt": "你是测试助手",
    "model": "gpt-4o-mini",
    "provider": "openai",
    "is_active": True,
    "is_main": False,
}
created = agent_repo.save("agent-1", agent_data)
check("save creates agent", created is not None and created["name"] == "测试Agent")
check("save sets id", created.get("id") == "agent-1")

retrieved = agent_repo.get("agent-1")
check("get returns saved agent", retrieved is not None and retrieved["name"] == "测试Agent")

# update (partial)
updated = agent_repo.update("agent-1", {"description": "更新后的描述"})
check("update partial field", updated["description"] == "更新后的描述")
check("update preserves other fields", updated["name"] == "测试Agent")

# save again (upsert)
agent_repo.save("agent-1", {"name": "新名字", "model": "claude", "provider": "anthropic"})
retrieved2 = agent_repo.get("agent-1")
check("save upsert updates name", retrieved2["name"] == "新名字")
check("save upsert updates model", retrieved2["model"] == "claude")

# 第二个 Agent（main）
agent_repo.save("agent-main", {"name": "主Agent", "is_main": True, "is_active": True})
agent_repo.save("agent-2", {"name": "副Agent", "is_main": False, "is_active": True})

all_agents = agent_repo.get_all()
check("get_all returns all agents", len(all_agents) == 3, f"count={len(all_agents)}")

non_main = agent_repo.get_all_non_main()
check("get_all_non_main excludes main", len(non_main) == 2, f"count={len(non_main)}")
check("get_all_non_main all is_main=False", all(not a.get("is_main") for a in non_main))

check("exists_by_name finds existing", agent_repo.exists_by_name("新名字") is True)
check("exists_by_name excludes id", agent_repo.exists_by_name("新名字", "agent-1") is False)
check("exists_by_name missing returns False", agent_repo.exists_by_name("不存在") is False)

# mutate (atomic read-modify-write)
def add_prefix(current):
    if current is None:
        return None
    new_val = dict(current)
    new_val["name"] = f"[prefix] {new_val['name']}"
    return new_val

mutated = agent_repo.mutate("agent-2", add_prefix)
check("mutate applies updater", mutated["name"] == "[prefix] 副Agent")

# delete
check("delete existing agent", agent_repo.delete("agent-2") is True)
check("get deleted returns None", agent_repo.get("agent-2") is None)
check("delete missing returns False", agent_repo.delete("agent-2") is False)


# ════════════════════════════════════════════════════
# 3. GroupRepository — CRUD
# ════════════════════════════════════════════════════
print("\n=== 3. GroupRepository ===")
from app.infrastructure.database.repositories import GroupRepository

group_repo = GroupRepository()
group_repo.save("group-1", {"name": "测试群组", "description": "群组描述",
                            "members": [{"agent_id": "a", "type": "agent"}, {"agent_id": "b", "type": "human"}]})
g = group_repo.get("group-1")
check("save/get group", g is not None and g["name"] == "测试群组")
check("group members persisted", g["members"] == [{"agent_id": "a", "type": "agent"}, {"agent_id": "b", "type": "human"}])

group_repo.save("group-2", {"name": "群组2"})
check("get_all groups", len(group_repo.get_all()) == 2)

check("delete group", group_repo.delete("group-2") is True)
check("get deleted group None", group_repo.get("group-2") is None)


# ════════════════════════════════════════════════════
# 4. PlatformInstanceRepository — CRUD
# ════════════════════════════════════════════════════
print("\n=== 4. PlatformInstanceRepository ===")
from app.infrastructure.database.repositories import PlatformRepository

platform_repo = PlatformRepository()
platform_repo.save("plat-1", {
    "name": "QQ测试",
    "adapter_type": "qq",
    "config": {"qq": 12345},
    "is_active": True,
})
p = platform_repo.get("plat-1")
check("save/get platform", p is not None and p["name"] == "QQ测试")
check("platform adapter_type persisted", p["adapter_type"] == "qq")
check("platform config dict persisted", p["config"] == {"qq": 12345})

check("delete platform", platform_repo.delete("plat-1") is True)


# ════════════════════════════════════════════════════
# 5. RepoSourceRepository — CRUD
# ════════════════════════════════════════════════════
print("\n=== 5. RepoSourceRepository ===")
from app.infrastructure.database.repositories import RepoSourceRepository

repo_repo = RepoSourceRepository()
repo_repo.save("repo-1", {"name": "测试仓库", "url": "https://github.com/test/repo.git", "type": "git"})
r = repo_repo.get("repo-1")
check("save/get repo_source", r is not None and r["name"] == "测试仓库")
check("repo url persisted", r["url"] == "https://github.com/test/repo.git")

check("delete repo_source", repo_repo.delete("repo-1") is True)


# ════════════════════════════════════════════════════
# 6. MarketplaceStatRepository — 原子增 + toggle_like
# ════════════════════════════════════════════════════
print("\n=== 6. MarketplaceStatRepository ===")
from app.infrastructure.database.repositories import MarketplaceStatRepository

stat_repo = MarketplaceStatRepository()

# get_or_create
stat = stat_repo.get_or_create("plugin-1", "plugin")
check("get_or_create creates new", stat is not None and stat["item_id"] == "plugin-1")
check("get_or_create init download_count=0", stat["download_count"] == 0)
check("get_or_create init like_count=0", stat["like_count"] == 0)

stat_again = stat_repo.get_or_create("plugin-1", "plugin")
check("get_or_create idempotent", stat_again["download_count"] == 0)

# increment_download (原子增)
stat_repo.increment_download("plugin-1", "plugin")
stat_repo.increment_download("plugin-1")
stat_repo.increment_download("plugin-1")
after_dl = stat_repo.get("plugin-1")
check("increment_download 3x → 3", after_dl["download_count"] == 3, f"got={after_dl['download_count']}")

# increment_download on non-existent creates with 1
stat_repo.increment_download("plugin-2", "plugin")
check("increment_download creates if missing", stat_repo.get("plugin-2")["download_count"] == 1)

# toggle_like
stat_repo.toggle_like("plugin-1", "user-A", "plugin")
stat_repo.toggle_like("plugin-1", "user-B", "plugin")
after_like = stat_repo.get("plugin-1")
check("toggle_like adds 2 → like_count=2", after_like["like_count"] == 2, f"got={after_like['like_count']}")
check("toggle_like liked_by has both users",
      "user-A" in after_like["liked_by"] and "user-B" in after_like["liked_by"])

# toggle_like again removes
stat_repo.toggle_like("plugin-1", "user-A", "plugin")
after_unlike = stat_repo.get("plugin-1")
check("toggle_like removes → like_count=1", after_unlike["like_count"] == 1, f"got={after_unlike['like_count']}")
check("toggle_like removes user from liked_by", "user-A" not in after_unlike["liked_by"])

# get_liked_items
liked = stat_repo.get_liked_items("user-B")
check("get_liked_items returns liked items", "plugin-1" in liked, f"got={liked}")

# delete + delete_all
check("delete stat", stat_repo.delete("plugin-1") is True)
check("get deleted stat None", stat_repo.get("plugin-1") is None)

stat_repo.delete_all()
check("delete_all clears all", len(stat_repo.get_all()) == 0)


# ════════════════════════════════════════════════════
# 7. UsageRepository — record + trim + summary
# ════════════════════════════════════════════════════
print("\n=== 7. UsageRepository ===")
from app.infrastructure.database.repositories import UsageRepository

usage_repo = UsageRepository()

# record
rec = usage_repo.record(provider="openai", model="gpt-4o", prompt_tokens=100,
                          completion_tokens=50, total_tokens=150, agent_id="agent-1",
                          conversation_id="conv-1", is_stream=True)
check("record returns entry", rec is not None and rec["provider"] == "openai")
check("record stores tokens", rec["total_tokens"] == 150)

usage_repo.record(provider="openai", model="gpt-4o", total_tokens=200)
usage_repo.record(provider="anthropic", model="claude", total_tokens=300)

# get_records
all_recs = usage_repo.get_records()
check("get_records returns all", len(all_recs) == 3, f"count={len(all_recs)}")

# get_summary
summary = usage_repo.get_summary()
check("summary total_requests", summary["total_requests"] == 3, f"got={summary['total_requests']}")
check("summary total_tokens", summary["total_tokens"] == 650, f"got={summary['total_tokens']}")
check("summary by_provider has openai", any(p["name"] == "openai" for p in summary["by_provider"]))
check("summary by_provider has anthropic", any(p["name"] == "anthropic" for p in summary["by_provider"]))

# bulk_import
import_data = [
    {"timestamp": "2026-01-01T00:00:00+00:00", "provider": "bulk", "model": "test",
     "prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    {"timestamp": "2026-01-02T00:00:00+00:00", "provider": "bulk", "model": "test",
     "prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
]
imported = usage_repo.bulk_import(import_data)
check("bulk_import returns count", imported == 2)
check("bulk_import adds records", len(usage_repo.get_records()) == 5)

# trim (保留最新 3 条)
trimmed = usage_repo.trim(3)
check("trim removes old records", trimmed == 2, f"trimmed={trimmed}")
check("trim leaves 3 records", len(usage_repo.get_records()) == 3)

# clear_all
cleared = usage_repo.clear_all()
check("clear_all returns count", cleared == 3, f"cleared={cleared}")
check("clear_all empties table", len(usage_repo.get_records()) == 0)


# ════════════════════════════════════════════════════
# 8. ConversationRepository — save + search + soft_delete
# ════════════════════════════════════════════════════
print("\n=== 8. ConversationRepository ===")
from app.infrastructure.database.repositories import ConversationRepository

conv_repo = ConversationRepository()

conv_data = {
    "title": "测试对话",
    "agent_id": "agent-1",
    "model": "gpt-4o",
    "provider": "openai",
    "messages": [
        {"role": "user", "content": "你好，请介绍一下你自己"},
        {"role": "assistant", "content": "你好！我是AI助手"},
        {"role": "user", "content": "你能做什么"},
        {"role": "assistant", "content": "我可以回答问题、写代码等"},
    ],
}
saved_conv = conv_repo.save("conv-1", conv_data)
check("save creates conversation", saved_conv is not None and saved_conv["title"] == "测试对话")
check("save auto-builds search_text", "你好" in (saved_conv.get("search_text") or ""))
check("save auto-builds last_message", saved_conv.get("last_message") is not None)
check("save sets created_at", saved_conv.get("created_at") != "")

retrieved_conv = conv_repo.get("conv-1")
check("get returns conversation", retrieved_conv is not None)
check("messages persisted as JSON list", len(retrieved_conv["messages"]) == 4)

# list_meta (不含 messages/search_text)
meta_list = conv_repo.list_meta()
check("list_meta returns 1 conversation", len(meta_list) == 1)
check("list_meta excludes messages", "messages" not in meta_list[0])
check("list_meta excludes search_text", "search_text" not in meta_list[0])

conv_repo.save("conv-2", {"title": "另一个", "agent_id": "agent-1", "messages": [{"role": "user", "content": "test"}]})
conv_repo.save("conv-3", {"title": "第三个", "agent_id": "agent-2", "messages": []})
check("list_meta all", len(conv_repo.list_meta()) == 3)
check("list_meta by agent_id", len(conv_repo.list_meta("agent-1")) == 2)

# search
results = conv_repo.search("你好")
check("search finds by content", len(results) >= 1, f"count={len(results)}")
check("search returns id", any(r["id"] == "conv-1" for r in results))
check("search returns snippet", "snippet" in results[0])

results_title = conv_repo.search("另一个")
check("search finds by title", len(results_title) == 1)

# soft_delete + trash
check("soft_delete moves to trash", conv_repo.soft_delete("conv-1") is True)
check("list_meta excludes soft-deleted", len(conv_repo.list_meta()) == 2)
check("list_trash shows deleted", len(conv_repo.list_trash()) == 1)

# restore
check("restore moves back", conv_repo.restore("conv-1") is True)
check("list_meta includes restored", len(conv_repo.list_meta()) == 3)
check("list_trash empty after restore", len(conv_repo.list_trash()) == 0)

# rename
check("rename updates title", conv_repo.rename("conv-1", "重命名的对话") is True)
renamed = conv_repo.get("conv-1")
check("rename persisted", renamed["title"] == "重命名的对话")

# permanent_delete
check("permanent_delete", conv_repo.permanent_delete("conv-3") is True)
check("get after permanent_delete None", conv_repo.get("conv-3") is None)

# batch operations
conv_repo.batch_soft_delete(["conv-1", "conv-2"])
check("batch_soft_delete", len(conv_repo.list_trash()) == 2)
conv_repo.batch_restore(["conv-1", "conv-2"])
check("batch_restore", len(conv_repo.list_trash()) == 0)


# ════════════════════════════════════════════════════
# 9. async wrappers
# ════════════════════════════════════════════════════
print("\n=== 9. Async wrappers ===")

async def test_async():
    agent_repo.save("async-agent", {"name": "异步Agent", "is_main": False})
    result = await agent_repo.get_async("async-agent")
    assert result is not None and result["name"] == "异步Agent"

    await agent_repo.delete_async("async-agent")
    assert await agent_repo.get_async("async-agent") is None

    stat_repo.get_or_create("async-stat", "plugin")
    s = await stat_repo.get_async("async-stat")
    assert s is not None and s["item_id"] == "async-stat"

    rec = await usage_repo.record_async(provider="async", model="test", total_tokens=10)
    assert rec["provider"] == "async"

asyncio.run(test_async())
check("async wrappers work", True)


# ════════════════════════════════════════════════════
# 清理
# ════════════════════════════════════════════════════
asyncio.run(dispose_db())
shutil.rmtree(TEMP_DATA, ignore_errors=True)

print(f"\n{'=' * 60}")
print(f"test_repositories 结果: {passed} passed, {failed} failed")
print(f"{'=' * 60}")
sys.exit(0 if failed == 0 else 1)
