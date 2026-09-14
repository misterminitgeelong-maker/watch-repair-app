"""add stripewebhookevent (idempotency ledger for the Stripe billing webhook)

Revision ID: 20260914a_stripe_webhook_event
Revises: 20260902g_user_mobile
Create Date: 2026-09-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260914a_stripe_webhook_event"
down_revision: Union[str, None] = "20260902g_user_mobile"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "stripewebhookevent",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("stripewebhookevent")
