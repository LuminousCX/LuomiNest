"""PlatformRepository — 平台实例（替代 platforms.json）。

config JSON 列含适配器凭据（P1-6）：写入前对凭据类字段 AES 加密
（enc:v1: 前缀标记，复用 get_cipher() 与 SECRET_KEY 体系），读出后解密——
对本仓储的所有调用方（registry/端点/迁移器）透明，拿到的仍是明文 dict，
适配器契约不变。加密字段判定与迁移见 platform_config_crypto。
"""
from typing import Callable, Optional

from app.infrastructure.database.models.platform_instance import PlatformInstance
from app.infrastructure.database.repositories.base import BaseRepository
from app.infrastructure.database.session import sync_session_factory
from app.security.crypto.platform_config_crypto import decrypt_config, encrypt_config


class PlatformRepository(BaseRepository):
    model = PlatformInstance
    pk = "id"

    # ── config 凭据字段加解密（P1-6：落库密文、出库明文）──

    @staticmethod
    def _transform_row_config(data: Optional[dict], transform) -> Optional[dict]:
        """对行 dict 的 config 字段应用 transform（非 dict config 原样返回）。"""
        if data and isinstance(data.get("config"), dict):
            return {**data, "config": transform(data["config"])}
        return data

    @classmethod
    def _encrypt_row(cls, data: Optional[dict]) -> Optional[dict]:
        return cls._transform_row_config(data, encrypt_config)

    @classmethod
    def _decrypt_row(cls, data: Optional[dict]) -> Optional[dict]:
        return cls._transform_row_config(data, decrypt_config)

    # ── Read（返回明文 config，调用方语义与加密前一致）──

    def get(self, key: str) -> Optional[dict]:
        return self._decrypt_row(super().get(key))

    def get_all(self) -> list[dict]:
        return [self._decrypt_row(d) for d in super().get_all()]

    # ── Write（config 凭据字段加密落库；返回值仍解密为明文）──

    def save(self, key: str, data: dict) -> dict:
        return self._decrypt_row(super().save(key, self._encrypt_row(data)))

    def update(self, key: str, updates: dict) -> Optional[dict]:
        return self._decrypt_row(super().update(key, self._encrypt_row(updates)))

    def mutate(self, key: str, updater_fn: Callable) -> Optional[dict]:
        """updater_fn 收到/返回的都是明文 config 的行 dict（加密仅发生在落库时）。"""

        def _wrapped(current: Optional[dict]) -> Optional[dict]:
            new_value = updater_fn(self._decrypt_row(current))
            if new_value is None:
                return None
            return self._encrypt_row(new_value)

        return self._decrypt_row(super().mutate(key, _wrapped))

    # ── 存量明文凭据迁移（P1-6，启动钩子调用）──

    def migrate_plaintext_credentials(self) -> int:
        """把存量行中明文形态的凭据字段加密重写（幂等，返回重写行数）。

        判定依据可靠：encrypt_config 仅对不带 enc:v1: 前缀的非空凭据值加密，
        已加密行加密前后内容一致即跳过，重复调用为零写入。
        """
        migrated = 0
        for row in super().get_all():
            config = row.get("config")
            if not isinstance(config, dict):
                continue
            encrypted = encrypt_config(config)
            if encrypted == config:
                continue
            with sync_session_factory() as session:
                obj = session.get(self.model, row[self.pk])
                if obj is not None:
                    obj.config = encrypted
                    session.commit()
            migrated += 1
        return migrated
