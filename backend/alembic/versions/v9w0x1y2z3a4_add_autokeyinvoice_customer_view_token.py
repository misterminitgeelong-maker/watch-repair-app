"""add customer_view_token to autokeyinvoice for SMS invoice links

Revision ID: v9w0x1y2z3a4
Revises: u8v9w0x1y2z3
Create Date: 2026-03-30

"""
from alembic import op
import sqlalchemy as sa

revision = "v9w0x1y2z3a4"
down_revision = "u8v9w0x1y2z3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "autokeyinvoice",
        sa.Column("customer_view_token", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_autokeyinvoice_customer_view_token",
        "autokeyinvoice",
        ["customer_view_token"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_autokeyinvoice_customer_view_token", table_name="autokeyinvoice")
    op.drop_column("autokeyinvoice", "customer_view_token")
