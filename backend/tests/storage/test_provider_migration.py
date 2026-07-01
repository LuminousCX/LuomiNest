"""Phase 2 迁移集成测试: Alembic upgrade（schema 变更 + 数据迁移 + 幂等性）。

测试流程：
1. 用 alembic upgrade cb814021f0d2 创建旧 schema（providers 有 api_key 列）
2. 用 ConfigRepository 写入 llm.providers.* 数据（模拟旧数据，api_key 自动加密）
3. 用 alembic upgrade head 应用新迁移
4. 验证：providers 表有数据（无 api_key）、provider_credentials 表有凭证、config_items 已清理
5. 幂等性：再跑一次 upgrade head 无变化
6. downgrade 回退 schema
"""
import os
import sys
import tempfile
import asyncio
import shutil

TEMP_DATA = tempfile.mkdtemp(prefix="luominest_test_almig_")
os.environ["DATA_DIR"] = TEMP_DATA
os.environ["SECRET_KEY"] = "test-key-not-for-production-use"
sys.path.insert(0, r"d:\Projects\Project\LuomiNest\backend")

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


from alembic.config import Config
from alembic import command

ALEMBIC_INI = r"d:\Projects\Project\LuomiNest\backend\scripts\migrate\alembic.ini"


def make_alembic_cfg():
    cfg = Config(ALEMBIC_INI)
    return cfg


# ════════════════════════════════════════════════════
# 1. 创建旧 schema（initial_schema）
# ════════════════════════════════════════════════════
print("\n=== 1. 创建旧 schema（cb814021f0d2）===")
cfg = make_alembic_cfg()
command.upgrade(cfg, "cb814021f0d2")
check("initial schema created", os.path.exists(os.path.join(TEMP_DATA, "luominest.db")))

# 验证旧 schema 有 api_key 列（无 enabled/sort_order）
from sqlalchemy import create_engine, inspect, text
db_path = os.path.join(TEMP_DATA, "luominest.db")
old_engine = create_engine(f"sqlite:///{db_path}")
old_inspector = inspect(old_engine)
old_cols = [c["name"] for c in old_inspector.get_columns("providers")]
check("old providers has api_key column", "api_key" in old_cols, f"cols={old_cols}")
check("old providers lacks enabled", "enabled" not in old_cols)
check("old providers lacks sort_order", "sort_order" not in old_cols)
check("old schema lacks provider_credentials table",
      "provider_credentials" not in old_inspector.get_table_names())
old_engine.dispose()


# ════════════════════════════════════════════════════
# 2. 写入旧格式数据（config_items llm.providers.*）
# ════════════════════════════════════════════════════
print("\n=== 2. 写入旧格式 config_items 数据 ===")
from app.infrastructure.database.repositories import ConfigRepository
config_repo = ConfigRepository()

# Provider 1: OpenAI（有 api_key）
config_repo.set("llm.providers.openai.name", "OpenAI")
config_repo.set("llm.providers.openai.vendor", "openai_compatible")
config_repo.set("llm.providers.openai.base_url", "https://api.openai.com/v1")
config_repo.set("llm.providers.openai.api_key", "sk-migration-test-key-12345")
config_repo.set("llm.providers.openai.default_model", "gpt-4o-mini")
config_repo.set("llm.providers.openai.is_default", True)
config_repo.set("llm.providers.openai.selected_models", ["gpt-4o", "gpt-4o-mini"])

# Provider 2: Ollama（api_key="ollama" 占位符）
config_repo.set("llm.providers.ollama.name", "Ollama")
config_repo.set("llm.providers.ollama.vendor", "ollama")
config_repo.set("llm.providers.ollama.base_url", "http://localhost:11434/v1")
config_repo.set("llm.providers.ollama.api_key", "ollama")
config_repo.set("llm.providers.ollama.default_model", "qwen3-vl:8b")
config_repo.set("llm.providers.ollama.is_default", False)
config_repo.set("llm.providers.ollama.selected_models", ["qwen3-vl:8b"])

# 验证数据写入
ns = config_repo.get_namespace("llm.providers.")
check("config_items has 14 provider keys", len(ns) == 14, f"count={len(ns)}")
check("api_key encrypted in config_items",
      config_repo.get("llm.providers.openai.api_key") == "sk-migration-test-key-12345")


# ════════════════════════════════════════════════════
# 3. 应用新迁移（upgrade head）
# ════════════════════════════════════════════════════
print("\n=== 3. 应用新迁移（upgrade head）===")
cfg = make_alembic_cfg()
command.upgrade(cfg, "head")

# 验证新 schema
new_engine = create_engine(f"sqlite:///{db_path}")
new_inspector = inspect(new_engine)
new_cols = [c["name"] for c in new_inspector.get_columns("providers")]
check("new providers lacks api_key", "api_key" not in new_cols, f"cols={new_cols}")
check("new providers has enabled", "enabled" in new_cols)
check("new providers has sort_order", "sort_order" in new_cols)
check("provider_credentials table created",
      "provider_credentials" in new_inspector.get_table_names())

cred_cols = [c["name"] for c in new_inspector.get_columns("provider_credentials")]
check("provider_credentials has api_key_encrypted", "api_key_encrypted" in cred_cols)
check("provider_credentials has api_key_prefix", "api_key_prefix" in cred_cols)
check("provider_credentials has api_key_hash", "api_key_hash" in cred_cols)
new_engine.dispose()


# ════════════════════════════════════════════════════
# 4. 验证数据迁移结果
# ════════════════════════════════════════════════════
print("\n=== 4. 验证数据迁移结果 ===")
from app.infrastructure.database.repositories import ProviderRepository, ProviderCredentialRepository
provider_repo = ProviderRepository()
cred_repo = ProviderCredentialRepository()

# providers 表
providers = provider_repo.get_all_ordered()
check("migrated 2 providers", len(providers) == 2, f"count={len(providers)}")
check("providers sorted (openai first)", providers[0]["id"] == "openai",
      f"order={[p['id'] for p in providers]}")

openai = provider_repo.get("openai")
check("openai name migrated", openai["name"] == "OpenAI")
check("openai base_url migrated", openai["base_url"] == "https://api.openai.com/v1")
check("openai default_model migrated", openai["default_model"] == "gpt-4o-mini")
check("openai is_default migrated", openai["is_default"] is True)
check("openai selected_models migrated", openai["selected_models"] == ["gpt-4o", "gpt-4o-mini"])
check("openai has no api_key", "api_key" not in openai)
check("openai has enabled=True", openai["enabled"] is True)
check("openai has sort_order=0", openai["sort_order"] == 0)

ollama = provider_repo.get("ollama")
check("ollama name migrated", ollama["name"] == "Ollama")
check("ollama has no api_key", "api_key" not in ollama)

# provider_credentials 表
openai_creds = cred_repo.list_credentials("openai")
check("openai has 1 credential", len(openai_creds) == 1, f"count={len(openai_creds)}")
check("openai credential prefix correct",
      openai_creds[0]["api_key_prefix"] == "sk-mig...2345",
      f"got={openai_creds[0]['api_key_prefix']}")

ollama_creds = cred_repo.list_credentials("ollama")
check("ollama has 1 credential", len(ollama_creds) == 1, f"count={len(ollama_creds)}")

# 解密验证
active_cred = cred_repo.get_active_credential("openai")
check("decrypted api_key matches original",
      active_cred["api_key"] == "sk-migration-test-key-12345",
      f"got={active_cred['api_key']!r}")

# config_items 已清理
remaining_ns = config_repo.get_namespace("llm.providers.")
check("config_items llm.providers.* cleaned up",
      len(remaining_ns) == 0,
      f"remaining={list(remaining_ns.keys())}")

# _migration_meta 标记
from app.infrastructure.database.models.migration_meta import MigrationMeta
from app.infrastructure.database.session import sync_session_factory
with sync_session_factory() as session:
    meta = session.get(MigrationMeta, "providers_config")
    check("_migration_meta marked", meta is not None)
    check("_migration_meta record_count=2", meta.record_count == 2, f"count={meta.record_count}")


# ════════════════════════════════════════════════════
# 5. 幂等性 — 再跑一次 upgrade head
# ════════════════════════════════════════════════════
print("\n=== 5. 幂等性 ===")
cfg = make_alembic_cfg()
command.upgrade(cfg, "head")

# 数据不变
check("providers unchanged after re-upgrade", len(provider_repo.get_all_ordered()) == 2)
check("openai credential unchanged",
      len(cred_repo.list_credentials("openai")) == 1)


# ════════════════════════════════════════════════════
# 6. downgrade 回退 schema
# ════════════════════════════════════════════════════
print("\n=== 6. downgrade 回退 ===")
cfg = make_alembic_cfg()
command.downgrade(cfg, "cb814021f0d2")

down_engine = create_engine(f"sqlite:///{db_path}")
down_inspector = inspect(down_engine)
down_cols = [c["name"] for c in down_inspector.get_columns("providers")]
check("downgraded providers has api_key back", "api_key" in down_cols)
check("downgraded providers lacks enabled", "enabled" not in down_cols)
check("downgraded providers lacks sort_order", "sort_order" not in down_cols)
check("provider_credentials table dropped",
      "provider_credentials" not in down_inspector.get_table_names())
down_engine.dispose()


# ════════════════════════════════════════════════════
# 清理
# ════════════════════════════════════════════════════
from app.infrastructure.database import dispose_db
asyncio.run(dispose_db())
shutil.rmtree(TEMP_DATA, ignore_errors=True)

print(f"\n{'=' * 60}")
print(f"test_provider_migration 结果: {passed} passed, {failed} failed")
print(f"{'=' * 60}")
sys.exit(0 if failed == 0 else 1)
