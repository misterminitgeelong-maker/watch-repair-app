"""Shop booking extras: tenant business_address.

Revision ID: 20260519_shop_booking_extras
Revises: 20260519_shop_mobile_booking
Create Date: 2026-05-19

"""
from alembic import op
import sqlalchemy as sa

revision = "20260519_shop_booking_extras"
down_revision = "20260519_shop_mobile_booking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenant", sa.Column("business_address", sa.String(length=2000), nullable=True))


def downgrade() -> None:
    op.drop_column("tenant", "business_address")
