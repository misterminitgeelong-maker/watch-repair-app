"""add source to prospectlead (distinguishes B2B-prospected leads from routed website leads)

Revision ID: 20260902c_prospect_lead_source
Revises: 20260902b_shop_booking_pool
Create Date: 2026-09-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260902c_prospect_lead_source"
down_revision: Union[str, None] = "20260902b_shop_booking_pool"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "prospectlead",
        sa.Column("source", sa.String(length=20), nullable=False, server_default="prospected"),
    )
    op.create_index(
        op.f("ix_prospectlead_source"),
        "prospectlead",
        ["source"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_prospectlead_source"), table_name="prospectlead")
    op.drop_column("prospectlead", "source")
