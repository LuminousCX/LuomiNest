"""ProviderRepository + ProviderCredentialRepository — LLM 供应商元信息 + 凭证仓储。

- ProviderRepository: 供应商元信息（不含 api_key），支持排序/默认查询
- ProviderCredentialRepository: 凭证（api_key 加密存储 + 前缀显示 + SHA-256 查重）

加密复用 get_cipher()（LumiAesCipher / Fernet），与 config_items 旧数据同密钥。
"""
import asyncio
import hashlib
import uuid
from typing import Optional

from sqlalchemy import select
from loguru import logger

from app.infrastructure.database.models.provider import Provider
from app.infrastructure.database.models.provider_credential import ProviderCredential
from app.infrastructure.database.repositories.base import BaseRepository, orm_to_dict, utcnow_iso
from app.infrastructure.database.session import sync_session_factory
from app.security.crypto.aes_cipher import get_cipher


class ProviderRepository(BaseRepository):
    """供应商元信息仓储（不含 api_key）。"""

    model = Provider
    pk = "id"

    def get_all_ordered(self) -> list[dict]:
        """按 sort_order → created_at 排序返回所有 provider。"""
        with sync_session_factory() as session:
            objs = session.execute(
                select(Provider).order_by(Provider.sort_order, Provider.created_at)
            ).scalars().all()
            return [orm_to_dict(o) for o in objs]

    def get_default(self) -> Optional[dict]:
        """返回 is_default=True 的 provider。"""
        with sync_session_factory() as session:
            obj = session.execute(
                select(Provider).where(Provider.is_default == True)  # noqa: E712
            ).scalars().first()
            return orm_to_dict(obj) if obj else None

    # ── Async wrappers ──

    async def get_all_ordered_async(self) -> list[dict]:
        return await asyncio.to_thread(self.get_all_ordered)

    async def get_default_async(self) -> Optional[dict]:
        return await asyncio.to_thread(self.get_default)


class ProviderCredentialRepository(BaseRepository):
    """供应商凭证仓储（api_key 加密存储 + 前缀 + hash 查重）。"""

    model = ProviderCredential
    pk = "id"

    # ── Helpers ──

    @staticmethod
    def _compute_prefix(api_key: str) -> str:
        """前6+...+后4（短 key 仅显示前4+...）。"""
        if len(api_key) > 10:
            return api_key[:6] + "..." + api_key[-4:]
        return api_key[:4] + "..."

    @staticmethod
    def _compute_hash(api_key: str) -> str:
        """SHA-256 查重 hash。"""
        return hashlib.sha256(api_key.encode("utf-8")).hexdigest()

    @staticmethod
    def _encrypt(api_key: str) -> str:
        """Fernet 加密 api_key。"""
        cipher = get_cipher()
        return cipher.encrypt(api_key)

    @staticmethod
    def _decrypt(encrypted: str) -> str:
        """Fernet 解密 api_key，失败返回空字符串。"""
        if not encrypted:
            return ""
        cipher = get_cipher()
        return cipher.decrypt(encrypted)

    # ── Core operations ──

    def save_credential(self, provider_id: str, api_key: str, label: str = "") -> dict:
        """加密 + 查重 + upsert。若同 hash 已存在则更新。

        返回保存后的凭证 dict（含 api_key 明文，供调用方使用）。
        """
        key_hash = self._compute_hash(api_key)
        encrypted = self._encrypt(api_key)
        prefix = self._compute_prefix(api_key)
        now = utcnow_iso()

        with sync_session_factory() as session:
            existing = session.execute(
                select(ProviderCredential).where(ProviderCredential.api_key_hash == key_hash)
            ).scalars().first()

            if existing is not None:
                existing.provider_id = provider_id
                existing.api_key_encrypted = encrypted
                existing.api_key_prefix = prefix
                existing.label = label
                existing.is_active = True
                existing.last_used_at = existing.last_used_at or ""
                session.commit()
                session.refresh(existing)
                data = orm_to_dict(existing)
            else:
                cred_id = uuid.uuid4().hex
                cred = ProviderCredential(
                    id=cred_id,
                    provider_id=provider_id,
                    api_key_encrypted=encrypted,
                    api_key_prefix=prefix,
                    api_key_hash=key_hash,
                    label=label,
                    is_active=True,
                    last_used_at="",
                    created_at=now,
                )
                session.add(cred)
                session.commit()
                session.refresh(cred)
                data = orm_to_dict(cred)

            data["api_key"] = api_key
            logger.debug(f"[ProviderCred] Saved credential for provider={provider_id}, prefix={prefix}")
            return data

    def get_active_credential(self, provider_id: str) -> Optional[dict]:
        """返回 provider 的活跃凭证（解密 api_key）。"""
        with sync_session_factory() as session:
            obj = session.execute(
                select(ProviderCredential)
                .where(ProviderCredential.provider_id == provider_id)
                .where(ProviderCredential.is_active == True)  # noqa: E712
                .order_by(ProviderCredential.created_at)
            ).scalars().first()
            if obj is None:
                return None
            data = orm_to_dict(obj)
            data["api_key"] = self._decrypt(data.get("api_key_encrypted", ""))
            return data

    def list_credentials(self, provider_id: str) -> list[dict]:
        """返回 provider 的所有凭证（不返回密文/明文，仅 prefix）。"""
        with sync_session_factory() as session:
            objs = session.execute(
                select(ProviderCredential)
                .where(ProviderCredential.provider_id == provider_id)
                .order_by(ProviderCredential.created_at)
            ).scalars().all()
            result = []
            for obj in objs:
                d = orm_to_dict(obj)
                d.pop("api_key_encrypted", None)
                result.append(d)
            return result

    def delete_credential(self, credential_id: str) -> bool:
        return self.delete(credential_id)

    def find_by_hash(self, api_key_hash: str) -> Optional[dict]:
        """按 hash 查重（防同一 key 重复添加）。"""
        with sync_session_factory() as session:
            obj = session.execute(
                select(ProviderCredential).where(ProviderCredential.api_key_hash == api_key_hash)
            ).scalars().first()
            return orm_to_dict(obj) if obj else None

    def find_by_api_key(self, api_key: str) -> Optional[dict]:
        """便捷方法：直接用 api_key 明文查重。"""
        return self.find_by_hash(self._compute_hash(api_key))

    def update_last_used(self, credential_id: str) -> None:
        """更新凭证最后使用时间。"""
        with sync_session_factory() as session:
            obj = session.get(ProviderCredential, credential_id)
            if obj is not None:
                obj.last_used_at = utcnow_iso()
                session.commit()

    def delete_by_provider(self, provider_id: str) -> int:
        """删除 provider 的所有凭证，返回删除数量。"""
        with sync_session_factory() as session:
            objs = session.execute(
                select(ProviderCredential).where(ProviderCredential.provider_id == provider_id)
            ).scalars().all()
            count = len(objs)
            for obj in objs:
                session.delete(obj)
            session.commit()
            return count

    # ── Async wrappers ──

    async def save_credential_async(self, provider_id: str, api_key: str, label: str = "") -> dict:
        return await asyncio.to_thread(self.save_credential, provider_id, api_key, label)

    async def get_active_credential_async(self, provider_id: str) -> Optional[dict]:
        return await asyncio.to_thread(self.get_active_credential, provider_id)

    async def list_credentials_async(self, provider_id: str) -> list[dict]:
        return await asyncio.to_thread(self.list_credentials, provider_id)

    async def delete_credential_async(self, credential_id: str) -> bool:
        return await asyncio.to_thread(self.delete_credential, credential_id)

    async def find_by_hash_async(self, api_key_hash: str) -> Optional[dict]:
        return await asyncio.to_thread(self.find_by_hash, api_key_hash)

    async def find_by_api_key_async(self, api_key: str) -> Optional[dict]:
        return await asyncio.to_thread(self.find_by_api_key, api_key)

    async def update_last_used_async(self, credential_id: str) -> None:
        await asyncio.to_thread(self.update_last_used, credential_id)

    async def delete_by_provider_async(self, provider_id: str) -> int:
        return await asyncio.to_thread(self.delete_by_provider, provider_id)
