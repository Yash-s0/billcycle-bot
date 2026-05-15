"""add user reminder preferences

Revision ID: 20260515_0010
Revises: 20260515_0009
Create Date: 2026-05-15 20:15:00

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260515_0010"
down_revision = "20260515_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("reminders_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "users",
        sa.Column("reminder_time", sa.Time(), nullable=False, server_default="09:00:00"),
    )


def downgrade() -> None:
    op.drop_column("users", "reminder_time")
    op.drop_column("users", "reminders_enabled")
