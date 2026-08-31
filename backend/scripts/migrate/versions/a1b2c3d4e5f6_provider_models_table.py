"""provider_models_table

Revision ID: a1b2c3d4e5f6
Revises: e7f3a2b1c4d8
Create Date: 2026-08-12 10:00:00.000000

改动：
1. 新建 provider_models 表，用于持久化每个供应商返回的模型列表。
2. 支持按模型维度配置启用状态与最大上下文长度。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'e7f3a2b1c4d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('provider_models',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('provider_id', sa.String(length=128), nullable=False),
        sa.Column('model_id', sa.String(length=256), nullable=False),
        sa.Column('name', sa.String(length=256), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('max_context_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.String(length=64), nullable=False, server_default=''),
        sa.Column('updated_at', sa.String(length=64), nullable=False, server_default=''),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('provider_models', schema=None) as batch_op:
        batch_op.create_index('ix_provider_models_provider_id', ['provider_id'], unique=False)
        batch_op.create_index('ix_provider_models_model_id', ['model_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('provider_models', schema=None) as batch_op:
        batch_op.drop_index('ix_provider_models_model_id')
        batch_op.drop_index('ix_provider_models_provider_id')
    op.drop_table('provider_models')
