import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from loguru import logger

from app.core.config import settings


class LumiAesCipher:
    """AES 加密器，用于敏感数据（如 API Key）的加密存储。

    使用 Fernet（AES-128-CBC + HMAC-SHA256）对称加密，
    密钥从 settings.SECRET_KEY 派生，无需额外管理密钥文件。
    """

    def __init__(self, secret_key: str | None = None):
        key_source = secret_key or settings.SECRET_KEY
        if not key_source or key_source == "change-me-in-production":
            logger.warning("[AesCipher] SECRET_KEY is not set or using default, generating ephemeral key")
            key_source = Fernet.generate_key().decode()

        digest = hashlib.sha256(key_source.encode()).digest()
        self._fernet = Fernet(base64.urlsafe_b64encode(digest))

    def encrypt(self, plaintext: str) -> str:
        """加密明文字符串，返回 base64 编码的密文。"""
        if not plaintext:
            return ""
        token = self._fernet.encrypt(plaintext.encode("utf-8"))
        return token.decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        """解密密文字符串，返回明文。解密失败返回空字符串。"""
        if not ciphertext:
            return ""
        try:
            token = self._fernet.decrypt(ciphertext.encode("utf-8"))
            return token.decode("utf-8")
        except InvalidToken:
            logger.error("[AesCipher] Failed to decrypt: invalid token or wrong key")
            return ""

    def encrypt_dict(self, data: dict) -> dict:
        """加密字典中所有字符串值，返回新字典。"""
        result = {}
        for key, value in data.items():
            if isinstance(value, str) and value:
                result[key] = self.encrypt(value)
            else:
                result[key] = value
        return result

    def decrypt_dict(self, data: dict) -> dict:
        """解密字典中所有字符串值，返回新字典。"""
        result = {}
        for key, value in data.items():
            if isinstance(value, str) and value:
                result[key] = self.decrypt(value)
            else:
                result[key] = value
        return result


_lumi_cipher: LumiAesCipher | None = None


def get_cipher() -> LumiAesCipher:
    """获取全局 AES 加密器单例。"""
    global _lumi_cipher
    if _lumi_cipher is None:
        _lumi_cipher = LumiAesCipher()
    return _lumi_cipher
