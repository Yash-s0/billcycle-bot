"""add cashback amount to transactions

Revision ID: 20260512_0002
Revises: 20260512_0001
Create Date: 2026-05-12 23:15:00

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260512_0002"
down_revision = "20260512_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("cashback_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("transactions", "cashback_amount")
