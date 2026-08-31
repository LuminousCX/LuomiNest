"""provider_protocol_column

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-08-15 16:40:00.000000

改动：
1. providers 表新增 protocol 列（接入协议：auto | chat_completions | anthropic_messages）。

背景：ORM 模型（app/infrastructure/database/models/provider.py）与运行时
engine.py 的列迁移兜底均已包含 protocol 列，但 Alembic 迁移链缺失该步骤，
导致纯 Alembic 升级路径（scripts/migrate）升级后的库缺少此列，ORM 查询报
"no such column: providers.protocol"。本迁移补齐迁移链与模型的偏差。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('providers', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('protocol', sa.String(length=32), nullable=False, server_default='auto')
        )


def downgrade() -> None:
    with op.batch_alter_table('providers', schema=None) as batch_op:
        batch_op.drop_column('protocol')
