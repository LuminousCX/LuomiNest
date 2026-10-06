"""SECRET_KEY 持久化管理（机器指纹绑定加密存储）。

确保 SECRET_KEY 在重启后保持不变，使 AES 加密数据可跨会话解密。
首次启动时生成 Fernet 兼容的随机密钥，用机器指纹派生密钥加密后写入文件（0600 权限），
后续启动用机器指纹解密读取。

安全特性：
1. 文件内容为密文（非明文），即使文件被复制也无法直接读取
2. 绑定机器指纹 + 随机盐 PBKDF2 高迭代拉伸，数据目录外带无法离线还原密钥
   （旧版为无盐 SHA256 直派生，MachineGuid/machine-id 世界可读即秒破——已带迁移自动升级）
3. 兼容旧版明文格式与旧版 SHA256 密文格式，启动时自动检测并迁移为 KDF 加密格式

跨机器恢复（恢复包，换机/重装系统/容器重建场景）：
- 用户在原机显式执行 create-recovery（CLI 或函数），用「恢复口令」PBKDF2 派生密钥
  加密当前 SECRET_KEY 生成 {file}.recovery（JSON，0600）；口令不落盘、不自动生成。
- 新机器上指纹变化导致解密失败时，凭恢复包 + 口令执行 recover：解出原密钥并按当前
  指纹重新加密落盘，已加密数据（如 LLM API Key）全部可继续解密。
- 无恢复包时保持 fail-closed：宁可不可恢复也不降级安全（无明文落盘、无硬编码兜底密钥），
  报错信息附带可操作的处理指引。容器/无头部署也可在首启前显式设置 SECRET_KEY/
  JWT_SECRET_KEY 环境变量跳过机器绑定。
"""
import base64
import hashlib
import json
import os
import platform
import stat
import sys
import uuid as uuid_mod
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from loguru import logger

DEFAULT_PLACEHOLDER = "change-me-in-production"
SECRET_KEY_FILE_NAME = "secret_key"
JWT_SECRET_KEY_FILE_NAME = "jwt_secret_key"

# PBKDF2-HMAC-SHA256 迭代次数（OWASP 推荐）与盐长度。
# 机器指纹来源（MachineGuid/machine-id）世界可读，无盐直派生可被离线秒破，
# 高迭代拉伸 + 随机盐是数据目录外带场景下的核心防线。
_KDF_ITERATIONS = 600_000
_KDF_SALT_BYTES = 32

# 恢复包：{file}.recovery（JSON），口令 PBKDF2 加密的密钥副本，参数与主密钥 KDF 一致。
RECOVERY_PACKAGE_SUFFIX = ".recovery"
_RECOVERY_PACKAGE_VERSION = 1
_RECOVERY_PACKAGE_KDF = "pbkdf2-hmac-sha256"
# 恢复口令下限：口令是恢复包唯一的保护材料，过短等同把密钥裸奔在数据目录里。
_MIN_PASSPHRASE_LEN = 8


def _diagnostic_name(file_name: str) -> str:
    """根据密钥文件名返回日志/异常中使用的诊断名称。"""
    if file_name == JWT_SECRET_KEY_FILE_NAME:
        return "JWT_SECRET_KEY"
    return "SECRET_KEY"


def get_secret_key_path(data_dir: str, file_name: str = SECRET_KEY_FILE_NAME) -> Path:
    """返回密钥持久化文件路径。

    Args:
        data_dir: 数据目录。
        file_name: 密钥文件名（默认 ``secret_key``，JWT 密钥用 ``jwt_secret_key``）。
    """
    return Path(data_dir) / "config" / file_name


def _get_machine_fingerprint() -> str:
    """获取稳定的机器指纹（用于绑定 SECRET_KEY 到当前机器）。

    优先级：
    - Windows: HKLM\\SOFTWARE\\Microsoft\\Cryptography\\MachineGuid
    - macOS: IOPlatformUUID
    - Linux: /etc/machine-id 或 /var/lib/dbus/machine-id
    - 兜底: MAC 地址 + 主机名（不如 OS 级 ID 稳定，但好过无绑定）
    """
    system = platform.system()

    if system == "Windows":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography",
            ) as key:
                guid, _ = winreg.QueryValueEx(key, "MachineGuid")
                if guid:
                    return f"win-{guid}"
        except Exception as exc:
            logger.debug(f"读取 Windows MachineGuid 失败，继续使用其他指纹来源: {exc}")

    if system == "Darwin":
        try:
            import subprocess

            result = subprocess.run(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            for line in result.stdout.splitlines():
                if "IOPlatformUUID" in line:
                    parts = line.split('"')
                    if len(parts) >= 4:
                        return f"mac-{parts[-2]}"
        except Exception as e:
            # Darwin 平台指纹探测失败时允许降级到后续方案，避免影响启动流程。
            logger.debug("Failed to read Darwin IOPlatformUUID, fallback to next fingerprint source: {}", e)

    if system == "Linux":
        for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
            try:
                content = Path(path).read_text(encoding="utf-8").strip()
                if content:
                    return f"linux-{content}"
            except Exception as exc:
                logger.debug(f"读取机器指纹文件失败: {path}, err={exc}")

    # 兜底：MAC 地址 + 主机名。该指纹不稳定（随网卡/主机名漂移），
    # 以它加密的密钥文件在环境变化后将永久无法解密，必须让这条路径可见。
    mac = uuid_mod.getnode()
    hostname = platform.node()
    fingerprint = f"fallback-{mac}-{hostname}"
    logger.warning(
        "[SecretKey] OS 级机器 ID 不可用，回退到 MAC+主机名的不稳定指纹"
        "（网卡/主机名变更后，已加密的密钥文件可能无法解密）"
    )
    return fingerprint


def _derive_machine_key(fingerprint: str) -> bytes:
    """旧版派生：SHA256(指纹) 直派生 Fernet 密钥。

    仅用于兼容读取升级前的旧密文（成功读取后会立即迁移到 PBKDF2 格式）。
    """
    digest = hashlib.sha256(fingerprint.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _kdf_salt_path(data_dir: str, file_name: str) -> Path:
    """返回 KDF 盐文件路径（每个密钥文件独立盐）。"""
    return Path(data_dir) / "config" / f"{file_name}.kdf-salt"


def _load_or_create_kdf_salt(data_dir: str, file_name: str) -> bytes:
    """加载或生成本密钥文件的 KDF 随机盐（与密钥文件同级存储，0600）。"""
    salt_path = _kdf_salt_path(data_dir, file_name)
    if salt_path.exists():
        salt = salt_path.read_bytes()
        if len(salt) >= 16:
            return salt
    salt = os.urandom(_KDF_SALT_BYTES)
    salt_path.write_bytes(salt)
    try:
        os.chmod(salt_path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    return salt


def _derive_kdf_key(fingerprint: str, salt: bytes) -> bytes:
    """新版派生：PBKDF2-HMAC-SHA256（随机盐 + 高迭代）拉伸机器指纹为 Fernet 密钥。"""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=_KDF_ITERATIONS,
    )
    return base64.urlsafe_b64encode(kdf.derive(fingerprint.encode("utf-8")))


def _derive_passphrase_key(passphrase: str, salt: bytes, iterations: int) -> bytes:
    """恢复包派生：PBKDF2-HMAC-SHA256 拉伸用户恢复口令为 Fernet 密钥。"""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=iterations,
    )
    return base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8")))


def _is_valid_fernet_key(key_str: str) -> bool:
    """检查字符串是否是合法的 Fernet key（urlsafe base64，32 字节解码后）。

    用于区分旧版明文格式和新版密文格式。
    """
    if not key_str:
        return False
    try:
        decoded = base64.urlsafe_b64decode(key_str.encode("ascii"))
        return len(decoded) == 32
    except Exception:
        return False


def load_or_create_secret_key(data_dir: str, file_name: str = SECRET_KEY_FILE_NAME) -> str:
    """加载或生成持久化密钥（机器指纹绑定 + PBKDF2 加盐拉伸存储）。

    流程：
    1. 文件存在 → 用 PBKDF2+盐 派生密钥尝试解密（当前格式）
    2. 解密失败 → 尝试旧版 SHA256 直派生密文兼容读取，成功则立即用新 KDF 重加密覆写（迁移）
    3. 仍失败 → 尝试作为旧版明文读取（兼容迁移），验证后加密覆写
    4. 明文也不合法 → 抛出 RuntimeError
    5. 文件不存在 → 生成新密钥，用新 KDF 加密后写入文件（0600）

    数据兼容说明：升级前存储的旧格式（SHA256 直派生密文）会在首次加载时自动迁移，
    用户无感知，全部 API Key 保持可解密。盐文件（{file}.kdf-salt）丢失等同机器指纹变更，
    需删除密钥文件重新生成（已加密的 API Key 需重新输入）。

    注意：机器指纹变化（换机/重装系统/容器重建）时解密会失败并抛出 RuntimeError
    （fail-closed）。若此前在原机创建过恢复包，按报错信息中的指引执行 recover 即可
    恢复原密钥；若无恢复包，只能删除密钥文件重新生成（已加密的 API Key 需重新输入）。

    Args:
        data_dir: 数据目录。
        file_name: 密钥文件名（默认 ``secret_key``，JWT 密钥用 ``jwt_secret_key``）。
    """
    key_path = get_secret_key_path(data_dir, file_name)
    key_path.parent.mkdir(parents=True, exist_ok=True)
    name = _diagnostic_name(file_name)

    fingerprint = _get_machine_fingerprint()

    def _kdf_fernet() -> Fernet:
        return Fernet(_derive_kdf_key(fingerprint, _load_or_create_kdf_salt(data_dir, file_name)))

    machine_fernet_legacy = Fernet(_derive_machine_key(fingerprint))

    if key_path.exists():
        raw = key_path.read_bytes()
        if raw:
            # 1. 尝试按当前格式（PBKDF2+盐）解密
            try:
                secret_key = _kdf_fernet().decrypt(raw).decode("utf-8").strip()
                if secret_key:
                    return secret_key
            except Exception as e:
                # 预期回退路径：旧版 SHA256 直派生密文或明文格式
                logger.debug(f"[SecretKey] KDF 密文解密失败，尝试旧版兼容读取: {e}")

            # 2. 旧版 SHA256 直派生密文：解出后立即用新 KDF 重加密落盘（自动迁移）
            try:
                secret_key = machine_fernet_legacy.decrypt(raw).decode("utf-8").strip()
                if secret_key:
                    encrypted = _kdf_fernet().encrypt(secret_key.encode("utf-8"))
                    key_path.write_bytes(encrypted)
                    try:
                        os.chmod(key_path, stat.S_IRUSR | stat.S_IWUSR)
                    except OSError:
                        pass
                    logger.success(
                        f"[SecretKey] 已将旧版 SHA256 直派生密文迁移为 PBKDF2+盐 格式（{name}）"
                    )
                    return secret_key
            except Exception:
                pass

            # 3. 尝试作为旧版明文读取（兼容迁移）
            try:
                plaintext = raw.decode("utf-8").strip()
                if plaintext and _is_valid_fernet_key(plaintext):
                    # 旧明文格式：用机器指纹加密后覆写，完成迁移
                    encrypted = _kdf_fernet().encrypt(plaintext.encode("utf-8"))
                    key_path.write_bytes(encrypted)
                    try:
                        os.chmod(key_path, stat.S_IRUSR | stat.S_IWUSR)
                    except OSError:
                        # Windows 上 chmod 语义不同，best-effort
                        pass
                    logger.success(
                        f"[SecretKey] 已将旧版明文 {name} 迁移为机器绑定加密格式"
                    )
                    return plaintext
            except Exception:
                # 旧版明文解析失败：继续走后续统一错误处理（既非有效密文也非有效明文）
                pass

            # 4. 既非有效密文也非有效明文：fail-closed，但给出可操作的恢复指引
            raise _unreadable_key_error(data_dir, file_name, fingerprint, key_path, name)

    # 5. 文件不存在或为空：生成新密钥并用新 KDF 加密后存储
    new_key = Fernet.generate_key().decode("utf-8")
    encrypted = _kdf_fernet().encrypt(new_key.encode("utf-8"))
    key_path.write_bytes(encrypted)
    try:
        os.chmod(key_path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        # Windows 上 chmod 语义不同，best-effort
        pass

    logger.success(f"[SecretKey] Generated machine-bound {name} at {key_path}")
    return new_key


# ── 恢复包（跨机器恢复密钥的唯一合法途径）────────────────────────────────────
#
# 恢复包 = 用「恢复口令」PBKDF2 派生密钥加密的密钥文件副本（JSON，0600）。
# 仅在用户显式调用时创建：绝不自动生成、口令不落盘、内容为密文（非明文）。
# 换机/容器重建后凭恢复包 + 口令解出原密钥，再按当前机器指纹重新加密落盘；
# 无恢复包时保持 fail-closed：宁可不可恢复也不降级安全。


def _validate_passphrase(passphrase: str) -> str:
    """校验恢复口令非空且达到最小长度（口令是恢复包唯一的保护材料）。"""
    if not isinstance(passphrase, str) or len(passphrase) < _MIN_PASSPHRASE_LEN:
        raise RuntimeError(f"恢复口令无效：不能为空且至少 {_MIN_PASSPHRASE_LEN} 个字符")
    return passphrase


def get_recovery_package_path(data_dir: str, file_name: str = SECRET_KEY_FILE_NAME) -> Path:
    """返回恢复包路径（与密钥文件同级：{file}.recovery）。"""
    return Path(data_dir) / "config" / f"{file_name}{RECOVERY_PACKAGE_SUFFIX}"


def has_recovery_package(data_dir: str, file_name: str = SECRET_KEY_FILE_NAME) -> bool:
    """判断指定密钥是否已存在恢复包。"""
    return get_recovery_package_path(data_dir, file_name).exists()


def create_recovery_package(data_dir: str, passphrase: str, file_name: str = SECRET_KEY_FILE_NAME) -> Path:
    """在原机为当前密钥创建口令恢复包（换机/重装前务必执行一次）。

    要求当前机器能解密既有密钥（恢复包本质是密钥的口令加密副本，原机都解不出
    就没有可打包的内容）；密钥文件尚不存在时会先按常规流程生成再打包。

    Args:
        data_dir: 数据目录（恢复包与密钥文件同级存放）。
        passphrase: 恢复口令（不落盘，只用于派生加密密钥；请用户自行妥善保管）。
        file_name: 密钥文件名（默认 ``secret_key``，JWT 密钥用 ``jwt_secret_key``）。

    Returns:
        恢复包路径。
    """
    _validate_passphrase(passphrase)
    try:
        secret_key = load_or_create_secret_key(data_dir, file_name)
    except RuntimeError as exc:
        raise RuntimeError(
            "创建恢复包失败：当前机器无法解密既有密钥（恢复包必须在原机、密钥尚可解密时创建）。"
            f"{exc}"
        ) from exc

    salt = os.urandom(_KDF_SALT_BYTES)
    token = Fernet(_derive_passphrase_key(passphrase, salt, _KDF_ITERATIONS)).encrypt(
        secret_key.encode("utf-8")
    )
    package = {
        "version": _RECOVERY_PACKAGE_VERSION,
        "kdf": _RECOVERY_PACKAGE_KDF,
        "iterations": _KDF_ITERATIONS,
        "salt": base64.urlsafe_b64encode(salt).decode("ascii"),
        "token": token.decode("ascii"),
    }
    package_path = get_recovery_package_path(data_dir, file_name)
    package_path.parent.mkdir(parents=True, exist_ok=True)
    package_path.write_text(json.dumps(package, indent=2), encoding="utf-8")
    try:
        os.chmod(package_path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        # Windows 上 chmod 语义不同，best-effort
        pass

    logger.success(
        f"[SecretKey] 已创建恢复包 {package_path}"
        "（口令不落盘，请妥善保管；换机/重装/容器重建后凭它恢复密钥）"
    )
    return package_path


def recover_secret_key(data_dir: str, passphrase: str, file_name: str = SECRET_KEY_FILE_NAME) -> str:
    """跨机器恢复：用恢复口令解出原密钥，并按当前机器指纹重新加密落盘。

    Fail-Closed：恢复包缺失/损坏/版本不符/口令错误均抛 RuntimeError，不做任何降级
    兜底。成功后下次启动 ``load_or_create_secret_key`` 即可正常解密，已加密数据
    （如 LLM API Key）随之恢复。

    Args:
        data_dir: 数据目录（含随数据卷迁移过来的恢复包）。
        passphrase: 创建恢复包时设置的恢复口令。
        file_name: 密钥文件名（默认 ``secret_key``，JWT 密钥用 ``jwt_secret_key``）。

    Returns:
        恢复出的原密钥。
    """
    _validate_passphrase(passphrase)
    name = _diagnostic_name(file_name)
    package_path = get_recovery_package_path(data_dir, file_name)
    if not package_path.exists():
        raise RuntimeError(
            f"{name} 恢复失败：未找到恢复包 {package_path}。"
            "恢复包必须在原机（密钥尚可解密时）通过 create-recovery 创建，并随数据目录整体迁移。"
        )

    try:
        package = json.loads(package_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"{name} 恢复失败：恢复包 {package_path} 损坏或格式不识别。") from exc

    # 版本/KDF 参数不符 = 格式不受支持或文件疑似被篡改，直接拒绝（不给暴力降级空间）
    if (
        package.get("version") != _RECOVERY_PACKAGE_VERSION
        or package.get("kdf") != _RECOVERY_PACKAGE_KDF
        or package.get("iterations") != _KDF_ITERATIONS
    ):
        raise RuntimeError(f"{name} 恢复失败：恢复包参数异常（版本不受支持或疑似被篡改），拒绝恢复。")

    try:
        salt = base64.urlsafe_b64decode(package["salt"])
        token = package["token"].encode("ascii")
    except Exception as exc:
        raise RuntimeError(f"{name} 恢复失败：恢复包字段缺失或损坏。") from exc

    try:
        secret_key = (
            Fernet(_derive_passphrase_key(passphrase, salt, _KDF_ITERATIONS))
            .decrypt(token)
            .decode("utf-8")
            .strip()
        )
    except InvalidToken as exc:
        raise RuntimeError(
            f"{name} 恢复失败：恢复口令错误（或该恢复包由其他口令创建）。"
            "数据未被改动，修正口令后可重试。"
        ) from exc

    if not secret_key or not _is_valid_fernet_key(secret_key):
        raise RuntimeError(f"{name} 恢复失败：恢复包内容不是合法密钥，拒绝写入。")

    # 用当前机器指纹重新加密落盘（盐沿用数据目录内既有盐，缺失则新生成）
    key_path = get_secret_key_path(data_dir, file_name)
    key_path.parent.mkdir(parents=True, exist_ok=True)
    encrypted = Fernet(
        _derive_kdf_key(_get_machine_fingerprint(), _load_or_create_kdf_salt(data_dir, file_name))
    ).encrypt(secret_key.encode("utf-8"))
    key_path.write_bytes(encrypted)
    try:
        os.chmod(key_path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        # Windows 上 chmod 语义不同，best-effort
        pass

    logger.success(f"[SecretKey] 已从恢复包恢复 {name} 并重新绑定当前机器（{key_path}）")
    return secret_key


def _unreadable_key_error(
    data_dir: str, file_name: str, fingerprint: str, key_path: Path, name: str
) -> RuntimeError:
    """构造密钥解密失败（指纹不匹配/文件损坏）的可操作报错。

    Fail-Closed 不变：仍然拒绝启动并抛 RuntimeError，但报错信息会根据恢复包
    是否存在给出对应处理指引，而不是让用户面对裸异常自行猜测。
    """
    fingerprint_source = (
        "MAC+主机名回退指纹（不稳定，随网卡/主机名漂移）"
        if fingerprint.startswith("fallback-")
        else "OS 级机器 ID（MachineGuid/machine-id）"
    )
    cli = "python -m app.security.crypto.secret_key_manager"
    file_arg = "" if file_name == SECRET_KEY_FILE_NAME else f" --file {file_name}"
    recovery_path = get_recovery_package_path(data_dir, file_name)

    if recovery_path.exists():
        hint = (
            f"检测到恢复包 {recovery_path}，可在本机恢复原密钥：\n"
            f"  {cli} recover --data-dir \"{Path(data_dir)}\"{file_arg}\n"
            "按提示输入创建恢复包时设置的恢复口令，恢复成功后重新启动应用即可。"
        )
    else:
        hint = (
            "未找到恢复包，换机/重装/容器重建后已加密数据（如 LLM API Key）无法解密。可选处理：\n"
            f"  1) 回到原机执行 {cli} create-recovery --data-dir \"<原数据目录>\"{file_arg} 生成恢复包，"
            "随数据目录整体迁移到本机后再执行 recover 子命令；\n"
            f"  2) 放弃旧数据：删除 {key_path} 与 {_kdf_salt_path(data_dir, file_name)} 后重启应用，"
            "密钥将重新生成，但需重新录入全部 API Key；\n"
            "  3) 容器/无头部署：首次启动前显式设置 SECRET_KEY/JWT_SECRET_KEY 环境变量可跳过机器绑定。"
        )

    logger.error(
        f"[SecretKey] 无法解密 {key_path}（机器指纹不匹配或文件损坏；"
        f"当前指纹来源: {fingerprint_source}）。{hint}"
    )
    return RuntimeError(
        f"{name} 解密失败：机器指纹不匹配或文件损坏（当前指纹来源: {fingerprint_source}）。{hint}"
    )


# ── 最小 CLI（恢复入口；不为此开放 HTTP API）─────────────────────────────────


def _cli_main(argv: list[str] | None = None) -> int:
    """密钥恢复工具 CLI。用法（在 backend/ 目录、用后端 venv 执行）：

    创建恢复包（原机）:   python -m app.security.crypto.secret_key_manager create-recovery --data-dir <数据目录>
    跨机器恢复（新机）:   python -m app.security.crypto.secret_key_manager recover --data-dir <数据目录>
    JWT 密钥加 --file jwt_secret_key；口令默认交互式输入，脚本场景可用 --passphrase。
    """
    import argparse
    import getpass

    parser = argparse.ArgumentParser(
        prog="python -m app.security.crypto.secret_key_manager",
        description="LuomiNest 密钥恢复工具：为机器绑定密钥创建口令恢复包，或在新机器上恢复。",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command, help_text in (
        ("create-recovery", "在原机为当前密钥创建口令恢复包（需密钥当前可解密）"),
        ("recover", "在新机器/容器上用恢复口令恢复密钥（成功后重启应用）"),
    ):
        sub = subparsers.add_parser(command, help=help_text)
        sub.add_argument("--data-dir", required=True, help="LuomiNest 数据目录（含 config/ 的那一级）")
        sub.add_argument(
            "--file",
            default=SECRET_KEY_FILE_NAME,
            choices=(SECRET_KEY_FILE_NAME, JWT_SECRET_KEY_FILE_NAME),
            help="密钥文件名（默认 secret_key；JWT 密钥用 jwt_secret_key）",
        )
        sub.add_argument(
            "--passphrase",
            default=None,
            help="恢复口令；省略则交互式输入（推荐，避免口令留在 shell 历史/进程列表）",
        )
    args = parser.parse_args(argv)

    if args.passphrase is None:
        args.passphrase = getpass.getpass("请输入恢复口令: ")
        if args.command == "create-recovery":
            if getpass.getpass("请再次输入恢复口令: ") != args.passphrase:
                print("两次输入的口令不一致，已取消。", file=sys.stderr)
                return 1

    try:
        if args.command == "create-recovery":
            package_path = create_recovery_package(args.data_dir, args.passphrase, args.file)
            print(f"恢复包已创建: {package_path}")
            print("请妥善保管恢复口令（不落盘），并将该恢复包随数据目录一起迁移。")
        else:
            recover_secret_key(args.data_dir, args.passphrase, args.file)
            print("密钥恢复成功，已重新绑定当前机器，请重启应用。")
        return 0
    except RuntimeError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(_cli_main())


def is_placeholder(secret_key: str | None) -> bool:
    """判断 SECRET_KEY 是否为空或占位符。"""
    return not secret_key or secret_key == DEFAULT_PLACEHOLDER
