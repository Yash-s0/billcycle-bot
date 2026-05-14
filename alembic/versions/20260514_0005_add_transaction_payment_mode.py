"""add transaction payment mode and optional card for non-card spends

Revision ID: 20260514_0005
Revises: 20260514_0004
Create Date: 2026-05-14 00:30:00

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260514_0005"
down_revision = "20260514_0004"
branch_labels = None
depends_on = None


payment_mode = sa.Enum(
    "card",
    "upi",
    "cash",
    name="paymentmode",
    native_enum=False,
)


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("payment_mode", payment_mode, nullable=False, server_default="card"),
    )
    op.execute(sa.text("UPDATE transactions SET payment_mode = 'card' WHERE payment_mode IS NULL"))
    op.alter_column("transactions", "payment_mode", server_default=None)
    op.alter_column("transactions", "card_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    # Non-card transactions cannot be represented after downgrade because card_id becomes mandatory.
    op.execute(sa.text("DELETE FROM transactions WHERE payment_mode <> 'card' OR card_id IS NULL"))
    op.alter_column("transactions", "card_id", existing_type=sa.Integer(), nullable=False)
    op.drop_column("transactions", "payment_mode")
