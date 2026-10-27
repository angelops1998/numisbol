"""todo_en_dolares

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-10-27

Todos los montos pasan a USD y se elimina el tipo de cambio. Los montos
existentes en BOB se convierten con la tasa que se guardó junto a cada fila
o, si no hay, con la última tasa de app_settings.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    row = conn.execute(sa.text("SELECT value FROM app_settings WHERE key = 'usd_bob_rate'")).first()
    rate = float(row[0]) if row and row[0] else 6.96
    p = {"r": rate}

    conn.execute(sa.text("""
        UPDATE coins SET estimated_value = ROUND(estimated_value / :r, 2)
        WHERE value_currency = 'BOB' AND estimated_value IS NOT NULL"""), p)
    conn.execute(sa.text("""
        UPDATE coins SET purchase_price = ROUND(purchase_price / COALESCE(NULLIF(purchase_usd_rate, 0), :r), 2)
        WHERE purchase_currency = 'BOB' AND purchase_price IS NOT NULL"""), p)
    conn.execute(sa.text("""
        UPDATE listings SET
            price = ROUND(price / COALESCE(NULLIF(usd_rate, 0), :r), 2),
            sale_price_actual = ROUND(sale_price_actual / COALESCE(NULLIF(usd_rate, 0), :r), 2)
        WHERE currency = 'BOB'"""), p)
    conn.execute(sa.text("""
        UPDATE listings SET cost = ROUND(cost / COALESCE(NULLIF(cost_usd_rate, 0), :r), 2)
        WHERE (cost_currency = 'BOB' OR cost_currency IS NULL) AND cost IS NOT NULL"""), p)
    conn.execute(sa.text("""
        UPDATE serie_precios SET monto = ROUND(monto / :r, 2) WHERE moneda = 'BOB'"""), p)

    conn.execute(sa.text("UPDATE coins SET value_currency = 'USD', purchase_currency = 'USD'"))
    conn.execute(sa.text("UPDATE listings SET currency = 'USD', cost_currency = 'USD'"))
    conn.execute(sa.text("UPDATE serie_precios SET moneda = 'USD'"))

    for tabla, col in (("coins", "value_currency"), ("coins", "purchase_currency")):
        op.alter_column(tabla, col, server_default='USD')
    op.alter_column("listings", "currency", server_default='USD')
    op.alter_column("listings", "cost_currency", server_default='USD')

    op.drop_column("coins", "purchase_usd_rate")
    op.drop_column("listings", "usd_rate")
    op.drop_column("listings", "cost_usd_rate")
    conn.execute(sa.text("DELETE FROM app_settings WHERE key LIKE 'usd_bob_rate%'"))


def downgrade() -> None:
    op.add_column("coins", sa.Column("purchase_usd_rate", sa.Numeric(10, 2), nullable=True))
    op.add_column("listings", sa.Column("usd_rate", sa.Numeric(10, 4), nullable=True))
    op.add_column("listings", sa.Column("cost_usd_rate", sa.Numeric(10, 4), nullable=True))
