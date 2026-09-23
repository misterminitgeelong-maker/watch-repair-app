"""customer portal one-time codes

Revision ID: 20260923c_customer_portal_otp
Revises: 20260923b_parent_link_requests
Create Date: 2026-09-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260923c_customer_portal_otp"
down_revision: Union[str, None] = "20260923b_parent_link_requests"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "customerportalotp",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("phone", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("code_hash", sa.String(length=128), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_customerportalotp_tenant_id"), "customerportalotp", ["tenant_id"])
    op.create_index(op.f("ix_customerportalotp_phone"), "customerportalotp", ["phone"])


def downgrade() -> None:
    op.drop_index(op.f("ix_customerportalotp_phone"), table_name="customerportalotp")
    op.drop_index(op.f("ix_customerportalotp_tenant_id"), table_name="customerportalotp")
    op.drop_table("customerportalotp")
