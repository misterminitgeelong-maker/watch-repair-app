"""parent link requests: a shop must accept before HQ can link it

Revision ID: 20260923b_parent_link_requests
Revises: 20260923a_explicit_hq_grants
Create Date: 2026-09-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260923b_parent_link_requests"
down_revision: Union[str, None] = "20260923a_explicit_hq_grants"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "parentlinkrequest",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("parent_account_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("shop_number", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("decided_by_user_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["parent_account_id"], ["parentaccount.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["decided_by_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_parentlinkrequest_parent_account_id"), "parentlinkrequest", ["parent_account_id"])
    op.create_index(op.f("ix_parentlinkrequest_tenant_id"), "parentlinkrequest", ["tenant_id"])
    op.create_index(op.f("ix_parentlinkrequest_status"), "parentlinkrequest", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_parentlinkrequest_status"), table_name="parentlinkrequest")
    op.drop_index(op.f("ix_parentlinkrequest_tenant_id"), table_name="parentlinkrequest")
    op.drop_index(op.f("ix_parentlinkrequest_parent_account_id"), table_name="parentlinkrequest")
    op.drop_table("parentlinkrequest")
