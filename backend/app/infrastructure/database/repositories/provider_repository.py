"""ProviderRepository — LLM 供应商配置（替代 llm.providers.* 命名空间）。

api_key 始终加密存储（非可选加密）。
"""
import asyncio
from typing import Optional

from sqlalchemy import select
from loguru import logger

from app.infrastructure.database.models.provider import Provider
from app.infrastructure.database.repositories.base import BaseRepository, orm_to_dict, utcnow_iso
from app.infrastructure.database.session import sync_session_factory
from app.security.crypto.aes_cipher import get_cipher


class ProviderRepository(BaseRepository):
    model = Provider
    pk = "id"

    def _encrypt_api_key(self, data: dict) -> dict:
        """加密 api_key（写前调用）。"""
        api_key = data.get("api_key")
        if api_key and isinstance(api_key, str):
            cipher = get_cipher()
            data["api_key"] = cipher.encrypt(api_key)
        return data

    def _decrypt_api_key(self, data: dict) -> dict:
        """解密 api_key（读后调用）。"""
        if not data:
            return data
        api_key = data.get("api_key")
        if api_key and isinstance(api_key, str):
            cipher = get_cipher()
            decrypted = cipher.decrypt(api_key)
            if decrypted:
                data["api_key"] = decrypted
        return data

    # ── Override to handle api_key encryption ──

    def get(self, key: str) -> Optional[dict]:
        data = super().get(key)
        return self._decrypt_api_key(data) if data else None

    def get_all(self) -> list[dict]:
        items = super().get_all()
        return [self._decrypt_api_key(d) for d in items]

    def save(self, key: str, data: dict) -> dict:
        encrypted_data = self._encrypt_api_key(dict(data))
        result = super().save(key, encrypted_data)
        return self._decrypt_api_key(result)

    def get_default(self) -> Optional[dict]:
        with sync_session_factory() as session:
            obj = session.execute(select(Provider).where(Provider.is_default == True)).scalars().first()
            data = orm_to_dict(obj) if obj else None
            return self._decrypt_api_key(data) if data else None

    # ── Async wrappers ──

    async def get_async(self, key: str) -> Optional[dict]:
        return await asyncio.to_thread(self.get, key)

    async def get_all_async(self) -> list[dict]:
        return await asyncio.to_thread(self.get_all)

    async def save_async(self, key: str, data: dict) -> dict:
        return await asyncio.to_thread(self.save, key, data)

    async def get_default_async(self) -> Optional[dict]:
        return await asyncio.to_thread(self.get_default)
