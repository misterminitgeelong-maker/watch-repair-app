"""add stripewebhookevent ledger for idempotent webhook processing

Revision ID: 20260421_stripe_evt
Revises: 20260421_prospect_lead
Create Date: 2026-04-21

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260421_stripe_evt"
down_revision: Union[str, None] = "20260421_prospect_lead"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "stripewebhookevent",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", name="uq_stripewebhookevent_event_id"),
    )
    op.create_index(op.f("ix_stripewebhookevent_event_id"), "stripewebhookevent", ["event_id"], unique=False)
    op.create_index(op.f("ix_stripewebhookevent_event_type"), "stripewebhookevent", ["event_type"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_stripewebhookevent_event_type"), table_name="stripewebhookevent")
    op.drop_index(op.f("ix_stripewebhookevent_event_id"), table_name="stripewebhookevent")
    op.drop_table("stripewebhookevent")
