"""add transaction category

Revision ID: 20260514_0007
Revises: 20260514_0006
Create Date: 2026-05-14 22:20:00

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260514_0007"
down_revision = "20260514_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("transactions", sa.Column("category", sa.String(length=80), nullable=True))


def downgrade() -> None:
    op.drop_column("transactions", "category")
