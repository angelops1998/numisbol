"""orden_serie

Revision ID: b2c3d4e5f6a7
Revises: a1f2c3d4e5f6
Create Date: 2026-07-16

Agrega series.orden (entero, default 100) para permitir ordenar
manualmente las series en /coleccion/series desde el admin.
Preserva el orden manual ya definido en código para las primeras
tres series destacadas.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1f2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('series', sa.Column('orden', sa.Integer(), nullable=False, server_default='100'))

    series = sa.table('series', sa.column('id', sa.Integer), sa.column('nombre', sa.String), sa.column('orden', sa.Integer))
    conn = op.get_bind()
    conn.execute(series.update().where(series.c.nombre.ilike('%Reales Bolivianos 1825%')).values(orden=0))
    conn.execute(series.update().where(series.c.nombre.ilike('%8 Soles 1827%1840%')).values(orden=1))
    conn.execute(series.update().where(series.c.nombre.ilike('%4 Soles 1827%1829%')).values(orden=2))


def downgrade() -> None:
    op.drop_column('series', 'orden')
