"""medal engraving events and orders

Adds engravingevent (one engraving stall at one meet, with a public QR token)
and engravingorder (one athlete's engraving, on qty medals), for the
QR-order → operator queue → laser CSV → ready alert flow.

Revision ID: 20261101_engraving_events
Revises: 20261028a_backfill_completed_at
Create Date: 2026-11-01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261101_engraving_events"
down_revision: Union[str, None] = "20261028a_backfill_completed_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "engravingevent",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=True),
        sa.Column("location", sa.String(), nullable=True),
        sa.Column("price_cents", sa.Integer(), nullable=False, server_default="1500"),
        sa.Column("minutes_per_medal", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("status", sa.String(), nullable=False, server_default="open"),
        sa.Column("sms_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("public_token", sa.String(), nullable=False),
        sa.Column("next_order_seq", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_engravingevent_tenant_id", "engravingevent", ["tenant_id"])
    op.create_index("ix_engravingevent_public_token", "engravingevent", ["public_token"], unique=True)

    op.create_table(
        "engravingorder",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_id", sa.Uuid(), sa.ForeignKey("engravingevent.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_seq", sa.Integer(), nullable=False),
        sa.Column("order_number", sa.String(), nullable=False),
        sa.Column("status_token", sa.String(), nullable=False),
        sa.Column("athlete_name", sa.String(), nullable=False),
        sa.Column("line2", sa.String(), nullable=True),
        sa.Column("place", sa.String(), nullable=False, server_default="None"),
        sa.Column("qty", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("medals_done", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="waiting"),
        sa.Column("paid", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("amount_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source", sa.String(), nullable=False, server_default="online"),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("ready_at", sa.DateTime(), nullable=True),
        sa.Column("ready_sms_status", sa.String(), nullable=True),
        sa.Column("collected_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("event_id", "order_seq", name="uq_engravingorder_event_seq"),
    )
    op.create_index("ix_engravingorder_tenant_id", "engravingorder", ["tenant_id"])
    op.create_index("ix_engravingorder_event_id", "engravingorder", ["event_id"])
    op.create_index("ix_engravingorder_status", "engravingorder", ["status"])
    op.create_index("ix_engravingorder_created_at", "engravingorder", ["created_at"])
    op.create_index("ix_engravingorder_status_token", "engravingorder", ["status_token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_engravingorder_status_token", table_name="engravingorder")
    op.drop_index("ix_engravingorder_created_at", table_name="engravingorder")
    op.drop_index("ix_engravingorder_status", table_name="engravingorder")
    op.drop_index("ix_engravingorder_event_id", table_name="engravingorder")
    op.drop_index("ix_engravingorder_tenant_id", table_name="engravingorder")
    op.drop_table("engravingorder")
    op.drop_index("ix_engravingevent_public_token", table_name="engravingevent")
    op.drop_index("ix_engravingevent_tenant_id", table_name="engravingevent")
    op.drop_table("engravingevent")
