"""shop mobile booking re-offer bookkeeping (offer_count, offered_operator_ids_json)

Revision ID: 20261103a_shop_booking_reoffer
Revises: 20261101_engraving_events
Create Date: 2026-11-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261103a_shop_booking_reoffer"
down_revision: Union[str, None] = "20261102_network_messages"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "shopmobilebookingrequest",
        sa.Column("offer_count", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "shopmobilebookingrequest",
        sa.Column("offered_operator_ids_json", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("shopmobilebookingrequest", "offered_operator_ids_json")
    op.drop_column("shopmobilebookingrequest", "offer_count")
