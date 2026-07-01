"""Phase 2 测试: ProviderRepository + ProviderCredentialRepository。

覆盖：
- ProviderRepository: CRUD + get_all_ordered（sort_order 排序）+ get_default + enabled/sort_order 字段
- ProviderCredentialRepository: save_credential + 加密/解密 round-trip + prefix 生成 +
  hash 查重（同 key upsert 不重复）+ get_active_credential + list_credentials（不返回明文）+
  find_by_hash/find_by_api_key + update_last_used + delete_credential + delete_by_provider +
  多凭证支持 + async wrappers
"""
import os
import sys
import tempfile
import asyncio
import shutil

TEMP_DATA = tempfile.mkdtemp(prefix="luominest_test_prov_")
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


# ════════════════════════════════════════════════════
# 1. ProviderRepository — CRUD + 排序 + 默认
# ════════════════════════════════════════════════════
print("\n=== 1. ProviderRepository ===")
from app.infrastructure.database.repositories import ProviderRepository

provider_repo = ProviderRepository()

# save（不含 api_key）
p1 = provider_repo.save("openai", {
    "name": "OpenAI",
    "vendor": "openai_compatible",
    "base_url": "https://api.openai.com/v1",
    "default_model": "gpt-4o-mini",
    "is_default": True,
    "selected_models": ["gpt-4o", "gpt-4o-mini"],
    "enabled": True,
    "sort_order": 0,
})
check("save creates provider", p1 is not None and p1["name"] == "OpenAI")
check("save sets id", p1.get("id") == "openai")
check("save has no api_key field", "api_key" not in p1, f"keys={list(p1.keys())}")
check("save has enabled field", p1.get("enabled") is True)
check("save has sort_order field", p1.get("sort_order") == 0)
check("save selected_models persisted", p1["selected_models"] == ["gpt-4o", "gpt-4o-mini"])

# get
retrieved = provider_repo.get("openai")
check("get returns provider", retrieved is not None and retrieved["name"] == "OpenAI")
check("get has no api_key field", "api_key" not in retrieved)

# 第二个 provider（非默认，sort_order=1）
p2 = provider_repo.save("ollama", {
    "name": "Ollama",
    "vendor": "ollama",
    "base_url": "http://localhost:11434/v1",
    "default_model": "qwen3-vl:8b",
    "is_default": False,
    "selected_models": ["qwen3-vl:8b"],
    "enabled": True,
    "sort_order": 1,
})
check("save second provider", p2 is not None and p2["name"] == "Ollama")

# 第三个 provider（禁用，sort_order=2）
p3 = provider_repo.save("anthropic", {
    "name": "Anthropic",
    "vendor": "openai_compatible",
    "base_url": "https://api.anthropic.com/v1",
    "default_model": "claude-3-5-sonnet",
    "is_default": False,
    "selected_models": [],
    "enabled": False,
    "sort_order": 2,
})

# get_all_ordered — 按 sort_order 排序
ordered = provider_repo.get_all_ordered()
check("get_all_ordered returns 3", len(ordered) == 3, f"count={len(ordered)}")
check("get_all_ordered sorts by sort_order",
      [p["id"] for p in ordered] == ["openai", "ollama", "anthropic"],
      f"order={[p['id'] for p in ordered]}")

# get_default
default = provider_repo.get_default()
check("get_default returns is_default=True", default is not None and default["id"] == "openai")

# update（部分更新）
updated = provider_repo.update("ollama", {"default_model": "llama3:8b"})
check("update partial field", updated["default_model"] == "llama3:8b")
check("update preserves other fields", updated["name"] == "Ollama")

# delete
check("delete provider", provider_repo.delete("anthropic") is True)
check("get deleted returns None", provider_repo.get("anthropic") is None)
check("get_all_ordered after delete", len(provider_repo.get_all_ordered()) == 2)


# ════════════════════════════════════════════════════
# 2. ProviderCredentialRepository — 加密 + prefix + hash
# ════════════════════════════════════════════════════
print("\n=== 2. ProviderCredentialRepository ===")
from app.infrastructure.database.repositories import ProviderCredentialRepository

cred_repo = ProviderCredentialRepository()

# ── save_credential + get_active_credential（加密 round-trip）──
LONG_KEY = "sk-test-1234567890abcdef"
cred = cred_repo.save_credential("openai", LONG_KEY, label="production")
check("save_credential returns dict", cred is not None)
check("save_credential sets provider_id", cred["provider_id"] == "openai")
check("save_credential sets label", cred["label"] == "production")
check("save_credential sets is_active", cred["is_active"] is True)
check("save_credential includes plaintext api_key", cred.get("api_key") == LONG_KEY)
check("save_credential has encrypted field", "api_key_encrypted" in cred)
check("save_credential encrypted != plaintext", cred["api_key_encrypted"] != LONG_KEY)

# prefix 生成：前6+...+后4
check("prefix correct for long key",
      cred["api_key_prefix"] == "sk-tes...cdef",
      f"got={cred['api_key_prefix']}")

# hash 生成：SHA-256
import hashlib
expected_hash = hashlib.sha256(LONG_KEY.encode()).hexdigest()
check("hash correct (sha256)", cred["api_key_hash"] == expected_hash)

# get_active_credential — 返回解密后的 api_key
active = cred_repo.get_active_credential("openai")
check("get_active_credential returns dict", active is not None)
check("get_active_credential decrypts api_key",
      active["api_key"] == LONG_KEY,
      f"got={active.get('api_key')!r}")
check("get_active_credential has prefix", active["api_key_prefix"] == "sk-tes...cdef")

# ── 短 key prefix ──
SHORT_KEY = "sk-ab"
short_cred = cred_repo.save_credential("ollama", SHORT_KEY)
check("prefix for short key uses first 4",
      short_cred["api_key_prefix"] == "sk-a...",
      f"got={short_cred['api_key_prefix']}")

# ── hash 查重：同 key 不重复创建 ──
DUPLICATE_KEY = "sk-duplicate-key-456"
first_save = cred_repo.save_credential("openai", DUPLICATE_KEY)
first_id = first_save["id"]
second_save = cred_repo.save_credential("ollama", DUPLICATE_KEY)
check("duplicate key upserts (same id)", second_save["id"] == first_id,
      f"first={first_id}, second={second_save['id']}")
check("duplicate key updates provider_id", second_save["provider_id"] == "ollama")

# 只有一条记录
all_creds_for_hash = cred_repo.find_by_hash(hashlib.sha256(DUPLICATE_KEY.encode()).hexdigest())
check("find_by_hash returns the credential", all_creds_for_hash is not None)
check("find_by_hash returns correct id", all_creds_for_hash["id"] == first_id)

# find_by_api_key（便捷方法）
found = cred_repo.find_by_api_key(LONG_KEY)
check("find_by_api_key finds credential", found is not None)
check("find_by_api_key correct id", found["id"] == cred["id"])
check("find_by_api_key missing returns None", cred_repo.find_by_api_key("sk-nonexistent") is None)

# ── list_credentials — 不返回密文/明文 ──
# 为 openai 再加一个 key
SECOND_KEY = "sk-another-key-789xyz"
cred_repo.save_credential("openai", SECOND_KEY, label="backup")

creds_list = cred_repo.list_credentials("openai")
check("list_credentials returns multiple", len(creds_list) >= 2, f"count={len(creds_list)}")
check("list_credentials excludes api_key_encrypted",
      all("api_key_encrypted" not in c for c in creds_list))
check("list_credentials excludes api_key plaintext",
      all("api_key" not in c for c in creds_list))
check("list_credentials includes prefix",
      all("api_key_prefix" in c for c in creds_list))

# ── update_last_used ──
cred_repo.update_last_used(cred["id"])
updated_cred = cred_repo.get_active_credential("openai")
# 注意：get_active_credential 返回 created_at 最早的活跃凭证
check("update_last_used sets timestamp", updated_cred["last_used_at"] != "",
      f"got={updated_cred.get('last_used_at')!r}")

# ── delete_credential ──
# 先加一个临时凭证再删
TEMP_KEY = "sk-temp-delete-me-001"
temp_cred = cred_repo.save_credential("ollama", TEMP_KEY)
temp_id = temp_cred["id"]
check("delete_credential returns True", cred_repo.delete_credential(temp_id) is True)
check("deleted credential not found", cred_repo.find_by_hash(
    hashlib.sha256(TEMP_KEY.encode()).hexdigest()) is None)

# ── delete_by_provider ──
# 为 anthropic 加几个凭证（先重新创建 anthropic provider）
provider_repo.save("anthropic", {
    "name": "Anthropic",
    "vendor": "openai_compatible",
    "base_url": "https://api.anthropic.com/v1",
    "default_model": "claude-3-5-sonnet",
    "is_default": False,
    "selected_models": [],
    "enabled": True,
    "sort_order": 2,
})
cred_repo.save_credential("anthropic", "sk-ant-key-aaa-111")
cred_repo.save_credential("anthropic", "sk-ant-key-bbb-222")
deleted_count = cred_repo.delete_by_provider("anthropic")
check("delete_by_provider removes all", deleted_count == 2, f"count={deleted_count}")
check("no credentials left for anthropic", len(cred_repo.list_credentials("anthropic")) == 0)


# ════════════════════════════════════════════════════
# 3. async wrappers
# ════════════════════════════════════════════════════
print("\n=== 3. Async wrappers ===")

async def test_async():
    # ProviderRepository async
    provider_repo.save("async-prov", {
        "name": "异步Provider",
        "vendor": "openai_compatible",
        "base_url": "https://api.async.com/v1",
        "default_model": "gpt-4o",
        "is_default": False,
        "selected_models": [],
        "enabled": True,
        "sort_order": 99,
    })
    result = await provider_repo.get_async("async-prov")
    assert result is not None and result["name"] == "异步Provider"

    ordered = await provider_repo.get_all_ordered_async()
    assert any(p["id"] == "async-prov" for p in ordered)

    await provider_repo.delete_async("async-prov")
    assert await provider_repo.get_async("async-prov") is None

    # ProviderCredentialRepository async
    cred = await cred_repo.save_credential_async("openai", "sk-async-test-key-999")
    assert cred["api_key"] == "sk-async-test-key-999"

    active = await cred_repo.get_active_credential_async("openai")
    assert active is not None

    found = await cred_repo.find_by_api_key_async("sk-async-test-key-999")
    assert found is not None

    listed = await cred_repo.list_credentials_async("openai")
    assert len(listed) >= 1

    await cred_repo.delete_credential_async(cred["id"])
    assert await cred_repo.find_by_api_key_async("sk-async-test-key-999") is None

asyncio.run(test_async())
check("async wrappers work", True)


# ════════════════════════════════════════════════════
# 清理
# ════════════════════════════════════════════════════
asyncio.run(dispose_db())
shutil.rmtree(TEMP_DATA, ignore_errors=True)

print(f"\n{'=' * 60}")
print(f"test_provider_repository 结果: {passed} passed, {failed} failed")
print(f"{'=' * 60}")
sys.exit(0 if failed == 0 else 1)
