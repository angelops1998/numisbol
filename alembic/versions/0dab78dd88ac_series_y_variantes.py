"""series_y_variantes

Revision ID: 0dab78dd88ac
Revises: 3c51e4dd88d5
Create Date: 2026-07-03

Crea el catálogo de series numismáticas y sus variantes,
y vincula las monedas de la colección a una variante.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0dab78dd88ac'
down_revision: Union[str, Sequence[str], None] = '3c51e4dd88d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('series',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nombre', sa.String(length=200), nullable=False),
        sa.Column('descripcion', sa.Text(), nullable=True),
        sa.Column('activo', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('nombre'),
    )
    op.create_index(op.f('ix_series_id'), 'series', ['id'], unique=False)

    op.create_table('serie_variantes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('serie_id', sa.Integer(), nullable=False),
        sa.Column('anio', sa.Integer(), nullable=True),
        sa.Column('ensayador', sa.String(length=100), nullable=True),
        sa.Column('ceca', sa.String(length=100), nullable=True),
        sa.Column('mintage', sa.String(length=50), nullable=True),
        sa.Column('nota', sa.String(length=300), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['serie_id'], ['series.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_serie_variantes_id'), 'serie_variantes', ['id'], unique=False)
    op.create_index(op.f('ix_serie_variantes_serie_id'), 'serie_variantes', ['serie_id'], unique=False)

    op.add_column('coins', sa.Column('variante_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_coins_variante_id'), 'coins', ['variante_id'], unique=False)
    op.create_foreign_key('fk_coins_variante_id', 'coins', 'serie_variantes',
                          ['variante_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint('fk_coins_variante_id', 'coins', type_='foreignkey')
    op.drop_index(op.f('ix_coins_variante_id'), table_name='coins')
    op.drop_column('coins', 'variante_id')
    op.drop_index(op.f('ix_serie_variantes_serie_id'), table_name='serie_variantes')
    op.drop_index(op.f('ix_serie_variantes_id'), table_name='serie_variantes')
    op.drop_table('serie_variantes')
    op.drop_index(op.f('ix_series_id'), table_name='series')
    op.drop_table('series')
