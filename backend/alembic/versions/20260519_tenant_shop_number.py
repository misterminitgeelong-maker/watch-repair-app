"""Add tenant.shop_number for Minit shop / operator identification.

Revision ID: 20260519_tenant_shop_number
Revises: 20260519_mobile_dispatch_phone
Create Date: 2026-05-19

"""
from alembic import op
import sqlalchemy as sa

revision = "20260519_tenant_shop_number"
down_revision = "20260519_mobile_dispatch_phone"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenant", sa.Column("shop_number", sa.String(length=10), nullable=True))
    op.create_index("ix_tenant_shop_number", "tenant", ["shop_number"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_tenant_shop_number", table_name="tenant")
    op.drop_column("tenant", "shop_number")
