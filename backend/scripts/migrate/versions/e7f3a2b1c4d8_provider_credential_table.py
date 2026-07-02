"""provider_credential_table

Revision ID: e7f3a2b1c4d8
Revises: cb814021f0d2
Create Date: 2026-07-01 20:00:00.000000

改动：
1. providers 表：删除 api_key 列，新增 enabled / sort_order 列
2. 新建 provider_credentials 表（加密 key + 前缀 + hash 查重）
3. 数据迁移：config_items 中 llm.providers.* 命名空间 → providers + provider_credentials
"""
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'e7f3a2b1c4d8'
down_revision: Union[str, None] = 'cb814021f0d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PROVIDER_NAMESPACE = "llm.providers."
MIGRATION_SOURCE = "providers_config"


def upgrade() -> None:
    # ── 1. providers 表：删除 api_key，新增 enabled / sort_order ──
    with op.batch_alter_table('providers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.text('1')))
        batch_op.add_column(sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'))
        batch_op.drop_column('api_key')

    # ── 2. provider_credentials 表 ──
    op.create_table('provider_credentials',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('provider_id', sa.String(length=128), nullable=False),
        sa.Column('api_key_encrypted', sa.Text(), nullable=False),
        sa.Column('api_key_prefix', sa.String(length=32), nullable=False),
        sa.Column('api_key_hash', sa.String(length=64), nullable=False),
        sa.Column('label', sa.String(length=128), nullable=False, server_default=''),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('last_used_at', sa.String(length=64), nullable=False, server_default=''),
        sa.Column('created_at', sa.String(length=64), nullable=False, server_default=''),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('provider_credentials', schema=None) as batch_op:
        batch_op.create_index('ix_provider_credentials_provider_id', ['provider_id'], unique=False)
        batch_op.create_index('ix_provider_credentials_api_key_hash', ['api_key_hash'], unique=False)

    # ── 3. 数据迁移：config_items → providers + provider_credentials ──
    _migrate_provider_data()


def _migrate_provider_data() -> None:
    """从 config_items 的 llm.providers.* 命名空间迁移到 providers + provider_credentials 表。

    幂等：通过 _migration_meta 表的 providers_config 标记防止重复迁移。
    """
    bind = op.get_bind()

    # 幂等检查
    existing = bind.execute(text(
        "SELECT source FROM _migration_meta WHERE source = :source"
    ), {"source": MIGRATION_SOURCE}).fetchone()
    if existing is not None:
        return

    # 读取 config_items 中所有 llm.providers.* 记录
    rows = bind.execute(text(
        "SELECT key, value, value_type, encrypted FROM config_items WHERE key LIKE :prefix"
    ), {"prefix": PROVIDER_NAMESPACE + "%"}).fetchall()

    now = datetime.now(timezone.utc).isoformat()

    if not rows:
        bind.execute(text(
            "INSERT INTO _migration_meta (source, migrated_at, record_count) VALUES (:source, :ts, 0)"
        ), {"source": MIGRATION_SOURCE, "ts": now})
        return

    # 按 provider_id 分组，还原每个 provider 的完整配置
    providers_data: dict[str, dict] = {}
    for row in rows:
        key, value, value_type, encrypted = row
        rest = key[len(PROVIDER_NAMESPACE):]
        if "." not in rest:
            continue
        provider_id, field = rest.split(".", 1)
        if provider_id not in providers_data:
            providers_data[provider_id] = {"id": provider_id}

        if encrypted:
            from app.security.crypto.aes_cipher import get_cipher
            cipher = get_cipher()
            val = cipher.decrypt(value)
        else:
            try:
                val = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                val = value
        providers_data[provider_id][field] = val

    # 插入 providers + provider_credentials
    from app.security.crypto.aes_cipher import get_cipher
    cipher = get_cipher()
    provider_count = 0

    for provider_id, cfg in providers_data.items():
        api_key = cfg.pop("api_key", "")

        # 插入 providers 表（不含 api_key）
        bind.execute(text(
            "INSERT INTO providers (id, name, vendor, base_url, default_model, is_default, "
            "selected_models, enabled, sort_order, created_at, updated_at) "
            "VALUES (:id, :name, :vendor, :base_url, :default_model, :is_default, "
            ":selected_models, :enabled, :sort_order, :created_at, :updated_at)"
        ), {
            "id": provider_id,
            "name": cfg.get("name", ""),
            "vendor": cfg.get("vendor", "openai_compatible"),
            "base_url": cfg.get("base_url", ""),
            "default_model": cfg.get("default_model", ""),
            "is_default": 1 if cfg.get("is_default", False) else 0,
            "selected_models": json.dumps(cfg.get("selected_models", []), ensure_ascii=False),
            "enabled": 1,
            "sort_order": 0,
            "created_at": cfg.get("created_at", now),
            "updated_at": now,
        })
        provider_count += 1

        # 若有 api_key，插入 provider_credentials
        if api_key:
            prefix = _compute_prefix(api_key)
            key_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
            cred_id = uuid.uuid4().hex
            encrypted_key = cipher.encrypt(api_key)

            bind.execute(text(
                "INSERT INTO provider_credentials "
                "(id, provider_id, api_key_encrypted, api_key_prefix, api_key_hash, "
                "label, is_active, last_used_at, created_at) "
                "VALUES (:id, :provider_id, :enc, :prefix, :hash, :label, 1, '', :created_at)"
            ), {
                "id": cred_id,
                "provider_id": provider_id,
                "enc": encrypted_key,
                "prefix": prefix,
                "hash": key_hash,
                "label": "",
                "created_at": now,
            })

    # 删除 config_items 中 llm.providers.* 记录
    bind.execute(text(
        "DELETE FROM config_items WHERE key LIKE :prefix"
    ), {"prefix": PROVIDER_NAMESPACE + "%"})

    # 标记迁移完成
    bind.execute(text(
        "INSERT INTO _migration_meta (source, migrated_at, record_count) "
        "VALUES (:source, :ts, :count)"
    ), {"source": MIGRATION_SOURCE, "ts": now, "count": provider_count})


def _compute_prefix(api_key: str) -> str:
    """生成 api_key 前缀：前6+...+后4（短 key 仅显示前4+...）。"""
    if len(api_key) > 10:
        return api_key[:6] + "..." + api_key[-4:]
    return api_key[:4] + "..."


def downgrade() -> None:
    # 删除 provider_credentials 表
    with op.batch_alter_table('provider_credentials', schema=None) as batch_op:
        batch_op.drop_index('ix_provider_credentials_api_key_hash')
        batch_op.drop_index('ix_provider_credentials_provider_id')
    op.drop_table('provider_credentials')

    # providers 表：恢复 api_key 列，删除 enabled / sort_order
    with op.batch_alter_table('providers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('api_key', sa.String(length=1024), nullable=False, server_default=''))
        batch_op.drop_column('sort_order')
        batch_op.drop_column('enabled')

    # 注意：数据迁移不可逆（config_items 中 llm.providers.* 已删除）
