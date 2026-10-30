"""precios_bs_y_fecha

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-10-30

Los precios de series pueden cargarse en Bs: se guarda el monto original y la
tasa usada además del equivalente en US$. Los precios sin fecha toman la de
carga, para poder comparar por período.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('serie_precios', sa.Column('monto_original', sa.Numeric(12, 2), nullable=True))
    op.add_column('serie_precios', sa.Column('tasa', sa.Numeric(10, 4), nullable=True))
    op.execute("UPDATE serie_precios SET fecha = COALESCE(created_at::date, CURRENT_DATE) WHERE fecha IS NULL")


def downgrade() -> None:
    op.drop_column('serie_precios', 'tasa')
    op.drop_column('serie_precios', 'monto_original')
