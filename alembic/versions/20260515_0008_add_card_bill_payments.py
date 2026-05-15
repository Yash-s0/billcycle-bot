"""add card bill payments table

Revision ID: 20260515_0008
Revises: 20260514_0007
Create Date: 2026-05-15 18:10:00

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260515_0008"
down_revision = "20260514_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "card_bill_payments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("card_id", sa.Integer(), nullable=False),
        sa.Column("cycle_start", sa.Date(), nullable=False),
        sa.Column("cycle_end", sa.Date(), nullable=False),
        sa.Column("amount_paid", sa.Numeric(12, 2), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["card_id"], ["cards.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_card_bill_payments_user_id", "card_bill_payments", ["user_id"], unique=False)
    op.create_index("ix_card_bill_payments_card_id", "card_bill_payments", ["card_id"], unique=False)
    op.create_index("ix_card_bill_payments_cycle_start", "card_bill_payments", ["cycle_start"], unique=False)
    op.create_index("ix_card_bill_payments_cycle_end", "card_bill_payments", ["cycle_end"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_card_bill_payments_cycle_end", table_name="card_bill_payments")
    op.drop_index("ix_card_bill_payments_cycle_start", table_name="card_bill_payments")
    op.drop_index("ix_card_bill_payments_card_id", table_name="card_bill_payments")
    op.drop_index("ix_card_bill_payments_user_id", table_name="card_bill_payments")
    op.drop_table("card_bill_payments")
