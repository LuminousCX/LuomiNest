"""ConfigRepository — KV 配置存储（替代 LumiConfigStore）。

保留 fnmatch 加密模式：敏感字段（api_key/secret_key）自动 AES 加密。
- set(key, value): 判定是否加密 → 序列化 → 存储
- get(key): 读取 → 判定是否加密 → 反序列化 → 返回明文
- get_namespace(prefix): 返回前缀下所有配置（自动解密）
- list_all(): 加密字段返回 "***" 而非明文
"""
import asyncio
import fnmatch
import json
from typing import Any, Optional

from sqlalchemy import delete as sa_delete, select
from loguru import logger

from app.core.utils import utc_now
from app.infrastructure.database.models.config_item import ConfigItem
from app.infrastructure.database.session import sync_session_factory
from app.security.crypto.aes_cipher import get_cipher


class ConfigRepository:
    """KV 配置 Repository，方法签名与 LumiConfigStore 对齐。"""

    ENCRYPTED_PATTERNS: set[str] = {
        "llm.api_key",
        "llm.providers.*.api_key",
        "system.secret_key",
    }

    def _is_encrypted_key(self, key: str) -> bool:
        return any(fnmatch.fnmatch(key, p) for p in self.ENCRYPTED_PATTERNS)

    def _serialize(self, key: str, value: Any) -> tuple[str, str, bool]:
        """序列化 value → (stored_value, value_type, encrypted)。"""
        is_encrypted = self._is_encrypted_key(key)
        if is_encrypted and isinstance(value, str) and value:
            cipher = get_cipher()
            return cipher.encrypt(value), "str", True
        return json.dumps(value, ensure_ascii=False), type(value).__name__, False

    def _deserialize(self, stored_value: str, value_type: str, encrypted: bool) -> Any:
        """反序列化 stored_value → 原始值。"""
        if not stored_value:
            return None
        if encrypted:
            cipher = get_cipher()
            decrypted = cipher.decrypt(stored_value)
            return decrypted if decrypted else stored_value
        try:
            return json.loads(stored_value)
        except (json.JSONDecodeError, TypeError):
            return stored_value

    # ── Core operations ──

    def get(self, key: str, default: Any = None) -> Any:
        with sync_session_factory() as session:
            obj = session.get(ConfigItem, key)
            if obj is None:
                return default
            return self._deserialize(obj.value, obj.value_type, obj.encrypted)

    def set(self, key: str, value: Any) -> None:
        stored, vtype, encrypted = self._serialize(key, value)
        with sync_session_factory() as session:
            obj = session.get(ConfigItem, key)
            if obj is None:
                obj = ConfigItem(key=key, value=stored, value_type=vtype, encrypted=encrypted, updated_at=utc_now())
                session.add(obj)
            else:
                obj.value = stored
                obj.value_type = vtype
                obj.encrypted = encrypted
                obj.updated_at = utc_now()
            session.commit()

    def delete(self, key: str) -> bool:
        with sync_session_factory() as session:
            obj = session.get(ConfigItem, key)
            if obj is None:
                return False
            session.delete(obj)
            session.commit()
            return True

    def delete_namespace(self, prefix: str) -> int:
        with sync_session_factory() as session:
            objs = session.execute(select(ConfigItem).where(ConfigItem.key.like(f"{prefix}%"))).scalars().all()
            for obj in objs:
                session.delete(obj)
            session.commit()
            return len(objs)

    def get_namespace(self, prefix: str) -> dict[str, Any]:
        with sync_session_factory() as session:
            objs = session.execute(select(ConfigItem).where(ConfigItem.key.like(f"{prefix}%"))).scalars().all()
            return {obj.key: self._deserialize(obj.value, obj.value_type, obj.encrypted) for obj in objs}

    def list_all(self) -> dict[str, Any]:
        with sync_session_factory() as session:
            objs = session.execute(select(ConfigItem)).scalars().all()
            result = {}
            for obj in objs:
                if obj.encrypted:
                    result[obj.key] = "***" if obj.value else ""
                else:
                    result[obj.key] = self._deserialize(obj.value, obj.value_type, obj.encrypted)
            return result

    def clear(self) -> None:
        with sync_session_factory() as session:
            session.execute(sa_delete(ConfigItem))
            session.commit()

    def invalidate(self) -> None:
        """SQL 始终读取最新数据，此方法为兼容保留。"""
        pass

    # ── Async wrappers ──

    async def get_async(self, key: str, default: Any = None) -> Any:
        return await asyncio.to_thread(self.get, key, default)

    async def set_async(self, key: str, value: Any) -> None:
        await asyncio.to_thread(self.set, key, value)

    async def delete_async(self, key: str) -> bool:
        return await asyncio.to_thread(self.delete, key)

    async def delete_namespace_async(self, prefix: str) -> int:
        return await asyncio.to_thread(self.delete_namespace, prefix)

    async def get_namespace_async(self, prefix: str) -> dict[str, Any]:
        return await asyncio.to_thread(self.get_namespace, prefix)

    async def list_all_async(self) -> dict[str, Any]:
        return await asyncio.to_thread(self.list_all)
