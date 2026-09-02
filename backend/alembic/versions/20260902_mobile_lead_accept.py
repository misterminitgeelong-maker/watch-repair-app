"""add accepted_at to mobileleaddispatch (quick-accept from SMS/email offer)

Revision ID: 20260902_mobile_lead_accept
Revises: 20260819_vswt_weekly_metrics
Create Date: 2026-09-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260902_mobile_lead_accept"
down_revision: Union[str, None] = "20260819_vswt_weekly_metrics"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "mobileleaddispatch",
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("mobileleaddispatch", "accepted_at")
