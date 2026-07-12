"""nota_variante_a_text

Revision ID: a1f2c3d4e5f6
Revises: 0dab78dd88ac
Create Date: 2026-07-12

Cambia serie_variantes.nota de String(300) a Text para permitir
notas largas por variante.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1f2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '0dab78dd88ac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('serie_variantes', 'nota',
                    existing_type=sa.String(length=300),
                    type_=sa.Text(),
                    existing_nullable=True)


def downgrade() -> None:
    op.alter_column('serie_variantes', 'nota',
                    existing_type=sa.Text(),
                    type_=sa.String(length=300),
                    existing_nullable=True)
