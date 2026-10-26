"""precios_series

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-10-25

Agrega la tabla serie_precios: precios de referencia que el admin ve
publicados en internet, por serie o por variante, para tener un estimativo.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'serie_precios',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('serie_id', sa.Integer(), nullable=False),
        sa.Column('variante_id', sa.Integer(), nullable=True),
        sa.Column('monto', sa.Numeric(12, 2), nullable=False),
        sa.Column('moneda', sa.String(length=3), server_default='USD', nullable=False),
        sa.Column('tipo', sa.String(length=10), server_default='oferta', nullable=False),
        sa.Column('estado', sa.String(length=30), nullable=True),
        sa.Column('fuente', sa.String(length=100), nullable=True),
        sa.Column('url', sa.String(length=500), nullable=True),
        sa.Column('fecha', sa.Date(), nullable=True),
        sa.Column('nota', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['serie_id'], ['series.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['variante_id'], ['serie_variantes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_serie_precios_id'), 'serie_precios', ['id'], unique=False)
    op.create_index(op.f('ix_serie_precios_serie_id'), 'serie_precios', ['serie_id'], unique=False)
    op.create_index(op.f('ix_serie_precios_variante_id'), 'serie_precios', ['variante_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_serie_precios_variante_id'), table_name='serie_precios')
    op.drop_index(op.f('ix_serie_precios_serie_id'), table_name='serie_precios')
    op.drop_index(op.f('ix_serie_precios_id'), table_name='serie_precios')
    op.drop_table('serie_precios')
