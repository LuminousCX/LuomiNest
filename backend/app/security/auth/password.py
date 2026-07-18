"""LuomiNest 密码哈希模块。

使用 bcrypt 直接哈希（不通过 passlib），因 passlib 在 bcrypt 4+ 已停止维护。
采用 SHA-256 预哈希绕过 bcrypt 72 字节截断限制：
    hash = bcrypt(base64(sha256(password)))

哈希格式: ``$lnv<N>$<bcrypt_hash>``，``<N>`` 为版本号。
- v1（遗留）: ``bcrypt(password)`` — 明文 bcrypt，受 72 字节截断影响
- v2（当前）: ``bcrypt(b64(sha256(password)))`` — SHA-256 预哈希，全密码参与

验证时自动检测版本，向后兼容 v1 及无版本前缀的旧哈希。
"""

from __future__ import annotations

import asyncio
import base64
import hashlib

_CURRENT_VERSION = 2
_PREFIX_V2 = "$lnv2$"
_PREFIX_V1 = "$lnv1$"

# bcrypt 可选导入：优先 bcrypt 库，回退 passlib
try:
    import bcrypt as _bcrypt

    _USE_BCRYPT = True
except ImportError:
    _USE_BCRYPT = False


def _pre_hash_v2(password: str) -> bytes:
    """SHA-256 预哈希，绕过 bcrypt 72 字节限制。"""
    return base64.b64encode(hashlib.sha256(password.encode("utf-8")).digest())


def _bcrypt_hash_raw(data: bytes) -> str:
    """使用 bcrypt 或 passlib 对原始字节进行哈希，返回哈希字符串。"""
    if _USE_BCRYPT:
        return _bcrypt.hashpw(data, _bcrypt.gensalt()).decode("utf-8")
    else:
        from passlib.hash import bcrypt as passlib_bcrypt

        return passlib_bcrypt.using(rounds=12).hash(data.decode("utf-8", errors="replace"))


def _bcrypt_check_raw(data: bytes, hashed: str) -> bool:
    """使用 bcrypt 或 passlib 验证密码。"""
    if _USE_BCRYPT:
        return _bcrypt.checkpw(data, hashed.encode("utf-8"))
    else:
        from passlib.hash import bcrypt as passlib_bcrypt

        return passlib_bcrypt.verify(data.decode("utf-8", errors="replace"), hashed)


def hash_password(password: str) -> str:
    """对密码进行哈希（当前版本: v2 — SHA-256 + bcrypt）。

    Args:
        password: 明文密码。

    Returns:
        带版本前缀的哈希字符串。
    """
    raw = _bcrypt_hash_raw(_pre_hash_v2(password))
    return f"{_PREFIX_V2}{raw}"


def verify_password(password: str, hashed_password: str) -> bool:
    """验证密码，自动检测哈希版本。

    支持 v2（``$lnv2$…``）、v1（``$lnv1$…``）及无版本前缀的旧哈希
   （视为 v1 以保持向后兼容）。

    Args:
        password: 明文密码。
        hashed_password: 存储的哈希字符串。

    Returns:
        验证通过返回 True，否则 False。
    """
    try:
        if hashed_password.startswith(_PREFIX_V2):
            bcrypt_hash = hashed_password[len(_PREFIX_V2) :]
            return _bcrypt_check_raw(_pre_hash_v2(password), bcrypt_hash)

        if hashed_password.startswith(_PREFIX_V1):
            bcrypt_hash = hashed_password[len(_PREFIX_V1) :]
        else:
            bcrypt_hash = hashed_password

        return _bcrypt_check_raw(password.encode("utf-8"), bcrypt_hash)
    except (ValueError, KeyError):
        # 哈希格式损坏或无效，安全失败（fail closed）
        return False


def needs_rehash(hashed_password: str) -> bool:
    """判断哈希是否使用旧版本，需要重新哈希。"""
    return not hashed_password.startswith(_PREFIX_V2)


async def hash_password_async(password: str) -> str:
    """异步密码哈希（非阻塞）。"""
    return await asyncio.to_thread(hash_password, password)


async def verify_password_async(password: str, hashed_password: str) -> bool:
    """异步密码验证（非阻塞）。"""
    return await asyncio.to_thread(verify_password, password, hashed_password)
