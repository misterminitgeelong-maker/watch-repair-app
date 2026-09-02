"""add shopownerinvite table (self-service owner login claim links)

Revision ID: 20260902f_shop_owner_invite
Revises: 20260902e_pool_alerted_at
Create Date: 2026-09-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260902f_shop_owner_invite"
down_revision: Union[str, None] = "20260902e_pool_alerted_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "shopownerinvite",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("parent_account_id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("token", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.ForeignKeyConstraint(["parent_account_id"], ["parentaccount.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_shopownerinvite_tenant_id"), "shopownerinvite", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_shopownerinvite_parent_account_id"), "shopownerinvite", ["parent_account_id"], unique=False)
    op.create_index(op.f("ix_shopownerinvite_owner_user_id"), "shopownerinvite", ["owner_user_id"], unique=False)
    op.create_index(op.f("ix_shopownerinvite_token"), "shopownerinvite", ["token"], unique=True)
    op.create_index(op.f("ix_shopownerinvite_status"), "shopownerinvite", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_shopownerinvite_status"), table_name="shopownerinvite")
    op.drop_index(op.f("ix_shopownerinvite_token"), table_name="shopownerinvite")
    op.drop_index(op.f("ix_shopownerinvite_owner_user_id"), table_name="shopownerinvite")
    op.drop_index(op.f("ix_shopownerinvite_parent_account_id"), table_name="shopownerinvite")
    op.drop_index(op.f("ix_shopownerinvite_tenant_id"), table_name="shopownerinvite")
    op.drop_table("shopownerinvite")
