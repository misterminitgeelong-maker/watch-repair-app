"""Add Stripe Connect Express fields on tenant for shop invoice payouts.

Revision ID: x1y2z3a4b5c6
Revises: w0x1y2z3a4b5
Create Date: 2026-03-30

"""
from alembic import op
import sqlalchemy as sa

revision = "x1y2z3a4b5c6"
down_revision = "w0x1y2z3a4b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenant", sa.Column("stripe_connect_account_id", sa.Text(), nullable=True))
    op.add_column(
        "tenant",
        sa.Column(
            "stripe_connect_charges_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "tenant",
        sa.Column(
            "stripe_connect_payouts_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "tenant",
        sa.Column(
            "stripe_connect_details_submitted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("tenant", "stripe_connect_details_submitted")
    op.drop_column("tenant", "stripe_connect_payouts_enabled")
    op.drop_column("tenant", "stripe_connect_charges_enabled")
    op.drop_column("tenant", "stripe_connect_account_id")
