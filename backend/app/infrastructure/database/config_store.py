import asyncio
import fnmatch
import json
import os
import threading
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from app.core.config import settings
from app.security.crypto.aes_cipher import get_cipher


class LumiConfigStore:
    """统一用户配置存储。

    提供命名空间隔离的 key-value 配置管理，
    敏感字段（标记为 encrypted=True）自动通过 AES 加密存储。
    所有写入操作使用原子写入，防止数据损坏。
    """

    ENCRYPTED_KEYS: set[str] = {
        "llm.api_key",
        "llm.providers.*.api_key",
        "system.secret_key",
    }

    def __init__(self):
        self._dir = os.path.join(settings.DATA_DIR, "config")
        os.makedirs(self._dir, exist_ok=True)
        self._path = os.path.join(self._dir, "user_config.json")
        self._lock = threading.Lock()
        self._cache: dict[str, Any] | None = None

    def _load(self) -> dict[str, Any]:
        if self._cache is not None:
            return self._cache
        if not os.path.exists(self._path):
            self._cache = {}
            return self._cache
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                self._cache = json.load(f)
                return self._cache
        except Exception as e:
            logger.warning(f"[ConfigStore] Failed to load {self._path}: {e}")
            self._cache = {}
            return self._cache

    def _save(self):
        """原子写入。"""
        tmp_path = self._path + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self._path)
        except Exception as e:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError as cleanup_error:
                    logger.warning(
                        f"[ConfigStore] Failed to remove temp file {tmp_path}: {cleanup_error}"
                    )
            logger.error(f"[ConfigStore] Failed to save {self._path}: {e}")

    def _is_encrypted_key(self, key: str) -> bool:
        """判断某个 key 是否需要加密存储。"""
        for pattern in self.ENCRYPTED_KEYS:
            if fnmatch.fnmatch(key, pattern):
                return True
        return False

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值，自动解密敏感字段。"""
        with self._lock:
            value = self._load().get(key, default)
        if value is None:
            return default
        if self._is_encrypted_key(key) and isinstance(value, str) and value:
            cipher = get_cipher()
            decrypted = cipher.decrypt(value)
            return decrypted if decrypted else value
        return value

    def set(self, key: str, value: Any) -> None:
        """设置配置值，自动加密敏感字段。"""
        with self._lock:
            data = self._load()
            if self._is_encrypted_key(key) and isinstance(value, str) and value:
                cipher = get_cipher()
                value = cipher.encrypt(value)
            data[key] = value
            data[f"{key}__updated_at"] = datetime.now(timezone.utc).isoformat()
            self._save()

    def delete(self, key: str) -> bool:
        """删除配置项。"""
        with self._lock:
            data = self._load()
            if key not in data:
                return False
            del data[key]
            data.pop(f"{key}__updated_at", None)
            self._save()
            return True

    def delete_namespace(self, prefix: str) -> int:
        """删除某个命名空间下所有配置，返回删除数量。"""
        with self._lock:
            data = self._load()
            keys_to_delete = [k for k in data if k.startswith(prefix)]
            for key in keys_to_delete:
                del data[key]
            if keys_to_delete:
                self._save()
            return len(keys_to_delete)

    def get_namespace(self, prefix: str) -> dict[str, Any]:
        """获取某个命名空间下所有配置（自动解密）。"""
        with self._lock:
            data = self._load()
        result = {}
        for key, value in data.items():
            if key.startswith(prefix) and not key.endswith("__updated_at"):
                if self._is_encrypted_key(key) and isinstance(value, str) and value:
                    cipher = get_cipher()
                    decrypted = cipher.decrypt(value)
                    result[key] = decrypted if decrypted else value
                else:
                    result[key] = value
        return result

    def list_all(self) -> dict[str, Any]:
        """列出所有配置（敏感字段返回是否存在，不返回明文）。"""
        with self._lock:
            data = self._load()
        result = {}
        for key, value in data.items():
            if key.endswith("__updated_at"):
                continue
            if self._is_encrypted_key(key):
                result[key] = "***" if value else ""
            else:
                result[key] = value
        return result

    def clear(self) -> None:
        """清空所有配置。"""
        with self._lock:
            self._cache = {}
            self._save()

    def invalidate(self) -> None:
        """清除内存缓存，下次读取时从磁盘重新加载。"""
        self._cache = None

    # ── Async wrappers ──

    async def get_async(self, key: str, default: Any = None) -> Any:
        return await asyncio.to_thread(self.get, key, default)

    async def set_async(self, key: str, value: Any) -> None:
        await asyncio.to_thread(self.set, key, value)

    async def delete_async(self, key: str) -> bool:
        return await asyncio.to_thread(self.delete, key)

    async def get_namespace_async(self, prefix: str) -> dict[str, Any]:
        return await asyncio.to_thread(self.get_namespace, prefix)

    async def list_all_async(self) -> dict[str, Any]:
        return await asyncio.to_thread(self.list_all)


lumi_config_store = LumiConfigStore()
