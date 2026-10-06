"""platform_instances.config 凭据字段级加密验收（链路审查 P1-6）。

覆盖：
- 写入路径：凭据字段落库为 enc:v1: 前缀密文（直接查 DB 断言无明文），
  普通配置（ws_host/port/enable 等）保持明文
- 读取路径：repo.get/get_all 返回明文，与写入值一致（适配器契约不变）
- 存量明文迁移：migrate_plaintext_credentials 幂等重写（二次调用零写入）
- 解密失败保留密文（SECRET_KEY 变化场景不清空销毁凭据）
- /instances 脱敏：mask_config 掩码凭据、strip_masked_values 哨兵不覆盖
- 元数据一致性：各适配器 config_metadata 的 password 键全部登记在册
"""

import pytest
from sqlalchemy import delete as sa_delete

from app.infrastructure.database.models.platform_instance import PlatformInstance
from app.infrastructure.database.repositories.platform_repository import PlatformRepository
from app.infrastructure.database.session import sync_session_factory
from app.security.crypto.platform_config_crypto import (
    CONFIG_ENC_PREFIX,
    CONFIG_VALUE_MASK,
    SENSITIVE_CONFIG_KEYS,
    decrypt_config,
    encrypt_config,
    is_encrypted_config_value,
    mask_config,
    strip_masked_values,
)


@pytest.fixture
def repo(_init_test_db):
    r = PlatformRepository()
    yield r
    with sync_session_factory() as session:
        session.execute(sa_delete(PlatformInstance))
        session.commit()


def _plaintext_config() -> dict:
    return {
        "ws_host": "0.0.0.0",
        "ws_port": 8080,
        "access_token": "secret-access-token",
        "enable": True,
        "model_config": {"system_prompt": "你是小鹭"},
    }


def _raw_insert(instance_id: str, config: dict, adapter_type: str = "qq_onebot") -> None:
    """绕过仓储直接插行（模拟存量明文数据/检查落库形态）。"""
    with sync_session_factory() as session:
        session.add(PlatformInstance(
            id=instance_id,
            adapter_type=adapter_type,
            name="raw-row",
            config=config,
            enable=True,
            status=None,
            message_count=0,
            last_sync=None,
            error_message="",
            icon="Globe",
            category="general",
            display_name="",
            created_at="",
            updated_at="",
        ))
        session.commit()


def _raw_get_config(instance_id: str) -> dict | None:
    """绕过仓储直读 DB（拿落库原始形态）。"""
    with sync_session_factory() as session:
        obj = session.get(PlatformInstance, instance_id)
        return obj.config if obj else None


# ─── 写入加密：DB 层面无明文 ───


def test_save_encrypts_sensitive_fields_in_db(repo):
    config = _plaintext_config()
    repo.save("enc-save-1", {
        "id": "enc-save-1",
        "adapter_type": "qq_onebot",
        "name": "实例",
        "config": config,
    })

    stored = _raw_get_config("enc-save-1")
    # 凭据字段：带前缀的密文，且不含明文
    assert stored["access_token"].startswith(CONFIG_ENC_PREFIX)
    assert "secret-access-token" not in stored["access_token"]
    # 普通配置保持明文
    assert stored["ws_host"] == "0.0.0.0"
    assert stored["ws_port"] == 8080
    assert stored["enable"] is True
    # 嵌套结构原样保留
    assert stored["model_config"] == {"system_prompt": "你是小鹭"}


def test_update_encrypts_sensitive_fields_in_db(repo):
    repo.save("enc-upd-1", {
        "id": "enc-upd-1",
        "adapter_type": "qq_onebot",
        "name": "实例",
        "config": {"ws_host": "0.0.0.0"},
    })
    repo.update("enc-upd-1", {"config": {**_plaintext_config(), "ws_port": 9999}})

    stored = _raw_get_config("enc-upd-1")
    assert is_encrypted_config_value(stored["access_token"])
    assert stored["ws_port"] == 9999


# ─── 读取解密：读出明文一致（roundtrip）───


def test_get_returns_plaintext_roundtrip(repo):
    config = _plaintext_config()
    repo.save("enc-rt-1", {
        "id": "enc-rt-1",
        "adapter_type": "qq_onebot",
        "name": "实例",
        "config": config,
    })

    row = repo.get("enc-rt-1")
    assert row["config"] == config

    repo.update("enc-rt-1", {"config": {**config, "ws_port": 1234}})
    row = repo.get("enc-rt-1")
    assert row["config"] == {**config, "ws_port": 1234}


def test_get_all_returns_plaintext(repo):
    config = _plaintext_config()
    repo.save("enc-all-1", {
        "id": "enc-all-1",
        "adapter_type": "qq_onebot",
        "name": "实例",
        "config": config,
    })

    rows = [r for r in repo.get_all() if r["id"] == "enc-all-1"]
    assert rows and rows[0]["config"] == config


def test_encrypt_config_idempotent_and_input_untouched():
    config = {"token": "abc", "ws_host": "h"}
    original = dict(config)

    once = encrypt_config(config)
    twice = encrypt_config(once)

    assert twice == once  # 幂等：不二次加密
    assert config == original  # 入参不被原地修改


# ─── 存量明文惰性迁移 ───


def test_migrate_encrypts_legacy_plaintext_rows(repo):
    legacy = {"access_token": "legacy-plain-token", "ws_host": "1.2.3.4"}
    _raw_insert("enc-mig-1", legacy)

    migrated = repo.migrate_plaintext_credentials()
    assert migrated >= 1

    stored = _raw_get_config("enc-mig-1")
    assert stored["access_token"].startswith(CONFIG_ENC_PREFIX)
    assert "legacy-plain-token" not in stored["access_token"]
    assert stored["ws_host"] == "1.2.3.4"  # 普通配置不动

    # 迁移后读出明文一致
    assert repo.get("enc-mig-1")["config"] == legacy

    # 幂等：二次调用不重写本行（密文逐字节不变 = 未重新加密）
    before = _raw_get_config("enc-mig-1")["access_token"]
    assert repo.migrate_plaintext_credentials() == 0
    assert _raw_get_config("enc-mig-1")["access_token"] == before


def test_migrate_skips_rows_without_credentials(repo):
    _raw_insert("enc-mig-2", {"ws_host": "1.2.3.4", "enable": True})
    _raw_insert("enc-mig-3", {"access_token": "has-credential"})

    before = _raw_get_config("enc-mig-2")
    repo.migrate_plaintext_credentials()
    assert _raw_get_config("enc-mig-2") == before  # 无凭据行零写入
    assert is_encrypted_config_value(_raw_get_config("enc-mig-3")["access_token"])


# ─── 解密失败保留密文（fail-safe，不清空销毁凭据）───


def test_decrypt_failure_preserves_ciphertext(repo):
    garbage = CONFIG_ENC_PREFIX + "not-a-valid-fernet-token"
    _raw_insert("enc-bad-1", {"access_token": garbage})

    row = repo.get("enc-bad-1")
    assert row["config"]["access_token"] == garbage  # 原样保留，而非空串

    # 迁移路径同样不破坏（已带前缀的值跳过）
    repo.migrate_plaintext_credentials()
    assert _raw_get_config("enc-bad-1")["access_token"] == garbage


# ─── /instances 响应脱敏与 PATCH 哨兵保护 ───


def test_mask_config_masks_only_sensitive_fields():
    masked = mask_config(_plaintext_config())
    assert masked["access_token"] == CONFIG_VALUE_MASK
    assert masked["ws_host"] == "0.0.0.0"
    assert masked["ws_port"] == 8080
    assert masked["model_config"] == {"system_prompt": "你是小鹭"}
    # 空字符串凭据保持空（无内容可泄漏）
    assert mask_config({"token": ""})["token"] == ""


def test_strip_masked_values_drops_only_masked_sensitive_keys():
    incoming = {
        "access_token": CONFIG_VALUE_MASK,  # 未修改的凭据 → 剔除
        "ws_host": "9.9.9.9",               # 修改过的普通配置 → 保留
        "ws_port": 1234,
        "bot_token": "new-token",           # 用户主动改凭据 → 保留
        "bot_name": CONFIG_VALUE_MASK,      # 非凭据键的巧合值 → 保留
    }
    stripped = strip_masked_values(incoming)
    assert "access_token" not in stripped
    assert stripped == {
        "ws_host": "9.9.9.9",
        "ws_port": 1234,
        "bot_token": "new-token",
        "bot_name": CONFIG_VALUE_MASK,
    }


def test_instance_to_response_masks_credentials():
    """_instance_to_response 不外泄明文凭据（GET/POST/PATCH 响应共用此转换）。"""
    from app.runtime.platform import registry
    from app.runtime.platform.base import BasePlatformAdapter, PlatformResponse
    from app.api.v1.endpoints.platform import _instance_to_response

    class _NoopAdapter(BasePlatformAdapter):
        platform_name = "fake_crypto"

        async def send_message(self, response: PlatformResponse, target: str) -> bool:
            return True

    saved_types = dict(registry._adapter_types)
    saved_instances = dict(registry._instances)
    try:
        registry.register_adapter_type(
            "fake_crypto", "Fake Crypto", "encryption test adapter", _NoopAdapter,
        )
        inst = registry.create_instance(
            instance_id="enc-mask-1",
            adapter_type="fake_crypto",
            name="脱敏实例",
            config={"bot_token": "real-bot-token", "ws_host": "1.2.3.4"},
        )
        resp = _instance_to_response(inst)
        assert resp.config["bot_token"] == CONFIG_VALUE_MASK
        assert "real-bot-token" not in str(resp.config)
        assert resp.config["ws_host"] == "1.2.3.4"
    finally:
        registry._adapter_types.clear()
        registry._adapter_types.update(saved_types)
        registry._instances.clear()
        registry._instances.update(saved_instances)


# ─── 加密字段集合与适配器元数据一致性 ───


def test_sensitive_keys_cover_adapter_metadata():
    """全部适配器 config_metadata 中 type=password 的键必须在 SENSITIVE_CONFIG_KEYS 内。

    新增适配器/新增 password 字段漏登记时在此失败，防止新凭据回到明文落库。
    """
    import app.runtime.platform.adapters  # noqa: F401 — 触发全部适配器注册
    from app.runtime.platform.registry import list_adapter_types

    declared = {
        key
        for at in list_adapter_types()
        for key, meta in (at.config_metadata or {}).items()
        if isinstance(meta, dict) and meta.get("type") == "password"
    }
    missing = declared - set(SENSITIVE_CONFIG_KEYS)
    assert not missing, f"password 凭据键未登记加密集合: {sorted(missing)}"


def test_decrypt_config_roundtrip_direct():
    """encrypt/decrypt 直接 roundtrip（不经 DB）。"""
    config = {"bot_token": "tk-123", "rcon_password": "pw-456", "ws_port": 8081}
    assert decrypt_config(encrypt_config(config)) == config
