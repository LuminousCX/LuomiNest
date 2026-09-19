"""SECRET_KEY 持久化管理（机器指纹绑定加密存储）。

确保 SECRET_KEY 在重启后保持不变，使 AES 加密数据可跨会话解密。
首次启动时生成 Fernet 兼容的随机密钥，用机器指纹派生密钥加密后写入文件（0600 权限），
后续启动用机器指纹解密读取。

安全特性：
1. 文件内容为密文（非明文），即使文件被复制也无法直接读取
2. 绑定机器指纹 + 随机盐 PBKDF2 高迭代拉伸，数据目录外带无法离线还原密钥
   （旧版为无盐 SHA256 直派生，MachineGuid/machine-id 世界可读即秒破——已带迁移自动升级）
3. 兼容旧版明文格式与旧版 SHA256 密文格式，启动时自动检测并迁移为 KDF 加密格式
"""
import base64
import hashlib
import os
import platform
import stat
import uuid as uuid_mod
from pathlib import Path

from cryptography.fernet import Fernet
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

    注意：若机器硬件变更导致指纹变化，解密会失败并抛出 RuntimeError。
    此时需删除密钥文件重新生成（已加密的 API Key 需重新输入）。

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

            # 4. 既非有效密文也非有效明文
            fingerprint_source = (
                "MAC+主机名回退指纹（不稳定，随网卡/主机名漂移）"
                if fingerprint.startswith("fallback-")
                else "OS 级机器 ID（MachineGuid/machine-id）"
            )
            logger.error(
                f"[SecretKey] 无法解密 {key_path}（机器指纹不匹配或文件损坏；"
                f"当前指纹来源: {fingerprint_source}）。"
                "若硬件已变更，删除该文件后重启可重新生成（已加密的 API Key 需重新输入）。"
            )
            raise RuntimeError(
                f"{name} 解密失败：机器指纹不匹配或文件损坏"
                f"（当前指纹来源: {fingerprint_source}）。"
                f"请删除 {key_path} 后重启应用。"
            )

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


def is_placeholder(secret_key: str | None) -> bool:
    """判断 SECRET_KEY 是否为空或占位符。"""
    return not secret_key or secret_key == DEFAULT_PLACEHOLDER
