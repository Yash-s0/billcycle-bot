"""remove merchant/category and keep notes

Revision ID: 20260514_0003
Revises: 20260512_0002
Create Date: 2026-05-14 00:00:00

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260514_0003"
down_revision = "20260512_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Preserve legacy data by backfilling notes from category/merchant when notes is empty.
    op.execute(
        sa.text(
            """
            UPDATE transactions
            SET notes = COALESCE(NULLIF(notes, ''), NULLIF(category, ''), NULLIF(merchant, ''))
            WHERE notes IS NULL OR notes = ''
            """
        )
    )

    op.drop_column("transactions", "category")
    op.drop_column("transactions", "merchant")


def downgrade() -> None:
    op.add_column("transactions", sa.Column("merchant", sa.String(length=255), nullable=True))
    op.add_column("transactions", sa.Column("category", sa.String(length=80), nullable=True))

    # Best-effort restore: map notes back to category for compatibility.
    op.execute(
        sa.text(
            """
            UPDATE transactions
            SET category = NULLIF(notes, '')
            WHERE category IS NULL AND notes IS NOT NULL
            """
        )
    )
