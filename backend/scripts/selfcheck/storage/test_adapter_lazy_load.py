"""Phase 7 测试: adapter P0 懒加载 + model.py import-time 解耦。

核心验证（P0 修复）：
1. import adapter.py / model.py 不触达 DB（模块加载与 DB init 彻底解耦）
2. ensure_providers_loaded() 懒加载正确工作（threading.Lock + _loaded 双重检查）
3. 方法级懒加载兜底（get_provider / list_providers 等自动触发）
4. 线程安全（多线程只加载一次）
5. 幂等性（重复调用不重载）
6. model_config DB round-trip（_save/_load/apply 全链路）
7. apply_model_config_from_db() 覆盖 provider is_default（调用顺序正确）
"""
import os
import sys
import tempfile
import asyncio
import threading
import inspect
import shutil

# ── 设置临时 DATA_DIR（模拟全新安装，DB 文件不存在）──
TEMP_DATA = tempfile.mkdtemp(prefix="luominest_test_lazy_")
os.environ["DATA_DIR"] = TEMP_DATA
os.environ["SECRET_KEY"] = "test-key-not-for-production-use"
sys.path.insert(0, r"D:/Projects/My_Projects/LuomiNest/backend")

print(f"[Test] TEMP_DATA_DIR = {TEMP_DATA}")

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
# 1. Import-time safety (P0) — import 不触达 DB
# ════════════════════════════════════════════════════
print("\n=== 1. Import-time safety (P0) ===")
from app.runtime.provider.llm.adapter import llm_adapter, LLMAdapter

check("ensure_providers_loaded method exists", hasattr(llm_adapter, "ensure_providers_loaded"))
check("_loaded flag is False at import (P0)", llm_adapter._loaded is False)
check("providers is empty at import (P0)", len(llm_adapter.providers) == 0,
      f"count={len(llm_adapter.providers)}")
check("_lock exists (threading.Lock)", hasattr(llm_adapter, "_lock"))
check("default_provider set from settings", llm_adapter.default_provider is not None)
print(f"  _loaded = {llm_adapter._loaded}, providers = {len(llm_adapter.providers)}, default = {llm_adapter.default_provider}")


# ════════════════════════════════════════════════════
# 2. model.py import safety — 不调用 _apply_model_config
# ════════════════════════════════════════════════════
print("\n=== 2. model.py import safety ===")
from app.api.v1.endpoints.model import apply_model_config_from_db
from app.core.config import settings

check("apply_model_config_from_db is exported function",
      inspect.isfunction(apply_model_config_from_db))
# settings.LLM_DEFAULT_MODEL 在 import 时应保持默认（未被 model_config 覆盖）
check("LLM_DEFAULT_MODEL unchanged at import",
      settings.LLM_DEFAULT_MODEL == "", f"got={settings.LLM_DEFAULT_MODEL!r}")
print(f"  LLM_DEFAULT_MODEL = {settings.LLM_DEFAULT_MODEL!r}")


# ════════════════════════════════════════════════════
# 3. init_db() 建表
# ════════════════════════════════════════════════════
print("\n=== 3. init_db() ===")
from app.infrastructure.database import init_db, dispose_db
asyncio.run(init_db())
check("DB file created", os.path.exists(os.path.join(TEMP_DATA, "luominest.db")))


# ════════════════════════════════════════════════════
# 4. ensure_providers_loaded() — 懒加载
# ════════════════════════════════════════════════════
print("\n=== 4. ensure_providers_loaded() ===")
llm_adapter.ensure_providers_loaded()
check("_loaded is True after ensure", llm_adapter._loaded is True)
check("providers loaded from fallback chain", len(llm_adapter.providers) > 0,
      f"count={len(llm_adapter.providers)}")
print(f"  _loaded = {llm_adapter._loaded}")
print(f"  providers = {list(llm_adapter.providers.keys())}")
print(f"  default_provider = {llm_adapter.default_provider}")


# ════════════════════════════════════════════════════
# 5. apply_model_config_from_db() — 空库安全返回
# ════════════════════════════════════════════════════
print("\n=== 5. apply_model_config_from_db() (空库) ===")
apply_model_config_from_db()
check("apply handles empty DB gracefully", True)


# ════════════════════════════════════════════════════
# 6. 方法级懒加载兜底 — list_providers
# ════════════════════════════════════════════════════
print("\n=== 6. 方法级懒加载兜底 (list_providers) ===")
llm_adapter._loaded = False
llm_adapter.providers = {}
llm_adapter._provider_configs = {}
result = llm_adapter.list_providers()
check("list_providers triggers lazy load", llm_adapter._loaded is True)
check("list_providers returns providers", len(result) > 0, f"count={len(result)}")
check("list_providers returns api_key_prefix field",
      all("api_key_prefix" in p for p in result),
      f"fields={[list(p.keys()) for p in result]}")
check("list_providers returns api_key_set field",
      all("api_key_set" in p for p in result),
      f"fields={[list(p.keys()) for p in result]}")
print(f"  list_providers() returned {len(result)} providers")


# ════════════════════════════════════════════════════
# 7. 方法级懒加载兜底 — get_provider
# ════════════════════════════════════════════════════
print("\n=== 7. 方法级懒加载兜底 (get_provider) ===")
llm_adapter._loaded = False
llm_adapter.providers = {}
llm_adapter._provider_configs = {}
llm_adapter.default_provider = settings.LLM_DEFAULT_PROVIDER
try:
    p = llm_adapter.get_provider()
    check("get_provider triggers lazy load", llm_adapter._loaded is True)
    check("get_provider returns provider", p is not None)
    print(f"  get_provider() returned: {getattr(p, 'provider_name', 'unknown')}")
except Exception as e:
    check("get_provider triggered lazy load before raising", llm_adapter._loaded is True)
    print(f"  get_provider raised (acceptable): {type(e).__name__}: {e}")


# ════════════════════════════════════════════════════
# 8. 线程安全 — 多线程同时调用 ensure_providers_loaded
# ════════════════════════════════════════════════════
print("\n=== 8. 线程安全 ===")
llm_adapter._loaded = False
llm_adapter.providers = {}
llm_adapter._provider_configs = {}
call_count = 0
count_lock = threading.Lock()
original_init = llm_adapter._init_providers


def counting_init():
    global call_count
    with count_lock:
        call_count += 1
    original_init()


llm_adapter._init_providers = counting_init

threads = [threading.Thread(target=llm_adapter.ensure_providers_loaded) for _ in range(8)]
for t in threads:
    t.start()
for t in threads:
    t.join()

check("_init_providers called exactly once (8 threads)", call_count == 1,
      f"called {call_count} times")
check("_loaded is True after concurrent calls", llm_adapter._loaded is True)
print(f"  _init_providers called {call_count} times (8 threads, expected: 1)")


# ════════════════════════════════════════════════════
# 9. 幂等性 — 重复调用
# ════════════════════════════════════════════════════
print("\n=== 9. 幂等性 ===")
count_before = call_count
llm_adapter.ensure_providers_loaded()
llm_adapter.ensure_providers_loaded()
llm_adapter.ensure_providers_loaded()
count_after = call_count
check("repeated ensure does not re-load", count_after == count_before,
      f"before={count_before}, after={count_after}")


# ════════════════════════════════════════════════════
# 10. model_config DB round-trip
# ════════════════════════════════════════════════════
print("\n=== 10. model_config DB round-trip ===")
from app.api.v1.endpoints.model import _save_model_config, _load_model_config

test_config = {
    "default_provider": "test_provider",
    "default_model": "test-model",
    "default_temperature": 0.5,
    "default_max_tokens": 2048,
    "default_top_p": 0.85,
}
_save_model_config(test_config)
loaded = _load_model_config()
check("model_config saved to DB",
      loaded.get("default_provider") == "test_provider")
check("model_config round-trip preserves all fields",
      loaded.get("default_model") == "test-model" and
      loaded.get("default_temperature") == 0.5 and
      loaded.get("default_max_tokens") == 2048 and
      loaded.get("default_top_p") == 0.85,
      f"loaded={loaded}")
print(f"  loaded config: {loaded}")


# ════════════════════════════════════════════════════
# 11. apply_model_config_from_db() 应用配置到运行时
# ════════════════════════════════════════════════════
print("\n=== 11. apply_model_config_from_db() 应用配置 ===")
apply_model_config_from_db()
check("apply sets llm_adapter.default_provider",
      llm_adapter.default_provider == "test_provider",
      f"got={llm_adapter.default_provider}")
check("apply sets settings.LLM_DEFAULT_MODEL",
      settings.LLM_DEFAULT_MODEL == "test-model",
      f"got={settings.LLM_DEFAULT_MODEL}")
check("apply sets settings.LLM_DEFAULT_TEMPERATURE",
      settings.LLM_DEFAULT_TEMPERATURE == 0.5,
      f"got={settings.LLM_DEFAULT_TEMPERATURE}")
check("apply sets settings.LLM_DEFAULT_MAX_TOKENS",
      settings.LLM_DEFAULT_MAX_TOKENS == 2048,
      f"got={settings.LLM_DEFAULT_MAX_TOKENS}")
check("apply sets settings.LLM_DEFAULT_TOP_P",
      settings.LLM_DEFAULT_TOP_P == 0.85,
      f"got={settings.LLM_DEFAULT_TOP_P}")
print(f"  llm_adapter.default_provider = {llm_adapter.default_provider}")
print(f"  settings.LLM_DEFAULT_MODEL = {settings.LLM_DEFAULT_MODEL}")


# ════════════════════════════════════════════════════
# 12. 调用顺序：ensure_providers_loaded 在 apply 之前
# ════════════════════════════════════════════════════
print("\n=== 12. lifespan 调用顺序模拟 ===")
# 模拟 app_factory.py lifespan 的调用顺序：
# 1. init_db (已执行)
# 2. migrate_all_json_to_sqlite (空库，跳过)
# 3. llm_adapter.ensure_providers_loaded() — 加载 providers
# 4. apply_model_config_from_db() — 覆盖 default_provider

# 重置状态
llm_adapter._loaded = False
llm_adapter.providers = {}
llm_adapter._provider_configs = {}
llm_adapter.default_provider = settings.LLM_DEFAULT_PROVIDER  # 回到默认

# Step 3: ensure_providers_loaded
llm_adapter.ensure_providers_loaded()
check("lifespan step 3: providers loaded", llm_adapter._loaded is True)
default_after_ensure = llm_adapter.default_provider
print(f"  default after ensure = {default_after_ensure}")

# Step 4: apply_model_config_from_db (会覆盖 default_provider)
apply_model_config_from_db()
check("lifespan step 4: model_config overrides default_provider",
      llm_adapter.default_provider == "test_provider",
      f"got={llm_adapter.default_provider}")
print(f"  default after apply = {llm_adapter.default_provider}")


# ════════════════════════════════════════════════════
# 清理
# ════════════════════════════════════════════════════
print("\n=== 13. Cleanup ===")
asyncio.run(dispose_db())
shutil.rmtree(TEMP_DATA, ignore_errors=True)
check("disposed engines + cleaned temp dir", not os.path.exists(TEMP_DATA))


# ════════════════════════════════════════════════════
# 结果汇总
# ════════════════════════════════════════════════════
print(f"\n{'=' * 60}")
print(f"test_adapter_lazy_load 结果: {passed} passed, {failed} failed")
print(f"{'=' * 60}")
sys.exit(0 if failed == 0 else 1)
