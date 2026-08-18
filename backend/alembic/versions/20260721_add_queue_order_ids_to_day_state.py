"""add queue_order_ids_json to repairqueuedaystate

Revision ID: 20260721_queue_order
Revises: 20260805_billing_exempt
Create Date: 2026-07-21

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260721_queue_order"
down_revision: Union[str, None] = "20260805_billing_exempt"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "repairqueuedaystate",
        sa.Column("queue_order_ids_json", sa.String(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("repairqueuedaystate", "queue_order_ids_json")
