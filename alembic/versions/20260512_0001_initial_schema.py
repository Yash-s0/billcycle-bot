"""initial schema

Revision ID: 20260512_0001
Revises:
Create Date: 2026-05-12 00:00:00

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260512_0001"
down_revision = None
branch_labels = None
depends_on = None


reimbursement_status = sa.Enum(
    "own",
    "pending",
    "partial",
    "paid",
    name="reimbursementstatus",
    native_enum=False,
)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=True)

    op.create_table(
        "cards",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bank_name", sa.String(length=120), nullable=False),
        sa.Column("card_name", sa.String(length=120), nullable=False),
        sa.Column("last_four", sa.String(length=4), nullable=False),
        sa.Column("billing_day", sa.Integer(), nullable=False),
        sa.Column("due_day", sa.Integer(), nullable=False),
        sa.Column("credit_limit", sa.Numeric(12, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_cards_user_id", "cards", ["user_id"], unique=False)

    op.create_table(
        "people",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "name", name="uq_people_user_name"),
    )
    op.create_index("ix_people_user_id", "people", ["user_id"], unique=False)

    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("card_id", sa.Integer(), sa.ForeignKey("cards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("final_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("merchant", sa.String(length=255), nullable=True),
        sa.Column("category", sa.String(length=80), nullable=True),
        sa.Column("txn_date", sa.Date(), nullable=False),
        sa.Column("is_for_someone_else", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("person_id", sa.Integer(), sa.ForeignKey("people.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reimbursement_status", reimbursement_status, nullable=False, server_default="own"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_transactions_user_id", "transactions", ["user_id"], unique=False)
    op.create_index("ix_transactions_card_id", "transactions", ["card_id"], unique=False)
    op.create_index("ix_transactions_person_id", "transactions", ["person_id"], unique=False)

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("person_id", sa.Integer(), sa.ForeignKey("people.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount_paid", sa.Numeric(12, 2), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_payments_user_id", "payments", ["user_id"], unique=False)
    op.create_index("ix_payments_transaction_id", "payments", ["transaction_id"], unique=False)
    op.create_index("ix_payments_person_id", "payments", ["person_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_payments_person_id", table_name="payments")
    op.drop_index("ix_payments_transaction_id", table_name="payments")
    op.drop_index("ix_payments_user_id", table_name="payments")
    op.drop_table("payments")

    op.drop_index("ix_transactions_person_id", table_name="transactions")
    op.drop_index("ix_transactions_card_id", table_name="transactions")
    op.drop_index("ix_transactions_user_id", table_name="transactions")
    op.drop_table("transactions")

    op.drop_index("ix_people_user_id", table_name="people")
    op.drop_table("people")

    op.drop_index("ix_cards_user_id", table_name="cards")
    op.drop_table("cards")

    op.drop_index("ix_users_telegram_id", table_name="users")
    op.drop_table("users")
