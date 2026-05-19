"""Add tenant.minit_area and tenant.minit_region from TSS shop import.

Revision ID: 20260519_tenant_minit_area_region
Revises: 20260519_tenant_shop_number
Create Date: 2026-05-19

"""
from alembic import op
import sqlalchemy as sa

revision = "20260519_tenant_minit_area_region"
down_revision = "20260519_tenant_shop_number"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenant", sa.Column("minit_area", sa.String(length=120), nullable=True))
    op.add_column("tenant", sa.Column("minit_region", sa.String(length=40), nullable=True))
    op.create_index("ix_tenant_minit_region", "tenant", ["minit_region"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_tenant_minit_region", table_name="tenant")
    op.drop_column("tenant", "minit_region")
    op.drop_column("tenant", "minit_area")
