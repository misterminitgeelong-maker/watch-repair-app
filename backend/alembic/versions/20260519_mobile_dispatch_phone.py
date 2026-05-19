"""Add tenant.mobile_dispatch_phone for shop booking operator SMS.

Revision ID: 20260519_mobile_dispatch_phone
Revises: 20260519_shop_booking_extras
Create Date: 2026-05-19

"""
from alembic import op
import sqlalchemy as sa

revision = "20260519_mobile_dispatch_phone"
down_revision = "20260519_shop_booking_extras"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenant", sa.Column("mobile_dispatch_phone", sa.String(length=80), nullable=True))


def downgrade() -> None:
    op.drop_column("tenant", "mobile_dispatch_phone")
