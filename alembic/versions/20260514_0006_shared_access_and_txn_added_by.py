"""add shared expense access and transaction added_by_user_id

Revision ID: 20260514_0006
Revises: 20260514_0005
Create Date: 2026-05-14 01:20:00

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260514_0006"
down_revision = "20260514_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("transactions", sa.Column("added_by_user_id", sa.Integer(), nullable=True))
    op.create_index("ix_transactions_added_by_user_id", "transactions", ["added_by_user_id"], unique=False)
    op.create_foreign_key(
        "fk_transactions_added_by_user_id_users",
        "transactions",
        "users",
        ["added_by_user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.execute(sa.text("UPDATE transactions SET added_by_user_id = user_id WHERE added_by_user_id IS NULL"))
    op.alter_column("transactions", "added_by_user_id", nullable=False)

    op.create_table(
        "shared_expense_access",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "collaborator_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_user_id", "collaborator_user_id", name="uq_shared_owner_collaborator"),
    )
    op.create_index("ix_shared_expense_access_owner_user_id", "shared_expense_access", ["owner_user_id"], unique=False)
    op.create_index(
        "ix_shared_expense_access_collaborator_user_id",
        "shared_expense_access",
        ["collaborator_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_shared_expense_access_collaborator_user_id", table_name="shared_expense_access")
    op.drop_index("ix_shared_expense_access_owner_user_id", table_name="shared_expense_access")
    op.drop_table("shared_expense_access")

    op.drop_constraint("fk_transactions_added_by_user_id_users", "transactions", type_="foreignkey")
    op.drop_index("ix_transactions_added_by_user_id", table_name="transactions")
    op.drop_column("transactions", "added_by_user_id")
