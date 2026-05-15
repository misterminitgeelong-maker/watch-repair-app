"""add discount_cents to quote and invoice

Revision ID: a1b2c3d4e5f6
Revises: z1a2b3c4d5e6
Create Date: 2026-05-15

"""
from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "z1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "quote",
        sa.Column("discount_cents", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "invoice",
        sa.Column("discount_cents", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("quote", "discount_cents")
    op.drop_column("invoice", "discount_cents")
