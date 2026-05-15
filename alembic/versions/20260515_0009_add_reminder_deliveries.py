"""add reminder deliveries table

Revision ID: 20260515_0009
Revises: 20260515_0008
Create Date: 2026-05-15 18:45:00

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260515_0009"
down_revision = "20260515_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reminder_deliveries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("reminder_date", sa.Date(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "reminder_date", name="uq_reminder_deliveries_user_date"),
    )
    op.create_index("ix_reminder_deliveries_user_id", "reminder_deliveries", ["user_id"], unique=False)
    op.create_index("ix_reminder_deliveries_reminder_date", "reminder_deliveries", ["reminder_date"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_reminder_deliveries_reminder_date", table_name="reminder_deliveries")
    op.drop_index("ix_reminder_deliveries_user_id", table_name="reminder_deliveries")
    op.drop_table("reminder_deliveries")
