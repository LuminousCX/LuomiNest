"""Phase 7 测试: Facade 兼容层 — 单例存在 + 方法签名兼容 + CRUD round-trip。

验证：
- 7 个 Facade 单例存在且方法签名与原 store 一致
- luominest_config_store 方法签名兼容
- main_agent_config 统一接口
- 薄 shim 文件正确 re-export（import 路径不变）
- CRUD round-trip 通过 Facade 单例
"""
import os
import sys
import tempfile
import asyncio
import shutil
import inspect

TEMP_DATA = tempfile.mkdtemp(prefix="luominest_test_facade_")
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
# 1. 7 个 Facade 单例存在
# ════════════════════════════════════════════════════
print("\n=== 1. Facade 单例存在 ===")
from app.infrastructure.database.facades.json_store_facade import (
    agents_store, groups_store, platforms_store, repo_sources_store,
)
from app.infrastructure.database.facades.marketplace_stats_store import marketplace_stats_store
from app.infrastructure.database.usage_store import usage_store
from app.infrastructure.database.conversation_store import conversation_store
from app.infrastructure.database.config_store import luominest_config_store

check("agents_store exists", agents_store is not None)
check("groups_store exists", groups_store is not None)
check("platforms_store exists", platforms_store is not None)
check("repo_sources_store exists", repo_sources_store is not None)
check("marketplace_stats_store exists", marketplace_stats_store is not None)
check("usage_store exists", usage_store is not None)
check("conversation_store exists", conversation_store is not None)
check("luominest_config_store exists", luominest_config_store is not None)


# ════════════════════════════════════════════════════
# 2. JsonStore Facade 方法签名兼容
# ════════════════════════════════════════════════════
print("\n=== 2. JsonStore Facade 方法签名 ===")

JSON_STORE_METHODS = ["set", "get", "delete", "list_all", "clear"]
for store_name, store in [
    ("agents_store", agents_store),
    ("groups_store", groups_store),
    ("platforms_store", platforms_store),
    ("repo_sources_store", repo_sources_store),
]:
    for method in JSON_STORE_METHODS:
        check(f"{store_name}.{method}() exists",
              hasattr(store, method) and callable(getattr(store, method)),
              f"missing={method}")

# marketplace_stats_store (Facade 暴露 list_all/all/values，不暴露 get_all/delete_all)
for method in ["set", "get", "list_all", "delete", "clear", "all", "values", "count"]:
    check(f"marketplace_stats_store.{method}() exists",
          hasattr(marketplace_stats_store, method) and callable(getattr(marketplace_stats_store, method)),
          f"missing={method}")

# usage_store (Facade 暴露 clear，不暴露 clear_all)
for method in ["record", "get_records", "get_summary", "trim", "clear"]:
    check(f"usage_store.{method}() exists",
          hasattr(usage_store, method) and callable(getattr(usage_store, method)),
          f"missing={method}")

# conversation_store (Facade 暴露 list_conversations/search_conversations，不暴露 list_meta/search)
for method in ["set", "get", "delete", "list_conversations", "search_conversations",
               "soft_delete", "restore", "rename", "list_trash", "permanent_delete"]:
    check(f"conversation_store.{method}() exists",
          hasattr(conversation_store, method) and callable(getattr(conversation_store, method)),
          f"missing={method}")

# luominest_config_store
for method in ["get", "set", "delete", "delete_namespace", "get_namespace", "list_all", "clear", "invalidate"]:
    check(f"luominest_config_store.{method}() exists",
          hasattr(luominest_config_store, method) and callable(getattr(luominest_config_store, method)),
          f"missing={method}")


# ════════════════════════════════════════════════════
# 3. async wrapper 方法存在
# ════════════════════════════════════════════════════
print("\n=== 3. async wrapper 方法 ===")
for store_name, store, methods in [
    ("agents_store", agents_store, ["set_async", "get_async", "delete_async", "list_all_async", "clear_async"]),
    ("marketplace_stats_store", marketplace_stats_store, ["set_async", "get_async", "delete_async", "clear_async", "list_all_async"]),
    ("usage_store", usage_store, ["record_async", "get_records_async", "clear_async", "trim_async"]),
    ("conversation_store", conversation_store, ["set_async", "get_async", "search_conversations_async", "soft_delete_async", "list_conversations_async"]),
    ("luominest_config_store", luominest_config_store, ["get_async", "set_async", "delete_async", "get_namespace_async"]),
]:
    for method in methods:
        check(f"{store_name}.{method}() exists",
              hasattr(store, method) and callable(getattr(store, method)),
              f"missing={method}")


# ════════════════════════════════════════════════════
# 4. CRUD round-trip 通过 Facade 单例
# ════════════════════════════════════════════════════
print("\n=== 4. CRUD round-trip ===")

# agents_store
agents_store.set("facade-agent", {"name": "Facade测试", "is_main": False})
check("agents_store round-trip",
      agents_store.get("facade-agent") is not None and
      agents_store.get("facade-agent")["name"] == "Facade测试")
check("agents_store.list_all", len(agents_store.list_all()) == 1)
agents_store.delete("facade-agent")
check("agents_store.delete", agents_store.get("facade-agent") is None)

# groups_store
groups_store.set("facade-group", {"name": "Facade群组", "member_ids": ["x"]})
check("groups_store round-trip", groups_store.get("facade-group")["name"] == "Facade群组")
groups_store.delete("facade-group")

# platforms_store
platforms_store.set("facade-plat", {"name": "Facade平台", "adapter_type": "test"})
check("platforms_store round-trip", platforms_store.get("facade-plat")["adapter_type"] == "test")
platforms_store.delete("facade-plat")

# repo_sources_store
repo_sources_store.set("facade-repo", {"name": "Facade仓库", "url": "test"})
check("repo_sources_store round-trip", repo_sources_store.get("facade-repo")["name"] == "Facade仓库")
repo_sources_store.delete("facade-repo")

# marketplace_stats_store
marketplace_stats_store.set("facade-stat", {"item_id": "facade-stat", "type": "plugin", "download_count": 5})
check("marketplace_stats_store round-trip",
      marketplace_stats_store.get("facade-stat")["download_count"] == 5)
marketplace_stats_store.clear()

# usage_store
usage_store.record(provider="facade", model="test", total_tokens=42)
check("usage_store round-trip", len(usage_store.get_records()) == 1)
usage_store.clear()

# conversation_store
conversation_store.set("facade-conv", {
    "title": "Facade对话", "agent_id": "a1", "messages": [{"role": "user", "content": "test"}]
})
check("conversation_store round-trip", conversation_store.get("facade-conv")["title"] == "Facade对话")
conversation_store.delete("facade-conv")

# luominest_config_store
luominest_config_store.set("facade.key", "value")
check("luominest_config_store round-trip", luominest_config_store.get("facade.key") == "value")
luominest_config_store.delete("facade.key")
check("luominest_config_store delete", luominest_config_store.get("facade.key") is None)


# ════════════════════════════════════════════════════
# 5. main_agent_config 统一接口
# ════════════════════════════════════════════════════
print("\n=== 5. main_agent_config 统一接口 ===")
from app.infrastructure.database.facades.main_agent_config import (
    load_luominest_main_agent_config, save_luominest_main_agent_config,
)

test_config = {
    "provider": "openai",
    "model": "gpt-4o",
    "system_prompt": "统一接口测试",
    "temperature": 0.8,
    "max_tokens": 4096,
}
save_luominest_main_agent_config(test_config)
loaded = load_luominest_main_agent_config()
check("main_agent_config save/load provider", loaded.get("provider") == "openai")
check("main_agent_config save/load model", loaded.get("model") == "gpt-4o")
check("main_agent_config save/load system_prompt", loaded.get("system_prompt") == "统一接口测试")
check("main_agent_config save/load temperature", loaded.get("temperature") == 0.8)
check("main_agent_config save/load max_tokens", loaded.get("max_tokens") == 4096)

# update partial
update_config = dict(loaded)
update_config["model"] = "claude-3"
save_luominest_main_agent_config(update_config)
check("main_agent_config update", load_luominest_main_agent_config().get("model") == "claude-3")


# ════════════════════════════════════════════════════
# 6. 薄 shim re-export 路径正确
# ════════════════════════════════════════════════════
print("\n=== 6. 薄 shim re-export ===")

# 旧 import 路径应仍可用（消费者零改动）
from app.infrastructure.database.json_store import JsonStore
check("JsonStore class re-exported from json_store", JsonStore is not None)

from app.infrastructure.database.config_store import luominest_config_store as shim_config_store
check("luominest_config_store re-exported from config_store shim",
      shim_config_store is luominest_config_store)

from app.infrastructure.database.usage_store import usage_store as shim_usage_store
check("usage_store re-exported from usage_store shim",
      shim_usage_store is usage_store)

from app.infrastructure.database.conversation_store import conversation_store as shim_conv_store
check("conversation_store re-exported from conversation_store shim",
      shim_conv_store is conversation_store)

from app.runtime.platform.main_agent_config import (
    load_luominest_main_agent_config as shim_load_main_agent,
)
check("main_agent_config re-exported from runtime/platform shim",
      callable(shim_load_main_agent))


# ════════════════════════════════════════════════════
# 7. async CRUD via Facade
# ════════════════════════════════════════════════════
print("\n=== 7. async CRUD via Facade ===")

async def test_async_crud():
    await agents_store.set_async("async-agent", {"name": "异步Agent", "is_main": False})
    result = await agents_store.get_async("async-agent")
    assert result is not None and result["name"] == "异步Agent"

    await luominest_config_store.set_async("async.key", {"nested": [1, 2]})
    val = await luominest_config_store.get_async("async.key")
    assert val == {"nested": [1, 2]}

    await usage_store.record_async(provider="async", model="test", total_tokens=99)
    recs = await usage_store.get_records_async()
    assert len(recs) == 1 and recs[0]["provider"] == "async"

    await conversation_store.set_async("async-conv", {"title": "异步对话", "messages": []})
    conv = await conversation_store.get_async("async-conv")
    assert conv is not None and conv["title"] == "异步对话"

asyncio.run(test_async_crud())
check("async CRUD round-trip via Facade", True)


# ════════════════════════════════════════════════════
# 清理
# ════════════════════════════════════════════════════
asyncio.run(dispose_db())
shutil.rmtree(TEMP_DATA, ignore_errors=True)

print(f"\n{'=' * 60}")
print(f"test_facade_compat 结果: {passed} passed, {failed} failed")
print(f"{'=' * 60}")
sys.exit(0 if failed == 0 else 1)
