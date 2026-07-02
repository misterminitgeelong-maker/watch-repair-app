"""add mobile_lead_force_hq_dispatch testing flag

Revision ID: 20260702_force_hq_testing
Revises: 20260702_mobile_lead_dispatch
Create Date: 2026-07-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260702_force_hq_testing"
down_revision: Union[str, None] = "20260702_mobile_lead_dispatch"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "parentaccount",
        sa.Column(
            "mobile_lead_force_hq_dispatch",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("parentaccount", "mobile_lead_force_hq_dispatch")
