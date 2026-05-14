"""remove cards.last_four

Revision ID: 20260514_0004
Revises: 20260514_0003
Create Date: 2026-05-14 00:10:00

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260514_0004"
down_revision = "20260514_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("cards", "last_four")


def downgrade() -> None:
    op.add_column("cards", sa.Column("last_four", sa.String(length=4), nullable=True))
