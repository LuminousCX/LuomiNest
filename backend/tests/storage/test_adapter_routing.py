"""Phase 3 测试: RouteHint 路由决策 + apply_reasoner_config + api_key_prefix + 凭证查重。

核心验证：
1. route_hint=CHAT 走主模型
2. route_hint=REASONER 走推理模型（配置后）
3. route_hint=REASONER 未配置推理模型时回退主模型
4. route_hint=AGENT 走主模型
5. 显式 provider_name 优先于 route_hint
6. apply_reasoner_config 正确应用到内存
7. get_reasoner_provider 返回配置元组
8. list_providers 返回 api_key_prefix
9. 凭证查重（相同 api_key 不重复创建）
"""
import os
import sys
import tempfile
import asyncio
import shutil

# ── 设置临时 DATA_DIR（模拟全新安装，DB 文件不存在）──
TEMP_DATA = tempfile.mkdtemp(prefix="luominest_test_routing_")
os.environ["DATA_DIR"] = TEMP_DATA
os.environ["SECRET_KEY"] = "test-key-not-for-production-use"
sys.path.insert(0, r"d:\Projects\Project\LuomiNest\backend")

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
# FakeProvider — 记录调用参数，不实际调用 LLM API
# ════════════════════════════════════════════════════
from app.runtime.provider.base import LLMProvider
from app.runtime.provider.llm.types import LLMRequest, LLMResponse, StreamEvent
from app.runtime.provider.llm.adapter import llm_adapter
from app.runtime.provider.llm.types import RouteHint


class FakeProvider(LLMProvider):
    def __init__(self, name: str = "fake", default_model: str = "fake-model"):
        self.provider_name = name
        self.default_model = default_model
        self.api_key = "fake-key"
        self.base_url = f"http://{name}.local/v1"
        self.last_request: LLMRequest | None = None
        self.chat_call_count = 0
        self.stream_call_count = 0

    async def chat(self, request: LLMRequest) -> LLMResponse:
        self.last_request = request
        self.chat_call_count += 1
        return LLMResponse(content=f"[{self.provider_name}]", reasoning="", tool_calls=None)

    async def chat_stream(self, request: LLMRequest):
        self.last_request = request
        self.stream_call_count += 1
        yield StreamEvent("content", {"content": f"[{self.provider_name}]"})
        yield StreamEvent("done")

    async def embed(self, text: str) -> list[float]:
        return [0.0]

    async def list_models(self) -> list[dict]:
        return [{"id": self.default_model, "name": self.default_model}]


def _reset_adapter():
    """重置 llm_adapter 到干净状态（保留 _lock）。"""
    llm_adapter.providers.clear()
    llm_adapter._provider_configs.clear()
    llm_adapter.default_provider = "main"
    llm_adapter._loaded = True  # 跳过懒加载，直接用注入的 FakeProvider
    llm_adapter._reasoner_provider = ""
    llm_adapter._reasoner_model = ""
    llm_adapter._reasoner_temperature = None
    llm_adapter._reasoner_max_tokens = None
    llm_adapter._reasoner_effort = ""


# ════════════════════════════════════════════════════
# 1. init_db — 凭证/列表测试需要
# ════════════════════════════════════════════════════
print("\n=== 1. init_db ===")
from app.infrastructure.database import init_db, dispose_db
asyncio.run(init_db())
check("DB file created", os.path.exists(os.path.join(TEMP_DATA, "luominest.db")))


# ════════════════════════════════════════════════════
# 2. apply_reasoner_config + get_reasoner_provider
# ════════════════════════════════════════════════════
print("\n=== 2. apply_reasoner_config / get_reasoner_provider ===")
_reset_adapter()

check("get_reasoner_provider returns None when unconfigured",
      llm_adapter.get_reasoner_provider() is None)

llm_adapter.apply_reasoner_config({
    "reasoner_provider": "deepseek",
    "reasoner_model": "deepseek-reasoner",
    "reasoner_temperature": 0.2,
    "reasoner_max_tokens": 8192,
    "reasoner_effort": "high",
})
result = llm_adapter.get_reasoner_provider()
check("get_reasoner_provider returns tuple after apply",
      result is not None and result[0] == "deepseek",
      f"got={result}")
check("reasoner_model applied",
      result[1] == "deepseek-reasoner", f"got={result[1]}")
check("reasoner_temperature applied",
      result[2] == 0.2, f"got={result[2]}")
check("reasoner_max_tokens applied",
      result[3] == 8192, f"got={result[3]}")
check("reasoner_effort applied",
      result[4] == "high", f"got={result[4]}")

# apply_reasoner_config 处理空值
llm_adapter.apply_reasoner_config({})
check("apply_reasoner_config with empty dict resets to None",
      llm_adapter.get_reasoner_provider() is None)


# ════════════════════════════════════════════════════
# 3. route_hint=CHAT 走主模型
# ════════════════════════════════════════════════════
print("\n=== 3. route_hint=CHAT → main provider ===")
_reset_adapter()
main_provider = FakeProvider("main", "gpt-4o-mini")
reasoner_provider = FakeProvider("deepseek", "deepseek-reasoner")
llm_adapter.providers["main"] = main_provider
llm_adapter.providers["deepseek"] = reasoner_provider
llm_adapter.default_provider = "main"
llm_adapter.apply_reasoner_config({
    "reasoner_provider": "deepseek",
    "reasoner_model": "deepseek-reasoner",
    "reasoner_temperature": 0.2,
    "reasoner_max_tokens": 8192,
    "reasoner_effort": "high",
})

response = asyncio.run(llm_adapter.chat(
    messages=[{"role": "user", "content": "hi"}],
    route_hint=RouteHint.CHAT,
))
check("CHAT uses main provider",
      main_provider.chat_call_count == 1 and reasoner_provider.chat_call_count == 0,
      f"main={main_provider.chat_call_count}, reasoner={reasoner_provider.chat_call_count}")
check("CHAT response is main provider content",
      response == "[main]", f"got={response!r}")
check("CHAT request model is main default",
      main_provider.last_request.model == "gpt-4o-mini",
      f"got={main_provider.last_request.model}")


# ════════════════════════════════════════════════════
# 4. route_hint=REASONER 走推理模型（配置后）
# ════════════════════════════════════════════════════
print("\n=== 4. route_hint=REASONER → reasoner provider ===")
_reset_adapter()
main_provider = FakeProvider("main", "gpt-4o-mini")
reasoner_provider = FakeProvider("deepseek", "deepseek-reasoner")
llm_adapter.providers["main"] = main_provider
llm_adapter.providers["deepseek"] = reasoner_provider
llm_adapter.default_provider = "main"
llm_adapter.apply_reasoner_config({
    "reasoner_provider": "deepseek",
    "reasoner_model": "deepseek-reasoner",
    "reasoner_temperature": 0.2,
    "reasoner_max_tokens": 8192,
    "reasoner_effort": "high",
})

response = asyncio.run(llm_adapter.chat(
    messages=[{"role": "user", "content": "complex reasoning task"}],
    route_hint=RouteHint.REASONER,
))
check("REASONER uses reasoner provider",
      reasoner_provider.chat_call_count == 1 and main_provider.chat_call_count == 0,
      f"main={main_provider.chat_call_count}, reasoner={reasoner_provider.chat_call_count}")
check("REASONER response is reasoner provider content",
      response == "[deepseek]", f"got={response!r}")
check("REASONER request model is reasoner_model",
      reasoner_provider.last_request.model == "deepseek-reasoner",
      f"got={reasoner_provider.last_request.model}")
check("REASONER request temperature is reasoner_temperature",
      reasoner_provider.last_request.temperature == 0.2,
      f"got={reasoner_provider.last_request.temperature}")
check("REASONER request max_tokens is reasoner_max_tokens",
      reasoner_provider.last_request.max_tokens == 8192,
      f"got={reasoner_provider.last_request.max_tokens}")
check("REASONER request reasoning_effort injected",
      reasoner_provider.last_request.extra.get("reasoning_effort") == "high",
      f"got={reasoner_provider.last_request.extra}")


# ════════════════════════════════════════════════════
# 5. route_hint=REASONER 未配置推理模型时回退主模型
# ════════════════════════════════════════════════════
print("\n=== 5. route_hint=REASONER (unconfigured) → fallback to main ===")
_reset_adapter()
main_provider = FakeProvider("main", "gpt-4o-mini")
reasoner_provider = FakeProvider("deepseek", "deepseek-reasoner")
llm_adapter.providers["main"] = main_provider
llm_adapter.providers["deepseek"] = reasoner_provider
llm_adapter.default_provider = "main"
# 不配置 reasoner_*

response = asyncio.run(llm_adapter.chat(
    messages=[{"role": "user", "content": "hi"}],
    route_hint=RouteHint.REASONER,
))
check("REASONER unconfigured falls back to main",
      main_provider.chat_call_count == 1 and reasoner_provider.chat_call_count == 0,
      f"main={main_provider.chat_call_count}, reasoner={reasoner_provider.chat_call_count}")
check("REASONER unconfigured response is main content",
      response == "[main]", f"got={response!r}")


# ════════════════════════════════════════════════════
# 6. route_hint=AGENT 走主模型
# ════════════════════════════════════════════════════
print("\n=== 6. route_hint=AGENT → main provider ===")
_reset_adapter()
main_provider = FakeProvider("main", "gpt-4o-mini")
reasoner_provider = FakeProvider("deepseek", "deepseek-reasoner")
llm_adapter.providers["main"] = main_provider
llm_adapter.providers["deepseek"] = reasoner_provider
llm_adapter.default_provider = "main"
llm_adapter.apply_reasoner_config({
    "reasoner_provider": "deepseek",
    "reasoner_model": "deepseek-reasoner",
    "reasoner_temperature": 0.2,
    "reasoner_max_tokens": 8192,
    "reasoner_effort": "high",
})

response = asyncio.run(llm_adapter.chat(
    messages=[{"role": "user", "content": "agent task"}],
    route_hint=RouteHint.AGENT,
))
check("AGENT uses main provider (not reasoner)",
      main_provider.chat_call_count == 1 and reasoner_provider.chat_call_count == 0,
      f"main={main_provider.chat_call_count}, reasoner={reasoner_provider.chat_call_count}")
check("AGENT response is main content",
      response == "[main]", f"got={response!r}")


# ════════════════════════════════════════════════════
# 7. 显式 provider_name 优先于 route_hint
# ════════════════════════════════════════════════════
print("\n=== 7. explicit provider_name overrides route_hint ===")
_reset_adapter()
main_provider = FakeProvider("main", "gpt-4o-mini")
reasoner_provider = FakeProvider("deepseek", "deepseek-reasoner")
custom_provider = FakeProvider("custom", "custom-model")
llm_adapter.providers["main"] = main_provider
llm_adapter.providers["deepseek"] = reasoner_provider
llm_adapter.providers["custom"] = custom_provider
llm_adapter.default_provider = "main"
llm_adapter.apply_reasoner_config({
    "reasoner_provider": "deepseek",
    "reasoner_model": "deepseek-reasoner",
    "reasoner_temperature": 0.2,
    "reasoner_max_tokens": 8192,
    "reasoner_effort": "high",
})

# 显式指定 custom，即使 route_hint=REASONER 也应走 custom
response = asyncio.run(llm_adapter.chat(
    messages=[{"role": "user", "content": "hi"}],
    provider_name="custom",
    route_hint=RouteHint.REASONER,
))
check("explicit provider_name overrides REASONER hint",
      custom_provider.chat_call_count == 1 and reasoner_provider.chat_call_count == 0,
      f"custom={custom_provider.chat_call_count}, reasoner={reasoner_provider.chat_call_count}")
check("explicit provider response is custom content",
      response == "[custom]", f"got={response!r}")


# ════════════════════════════════════════════════════
# 8. chat_stream 路由决策
# ════════════════════════════════════════════════════
print("\n=== 8. chat_stream routing ===")
_reset_adapter()
main_provider = FakeProvider("main", "gpt-4o-mini")
reasoner_provider = FakeProvider("deepseek", "deepseek-reasoner")
llm_adapter.providers["main"] = main_provider
llm_adapter.providers["deepseek"] = reasoner_provider
llm_adapter.default_provider = "main"
llm_adapter.apply_reasoner_config({
    "reasoner_provider": "deepseek",
    "reasoner_model": "deepseek-reasoner",
    "reasoner_temperature": 0.2,
    "reasoner_max_tokens": 8192,
})


async def _collect_stream(stream):
    chunks = []
    async for chunk in stream:
        chunks.append(chunk)
    return chunks


# CHAT stream → main
chunks = asyncio.run(_collect_stream(llm_adapter.chat_stream(
    messages=[{"role": "user", "content": "hi"}],
    route_hint=RouteHint.CHAT,
)))
check("stream CHAT uses main provider",
      main_provider.stream_call_count == 1 and reasoner_provider.stream_call_count == 0,
      f"main={main_provider.stream_call_count}, reasoner={reasoner_provider.stream_call_count}")

# REASONER stream → reasoner
chunks = asyncio.run(_collect_stream(llm_adapter.chat_stream(
    messages=[{"role": "user", "content": "complex"}],
    route_hint=RouteHint.REASONER,
)))
check("stream REASONER uses reasoner provider",
      reasoner_provider.stream_call_count == 1,
      f"reasoner={reasoner_provider.stream_call_count}")
check("stream REASONER model is reasoner_model",
      reasoner_provider.last_request.model == "deepseek-reasoner",
      f"got={reasoner_provider.last_request.model}")


# ════════════════════════════════════════════════════
# 9. list_providers 返回 api_key_prefix
# ════════════════════════════════════════════════════
print("\n=== 9. list_providers returns api_key_prefix ===")
# 重置 adapter，使用真实 repo 流程注册 provider
llm_adapter._loaded = False
llm_adapter.providers.clear()
llm_adapter._provider_configs.clear()
llm_adapter._provider_repo = None
llm_adapter._credential_repo = None
llm_adapter.default_provider = "openai"

from app.runtime.provider.llm.adapter import _create_provider_from_config

test_api_key = "sk-test-routing-key-1234567890abcdef"
config = {
    "id": "test_prefix_provider",
    "name": "Test Prefix Provider",
    "vendor": "openai_compatible",
    "base_url": "https://api.test.com/v1",
    "api_key": test_api_key,
    "default_model": "test-model",
    "is_default": True,
    "selected_models": ["test-model"],
}
provider = _create_provider_from_config(config)
llm_adapter.register_provider(
    name="test_prefix_provider",
    provider=provider,
    config=config,
    set_default=True,
)

providers_list = llm_adapter.list_providers()
target = next((p for p in providers_list if p["id"] == "test_prefix_provider"), None)
check("list_providers contains registered provider",
      target is not None, f"providers={[p['id'] for p in providers_list]}")
check("list_providers returns api_key_prefix",
      target is not None and bool(target.get("api_key_prefix")),
      f"prefix={target.get('api_key_prefix') if target else 'N/A'}")
check("list_providers api_key_prefix is non-empty string",
      target is not None and isinstance(target.get("api_key_prefix"), str) and len(target["api_key_prefix"]) > 0,
      f"prefix={target.get('api_key_prefix') if target else 'N/A'}")
check("list_providers api_key_set matches prefix bool",
      target is not None and target.get("api_key_set") == bool(target.get("api_key_prefix")),
      f"set={target.get('api_key_set')}, prefix={target.get('api_key_prefix')}")


# ════════════════════════════════════════════════════
# 10. 凭证查重（相同 api_key 不重复创建）
# ════════════════════════════════════════════════════
print("\n=== 10. credential dedup ===")
from app.infrastructure.database.repositories import ProviderCredentialRepository
cred_repo = ProviderCredentialRepository()

# 先保存一次
cred1 = cred_repo.save_credential("test_prefix_provider", test_api_key, label="first")
# 用相同 api_key 再保存（关联到不同 provider）
cred2 = cred_repo.save_credential("another_provider", test_api_key, label="second")

check("dedup: same api_key returns same credential id",
      cred1["id"] == cred2["id"],
      f"cred1={cred1['id']}, cred2={cred2['id']}")
check("dedup: only one credential for same key",
      len(cred_repo.list_credentials("test_prefix_provider")) + len(cred_repo.list_credentials("another_provider")) <= 1,
      f"test_prefix={len(cred_repo.list_credentials('test_prefix_provider'))}, another={len(cred_repo.list_credentials('another_provider'))}")

# 不同 api_key 创建独立凭证
different_key = "sk-different-key-9876543210fedcba"
cred3 = cred_repo.save_credential("test_prefix_provider", different_key, label="different")
check("different api_key creates new credential",
      cred3["id"] != cred1["id"],
      f"cred1={cred1['id']}, cred3={cred3['id']}")
check("different api_key credential has different prefix",
      cred3["api_key_prefix"] != cred1["api_key_prefix"],
      f"cred1_prefix={cred1['api_key_prefix']}, cred3_prefix={cred3['api_key_prefix']}")

# find_by_api_key 查重
found = cred_repo.find_by_api_key(test_api_key)
check("find_by_api_key locates existing credential",
      found is not None, f"found={found}")
check("find_by_api_key returns correct hash",
      found is not None and found["api_key_hash"] == cred_repo._compute_hash(test_api_key),
      f"found_hash={found['api_key_hash'] if found else 'N/A'}")

# 清理查重测试数据
# 注意：dedup 会把同 hash 凭证 reassign 到 another_provider，需先删 another_provider，
# 再为 test_prefix_provider 重新保存凭证，保证后续 remove_provider 测试有凭证可删
cred_repo.delete_by_provider("another_provider")
cred_repo.delete_credential(cred3["id"])
cred_repo.save_credential("test_prefix_provider", test_api_key, label="restored")


# ════════════════════════════════════════════════════
# 11. remove_provider 清理凭证
# ════════════════════════════════════════════════════
print("\n=== 11. remove_provider cleans credentials ===")
# 确认注册时凭证已创建
creds_before = cred_repo.list_credentials("test_prefix_provider")
check("credentials exist before remove_provider",
      len(creds_before) >= 1, f"count={len(creds_before)}")

llm_adapter.remove_provider("test_prefix_provider")
creds_after = cred_repo.list_credentials("test_prefix_provider")
check("remove_provider deletes associated credentials",
      len(creds_after) == 0, f"count={len(creds_after)}")
check("remove_provider removes from memory",
      "test_prefix_provider" not in llm_adapter.providers,
      f"providers={list(llm_adapter.providers.keys())}")


# ════════════════════════════════════════════════════
# 12. aclose 清理 providers
# ════════════════════════════════════════════════════
print("\n=== 12. aclose ===")
_reset_adapter()
fake = FakeProvider("main", "model")
llm_adapter.providers["main"] = fake
asyncio.run(llm_adapter.aclose())
check("aclose clears providers dict",
      len(llm_adapter.providers) == 0, f"count={len(llm_adapter.providers)}")
check("aclose clears _provider_configs",
      len(llm_adapter._provider_configs) == 0, f"count={len(llm_adapter._provider_configs)}")
check("aclose resets _loaded flag",
      llm_adapter._loaded is False)


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
print(f"test_adapter_routing 结果: {passed} passed, {failed} failed")
print(f"{'=' * 60}")
sys.exit(0 if failed == 0 else 1)
