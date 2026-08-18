"""add mobile_weekly_report_opt_in + last_mobile_weekly_report_sent_at to parentaccount

Revision ID: 20260808_mobile_weekly_report
Revises: 20260721_queue_order
Create Date: 2026-08-08

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260808_mobile_weekly_report"
down_revision: Union[str, None] = "20260721_queue_order"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "parentaccount",
        sa.Column("mobile_weekly_report_opt_in", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "parentaccount",
        sa.Column("last_mobile_weekly_report_sent_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("parentaccount", "last_mobile_weekly_report_sent_at")
    op.drop_column("parentaccount", "mobile_weekly_report_opt_in")
