"""secret_key_manager KDF 升级与兼容迁移测试（审计 B2-6 / 链路 E P0-3）。

旧版 SHA256(指纹) 无盐直派生：MachineGuid/machine-id 世界可读，数据目录外带即可
离线还原密钥并解密全部 API Key。新版为 PBKDF2-HMAC-SHA256（随机盐 + 高迭代）。
本文件验证：新格式读写回归、旧版密文自动迁移（用户无感知）、指纹变更 fail-closed、
口令恢复包（换机/容器重建后恢复密钥的唯一合法途径）与失败指引。
"""

import json

import pytest
from cryptography.fernet import Fernet

from app.security.crypto import secret_key_manager as skm


PASSPHRASE = "correct-horse-battery"


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


# ── 恢复包（链路 E P0-3：换机/容器重建后的密钥恢复）──────────────────────────


def test_recovery_roundtrip_same_machine(data_dir):
    """原机：创建恢复包 → 恢复，密钥值不变，正常加解密不受影响。"""
    key = skm.load_or_create_secret_key(data_dir)

    package_path = skm.create_recovery_package(data_dir, PASSPHRASE)
    assert skm.has_recovery_package(data_dir)
    assert package_path.exists()

    assert skm.recover_secret_key(data_dir, PASSPHRASE) == key
    assert skm.load_or_create_secret_key(data_dir) == key


def test_recovery_roundtrip_jwt_file(data_dir):
    """JWT 密钥文件走同一套恢复机制（file_name 参数化）。"""
    key = skm.load_or_create_secret_key(data_dir, skm.JWT_SECRET_KEY_FILE_NAME)
    skm.create_recovery_package(data_dir, PASSPHRASE, skm.JWT_SECRET_KEY_FILE_NAME)

    assert skm.recover_secret_key(data_dir, PASSPHRASE, skm.JWT_SECRET_KEY_FILE_NAME) == key
    assert skm.load_or_create_secret_key(data_dir, skm.JWT_SECRET_KEY_FILE_NAME) == key


def test_cross_fingerprint_with_package_recovers_original_key(data_dir, monkeypatch):
    """换机场景：原机建包 → 新指纹下先 fail-closed → 凭口令恢复出原密钥。"""
    key = skm.load_or_create_secret_key(data_dir)
    skm.create_recovery_package(data_dir, PASSPHRASE)
    monkeypatch.setattr(skm, "_get_machine_fingerprint", lambda: "new-machine")

    # 恢复前：fail-closed
    with pytest.raises(RuntimeError):
        skm.load_or_create_secret_key(data_dir)

    # 凭恢复包 + 口令恢复，得到原密钥且此后正常加载
    assert skm.recover_secret_key(data_dir, PASSPHRASE) == key
    assert skm.load_or_create_secret_key(data_dir) == key


def test_cross_fingerprint_without_package_error_has_guidance(data_dir, monkeypatch):
    """换机且无恢复包：明确报错 + 可操作指引（恢复途径与放弃旧数据的删除步骤）。"""
    key_path = skm.get_secret_key_path(data_dir)
    skm.load_or_create_secret_key(data_dir)
    monkeypatch.setattr(skm, "_get_machine_fingerprint", lambda: "new-machine")

    with pytest.raises(RuntimeError) as exc_info:
        skm.load_or_create_secret_key(data_dir)
    message = str(exc_info.value)

    assert "SECRET_KEY" in message          # 诊断名
    assert str(key_path) in message          # 指明问题文件
    assert "恢复包" in message               # 指引：回原机创建恢复包的途径
    assert "删除" in message                 # 指引：放弃旧数据的操作步骤
    assert "SECRET_KEY/JWT_SECRET_KEY" in message  # 指引：容器显式 env 替代方案


def test_cross_fingerprint_with_package_error_points_to_recover(data_dir, monkeypatch):
    """换机且已有恢复包：报错直接给出 recover 命令指引。"""
    skm.load_or_create_secret_key(data_dir)
    skm.create_recovery_package(data_dir, PASSPHRASE)
    monkeypatch.setattr(skm, "_get_machine_fingerprint", lambda: "new-machine")

    with pytest.raises(RuntimeError) as exc_info:
        skm.load_or_create_secret_key(data_dir)
    message = str(exc_info.value)

    assert "recover" in message
    assert skm.get_recovery_package_path(data_dir).name in message


def test_recover_wrong_passphrase_fails_closed(data_dir, monkeypatch):
    """口令错误：fail-closed 报错，密钥文件不被破坏，正确口令仍可恢复。"""
    key = skm.load_or_create_secret_key(data_dir)
    raw_before = skm.get_secret_key_path(data_dir).read_bytes()
    skm.create_recovery_package(data_dir, PASSPHRASE)
    monkeypatch.setattr(skm, "_get_machine_fingerprint", lambda: "new-machine")

    with pytest.raises(RuntimeError, match="口令错误"):
        skm.recover_secret_key(data_dir, "wrong-passphrase-999")

    assert skm.get_secret_key_path(data_dir).read_bytes() == raw_before
    assert skm.recover_secret_key(data_dir, PASSPHRASE) == key


def test_recover_without_package_fails_closed(data_dir):
    """无恢复包直接调恢复：明确报错，指引先回原机创建恢复包。"""
    with pytest.raises(RuntimeError, match="create-recovery"):
        skm.recover_secret_key(data_dir, PASSPHRASE)


def test_create_recovery_requires_readable_key(data_dir, monkeypatch):
    """原机密钥已不可解密时禁止建包（否则打包不了任何有效内容）。"""
    skm.load_or_create_secret_key(data_dir)
    monkeypatch.setattr(skm, "_get_machine_fingerprint", lambda: "new-machine")

    with pytest.raises(RuntimeError, match="创建恢复包失败"):
        skm.create_recovery_package(data_dir, PASSPHRASE)


def test_recovery_package_stores_no_plaintext(data_dir):
    """恢复包内容为密文：不含密钥明文，也不含口令明文。"""
    key = skm.load_or_create_secret_key(data_dir)
    package_path = skm.create_recovery_package(data_dir, PASSPHRASE)

    blob = package_path.read_text(encoding="utf-8")
    assert key not in blob
    assert PASSPHRASE not in blob
    package = json.loads(blob)
    assert package["version"] == 1
    assert package["kdf"] == "pbkdf2-hmac-sha256"
    assert package["iterations"] == skm._KDF_ITERATIONS


def test_passphrase_validation(data_dir):
    """口令过短/为空：创建与恢复同样拒绝（口令是恢复包唯一保护材料）。"""
    skm.load_or_create_secret_key(data_dir)
    with pytest.raises(RuntimeError, match="恢复口令"):
        skm.create_recovery_package(data_dir, "short")
    with pytest.raises(RuntimeError, match="恢复口令"):
        skm.create_recovery_package(data_dir, "")
    with pytest.raises(RuntimeError, match="恢复口令"):
        skm.recover_secret_key(data_dir, "")


def test_cli_recover_flow(data_dir, monkeypatch, capsys):
    """CLI：跨指纹后用 recover 子命令恢复成功；口令错误返回非零且不抛裸异常。"""
    key = skm.load_or_create_secret_key(data_dir)
    skm.create_recovery_package(data_dir, PASSPHRASE)
    monkeypatch.setattr(skm, "_get_machine_fingerprint", lambda: "new-machine")

    assert skm._cli_main(["recover", "--data-dir", data_dir, "--passphrase", PASSPHRASE]) == 0
    assert skm.load_or_create_secret_key(data_dir) == key
    assert "恢复成功" in capsys.readouterr().out

    # 再造一个新包验证口令错误路径：CLI 返回 1 并输出指引，不抛裸异常
    monkeypatch.setattr(skm, "_get_machine_fingerprint", lambda: "another-machine")
    with pytest.raises(RuntimeError):
        skm.load_or_create_secret_key(data_dir)
    assert skm._cli_main(["recover", "--data-dir", data_dir, "--passphrase", "bad-passphrase"]) == 1
    assert "错误" in capsys.readouterr().err
