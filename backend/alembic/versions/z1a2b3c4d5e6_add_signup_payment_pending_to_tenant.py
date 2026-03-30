"""add tenant.signup_payment_pending for Stripe signup gating

Revision ID: z1a2b3c4d5e6
Revises: x1y2z3a4b5c6
Create Date: 2026-03-30

"""
from alembic import op
import sqlalchemy as sa

revision = "z1a2b3c4d5e6"
down_revision = "x1y2z3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenant",
        sa.Column(
            "signup_payment_pending",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("tenant", "signup_payment_pending")
