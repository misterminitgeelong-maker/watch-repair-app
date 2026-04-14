"""add tenant.subscription_status and tenant.trial_end for Stripe lifecycle tracking

Revision ID: e1f2a3b4c5d6
Revises: d5e6f7a8b9c0
Create Date: 2026-04-14

"""
from alembic import op
import sqlalchemy as sa

revision = "e1f2a3b4c5d6"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenant",
        sa.Column("subscription_status", sa.String(), nullable=True),
    )
    op.add_column(
        "tenant",
        sa.Column("trial_end", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenant", "trial_end")
    op.drop_column("tenant", "subscription_status")
