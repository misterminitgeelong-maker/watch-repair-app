"""Add shop identity fields to tenant (ABN, phone, email, payment instructions).

Revision ID: 20260521_add_shop_identity
Revises: 20260519_tenant_shop_number
Create Date: 2026-05-21

"""
from alembic import op
import sqlalchemy as sa

revision = "20260521_add_shop_identity"
down_revision = "20260519_tenant_shop_number"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenant", sa.Column("abn", sa.String(length=20), nullable=True))
    op.add_column("tenant", sa.Column("shop_phone", sa.String(length=40), nullable=True))
    op.add_column("tenant", sa.Column("shop_email", sa.String(length=200), nullable=True))
    op.add_column("tenant", sa.Column("payment_instructions", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("tenant", "payment_instructions")
    op.drop_column("tenant", "shop_email")
    op.drop_column("tenant", "shop_phone")
    op.drop_column("tenant", "abn")
