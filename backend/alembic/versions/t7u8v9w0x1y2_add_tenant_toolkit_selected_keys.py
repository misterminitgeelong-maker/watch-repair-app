"""add tenant.toolkit_selected_keys for mobile services toolkit inventory

Revision ID: t7u8v9w0x1y2
Revises: 534bf5c52bfa
Create Date: 2026-03-30

"""
from alembic import op
import sqlalchemy as sa

revision = "t7u8v9w0x1y2"
down_revision = "534bf5c52bfa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenant",
        sa.Column("toolkit_selected_keys", sa.Text(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("tenant", "toolkit_selected_keys")
