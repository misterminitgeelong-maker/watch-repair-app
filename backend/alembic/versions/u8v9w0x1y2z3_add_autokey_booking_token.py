"""add booking_confirmation_token to autokeyjob

Revision ID: u8v9w0x1y2z3
Revises: t7u8v9w0x1y2
Create Date: 2026-03-30

"""
from alembic import op
import sqlalchemy as sa

revision = "u8v9w0x1y2z3"
down_revision = "t7u8v9w0x1y2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "autokeyjob",
        sa.Column("booking_confirmation_token", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_autokeyjob_booking_confirmation_token",
        "autokeyjob",
        ["booking_confirmation_token"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_autokeyjob_booking_confirmation_token", table_name="autokeyjob")
    op.drop_column("autokeyjob", "booking_confirmation_token")
