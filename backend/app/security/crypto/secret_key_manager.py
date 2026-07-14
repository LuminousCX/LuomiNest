"""SECRET_KEY 持久化管理（机器指纹绑定加密存储）。

确保 SECRET_KEY 在重启后保持不变，使 AES 加密数据可跨会话解密。
首次启动时生成 Fernet 兼容的随机密钥，用机器指纹派生密钥加密后写入文件（0600 权限），
后续启动用机器指纹解密读取。

安全特性：
1. 文件内容为密文（非明文），即使文件被复制也无法直接读取
2. 绑定机器指纹，文件被复制到其他机器时解密失败
3. 兼容旧版明文格式，启动时自动检测并迁移为加密格式
"""
import base64
import hashlib
import os
import platform
import stat
import uuid as uuid_mod
from pathlib import Path

from cryptography.fernet import Fernet
from loguru import logger

DEFAULT_PLACEHOLDER = "change-me-in-production"
SECRET_KEY_FILE_NAME = "secret_key"


def get_secret_key_path(data_dir: str) -> Path:
    """返回 SECRET_KEY 持久化文件路径。"""
    return Path(data_dir) / "config" / SECRET_KEY_FILE_NAME


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
        except Exception:
            pass

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
        except Exception:
            pass

    if system == "Linux":
        for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
            try:
                content = Path(path).read_text(encoding="utf-8").strip()
                if content:
                    return f"linux-{content}"
            except Exception:
                pass

    # 兜底：MAC 地址 + 主机名
    mac = uuid_mod.getnode()
    hostname = platform.node()
    return f"fallback-{mac}-{hostname}"


def _derive_machine_key(fingerprint: str) -> bytes:
    """从机器指纹派生 Fernet 密钥（用于加密/解密 SECRET_KEY 文件）。"""
    digest = hashlib.sha256(fingerprint.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


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


def load_or_create_secret_key(data_dir: str) -> str:
    """加载或生成持久化 SECRET_KEY（机器指纹绑定加密存储）。

    流程：
    1. 文件存在 → 尝试用机器指纹解密
    2. 解密失败 → 尝试作为旧版明文读取（兼容迁移），验证后加密覆写
    3. 明文也不合法 → 抛出 RuntimeError
    4. 文件不存在 → 生成新密钥，加密后写入文件（0600）

    注意：若机器硬件变更导致指纹变化，且文件不是旧明文格式，解密会失败并抛出 RuntimeError。
    此时需删除 secret_key 文件重新生成（已加密的 API Key 需重新输入）。
    """
    key_path = get_secret_key_path(data_dir)
    key_path.parent.mkdir(parents=True, exist_ok=True)

    fingerprint = _get_machine_fingerprint()
    machine_key = _derive_machine_key(fingerprint)
    machine_fernet = Fernet(machine_key)

    if key_path.exists():
        raw = key_path.read_bytes()
        if raw:
            # 1. 尝试作为密文解密（新版格式）
            try:
                secret_key = machine_fernet.decrypt(raw).decode("utf-8").strip()
                if secret_key:
                    return secret_key
            except Exception:
                pass

            # 2. 尝试作为旧版明文读取（兼容迁移）
            try:
                plaintext = raw.decode("utf-8").strip()
                if plaintext and _is_valid_fernet_key(plaintext):
                    # 旧明文格式：用机器指纹加密后覆写，完成迁移
                    encrypted = machine_fernet.encrypt(plaintext.encode("utf-8"))
                    key_path.write_bytes(encrypted)
                    try:
                        os.chmod(key_path, stat.S_IRUSR | stat.S_IWUSR)
                    except OSError:
                        pass
                    logger.success(
                        "[SecretKey] 已将旧版明文 SECRET_KEY 迁移为机器绑定加密格式"
                    )
                    return plaintext
            except Exception:
                pass

            # 3. 既非有效密文也非有效明文
            logger.error(
                f"[SecretKey] 无法解密 {key_path}（机器指纹不匹配或文件损坏）。"
                "若硬件已变更，删除该文件后重启可重新生成（已加密的 API Key 需重新输入）。"
            )
            raise RuntimeError(
                "SECRET_KEY 解密失败：机器指纹不匹配或文件损坏。"
                "请删除 data/config/secret_key 后重启应用。"
            )

    # 4. 文件不存在或为空：生成新密钥并用机器指纹加密后存储
    new_key = Fernet.generate_key().decode("utf-8")
    encrypted = machine_fernet.encrypt(new_key.encode("utf-8"))
    key_path.write_bytes(encrypted)
    try:
        os.chmod(key_path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        # Windows 上 chmod 语义不同，best-effort
        pass

    logger.success(f"[SecretKey] Generated machine-bound SECRET_KEY at {key_path}")
    return new_key


def is_placeholder(secret_key: str | None) -> bool:
    """判断 SECRET_KEY 是否为空或占位符。"""
    return not secret_key or secret_key == DEFAULT_PLACEHOLDER
