"""secret_key_manager KDF 升级与兼容迁移测试（审计 B2-6）。

旧版 SHA256(指纹) 无盐直派生：MachineGuid/machine-id 世界可读，数据目录外带即可
离线还原密钥并解密全部 API Key。新版为 PBKDF2-HMAC-SHA256（随机盐 + 高迭代）。
本文件验证：新格式读写回归、旧版密文自动迁移（用户无感知）、指纹变更 fail-closed。
"""

import pytest
from cryptography.fernet import Fernet

from app.security.crypto import secret_key_manager as skm


@pytest.fixture()
def data_dir(tmp_path):
    return str(tmp_path)


def test_roundtrip_and_persistence(data_dir):
    """新格式：首次生成后跨加载保持稳定，盐文件随之落盘。"""
    key1 = skm.load_or_create_secret_key(data_dir)
    key2 = skm.load_or_create_secret_key(data_dir)

    assert key1 == key2
    assert skm.get_secret_key_path(data_dir).exists()
    assert skm._kdf_salt_path(data_dir, skm.SECRET_KEY_FILE_NAME).exists()


def test_legacy_sha256_ciphertext_auto_migrates(data_dir):
    """旧版 SHA256 直派生密文：首次加载自动迁移为 PBKDF2 格式，值不变。"""
    secret = Fernet.generate_key().decode()
    key_path = skm.get_secret_key_path(data_dir)
    key_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_fernet = Fernet(skm._derive_machine_key(skm._get_machine_fingerprint()))
    key_path.write_bytes(legacy_fernet.encrypt(secret.encode()))

    # 加载：应解出原值并完成迁移
    assert skm.load_or_create_secret_key(data_dir) == secret

    # 落盘内容已可被新 KDF 解开，且再次加载保持稳定
    raw = key_path.read_bytes()
    salt = skm._load_or_create_kdf_salt(data_dir, skm.SECRET_KEY_FILE_NAME)
    migrated = Fernet(skm._derive_kdf_key(skm._get_machine_fingerprint(), salt)).decrypt(raw)
    assert migrated.decode() == secret
    assert skm.load_or_create_secret_key(data_dir) == secret


def test_fingerprint_change_fails_closed(data_dir, monkeypatch):
    """指纹变更（换机/外带）：fail-closed 抛 RuntimeError，而非静默返回错误密钥。"""
    skm.load_or_create_secret_key(data_dir)
    monkeypatch.setattr(skm, "_get_machine_fingerprint", lambda: "other-machine")

    with pytest.raises(RuntimeError):
        skm.load_or_create_secret_key(data_dir)
