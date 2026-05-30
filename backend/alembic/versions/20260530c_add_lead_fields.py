"""add suburb_name and next_follow_up_on to prospect lead

Revision ID: 20260530c_lead_fields
Revises: 20260530b_cai_xero
Create Date: 2026-05-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260530c_lead_fields"
down_revision: Union[str, None] = "20260530b_cai_xero"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("prospectlead", sa.Column("suburb_name", sa.String(), nullable=True))
    op.add_column("prospectlead", sa.Column("next_follow_up_on", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("prospectlead", "next_follow_up_on")
    op.drop_column("prospectlead", "suburb_name")
