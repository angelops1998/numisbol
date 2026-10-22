"""likes_monedas_publicas

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-10-22

Agrega la tabla coin_likes: un «me gusta» por usuario y por pieza.
La restricción única (coin_id, user_id) es la que impide el doble like,
y los índices sirven para contar likes por pieza y listar los de un usuario.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'coin_likes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('coin_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['coin_id'], ['coins.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('coin_id', 'user_id', name='uq_coin_likes_coin_user'),
    )
    op.create_index('ix_coin_likes_id', 'coin_likes', ['id'])
    op.create_index('ix_coin_likes_coin_id', 'coin_likes', ['coin_id'])
    op.create_index('ix_coin_likes_user_id', 'coin_likes', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_coin_likes_user_id', table_name='coin_likes')
    op.drop_index('ix_coin_likes_coin_id', table_name='coin_likes')
    op.drop_index('ix_coin_likes_id', table_name='coin_likes')
    op.drop_table('coin_likes')
