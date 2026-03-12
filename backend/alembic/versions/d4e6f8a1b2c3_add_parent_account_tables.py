"""add parent account tables

Revision ID: d4e6f8a1b2c3
Revises: c3d5e7f9a1b4
Create Date: 2026-03-12 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d4e6f8a1b2c3"
down_revision: Union[str, None] = "c3d5e7f9a1b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "parentaccount",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("owner_email", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_parentaccount_owner_email"), "parentaccount", ["owner_email"], unique=False)

    op.create_table(
        "parentaccountmembership",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("parent_account_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["parent_account_id"], ["parentaccount.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_parentaccountmembership_parent_account_id"),
        "parentaccountmembership",
        ["parent_account_id"],
        unique=False,
    )
    op.create_index(op.f("ix_parentaccountmembership_tenant_id"), "parentaccountmembership", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_parentaccountmembership_user_id"), "parentaccountmembership", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_parentaccountmembership_user_id"), table_name="parentaccountmembership")
    op.drop_index(op.f("ix_parentaccountmembership_tenant_id"), table_name="parentaccountmembership")
    op.drop_index(op.f("ix_parentaccountmembership_parent_account_id"), table_name="parentaccountmembership")
    op.drop_table("parentaccountmembership")

    op.drop_index(op.f("ix_parentaccount_owner_email"), table_name="parentaccount")
    op.drop_table("parentaccount")
