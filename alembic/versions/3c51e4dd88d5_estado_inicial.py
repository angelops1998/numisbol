"""estado_inicial

Revision ID: 3c51e4dd88d5
Revises:
Create Date: 2026-06-13

Baseline: la base de datos ya existía antes de configurar Alembic.
Esta migración no hace nada — solo marca el punto de partida.
"""
from typing import Sequence, Union

revision: str = '3c51e4dd88d5'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
