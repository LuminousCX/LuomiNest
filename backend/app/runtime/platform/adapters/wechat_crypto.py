import base64
import hashlib
import socket
import struct
import time
import xml.etree.ElementTree as ET
from typing import Any
from loguru import logger

try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False


class LuomiNestWeChatCrypto:
    """微信消息加解密辅助类（企业微信/公众号通用，纯 Python 实现）。

    基于 WXBizMsgCrypt 协议：
    - 签名：sha1(sort(token, timestamp, nonce, encrypt))
    - 加解密：AES-256-CBC，key = base64decode(encoding_aes_key + "=")
    - 解密后内容：16字节随机串 + 4字节网络序消息长度 + 消息体 + corp_id
    """

    def __init__(self, token: str, encoding_aes_key: str, app_id: str) -> None:
        self._token = token
        self._app_id = app_id
        self._aes_key = base64.b64decode(encoding_aes_key + "=")
        self._iv = self._aes_key[:16]

    @staticmethod
    def is_available() -> bool:
        return _CRYPTO_AVAILABLE

    def verify_signature(self, signature: str, timestamp: str, nonce: str, encrypt: str = "") -> bool:
        parts = sorted([self._token, timestamp, nonce, encrypt]) if encrypt else sorted([self._token, timestamp, nonce])
        computed = hashlib.sha1("".join(parts).encode()).hexdigest()
        return computed == signature

    def decrypt(self, encrypt: str) -> tuple[str, str]:
        """解密消息，返回 (xml_content, app_id)。"""
        if not _CRYPTO_AVAILABLE:
            raise RuntimeError("cryptography library not available")

        ciphertext = base64.b64decode(encrypt)
        cipher = Cipher(algorithms.AES(self._aes_key), modes.CBC(self._iv), backend=default_backend())
        decryptor = cipher.decryptor()
        plaintext = decryptor.update(ciphertext) + decryptor.finalize()

        pad_len = plaintext[-1]
        content = plaintext[:-pad_len]

        random_bytes = content[:16]
        msg_len = struct.unpack("!I", content[16:20])[0]
        xml_content = content[20:20 + msg_len].decode("utf-8")
        from_id = content[20 + msg_len:].decode("utf-8")

        return xml_content, from_id

    def encrypt(self, reply_msg: str) -> str:
        """加密回复消息，返回 base64 密文。"""
        if not _CRYPTO_AVAILABLE:
            raise RuntimeError("cryptography library not available")

        random_bytes = socket.inet_aton(socket.inet_ntoa(struct.pack("I", int(time.time()))))
        msg_bytes = reply_msg.encode("utf-8")
        app_id_bytes = self._app_id.encode("utf-8")

        content = random_bytes + struct.pack("!I", len(msg_bytes)) + msg_bytes + app_id_bytes

        pad_len = 32 - (len(content) % 32)
        padding = bytes([pad_len] * pad_len)
        plaintext = content + padding

        cipher = Cipher(algorithms.AES(self._aes_key), modes.CBC(self._iv), backend=default_backend())
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(plaintext) + encryptor.finalize()

        return base64.b64encode(ciphertext).decode("utf-8")

    def generate_signature(self, timestamp: str, nonce: str, encrypt: str) -> str:
        parts = sorted([self._token, timestamp, nonce, encrypt])
        return hashlib.sha1("".join(parts).encode()).hexdigest()

    @staticmethod
    def parse_xml(xml_str: str) -> dict[str, str]:
        """解析微信 XML 消息为字典。"""
        root = ET.fromstring(xml_str)
        result: dict[str, str] = {}
        for child in root:
            result[child.tag] = child.text or ""
        return result

    @staticmethod
    def build_encrypted_reply(
        crypto: "LuomiNestWeChatCrypto",
        to_user: str,
        from_user: str,
        content: str,
        timestamp: str,
        nonce: str,
    ) -> str:
        """构建加密的 XML 回复（用于公众号被动回复）。"""
        plain_xml = (
            f"<xml>"
            f"<ToUserName><![CDATA[{to_user}]]></ToUserName>"
            f"<FromUserName><![CDATA[{from_user}]]></FromUserName>"
            f"<CreateTime>{int(time.time())}</CreateTime>"
            f"<MsgType><![CDATA[text]]></MsgType>"
            f"<Content><![CDATA[{content}]]></Content>"
            f"</xml>"
        )

        encrypt = crypto.encrypt(plain_xml)
        signature = crypto.generate_signature(timestamp, nonce, encrypt)

        return (
            f"<xml>"
            f"<Encrypt><![CDATA[{encrypt}]]></Encrypt>"
            f"<MsgSignature><![CDATA[{signature}]]></MsgSignature>"
            f"<TimeStamp>{timestamp}</TimeStamp>"
            f"<Nonce><![CDATA[{nonce}]]></Nonce>"
            f"</xml>"
        )
