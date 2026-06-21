"""Add suburb routing metadata to shop mobile booking requests.

Revision ID: 20260622_shop_booking_routing
Revises: 20260621c_invoice_payurl
Create Date: 2026-06-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260622_shop_booking_routing"
down_revision: Union[str, None] = "20260621c_invoice_payurl"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("shopmobilebookingrequest", sa.Column("job_suburb", sa.String(length=200), nullable=True))
    op.add_column("shopmobilebookingrequest", sa.Column("job_state_code", sa.String(length=8), nullable=True))
    op.add_column("shopmobilebookingrequest", sa.Column("operator_routing_rule", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("shopmobilebookingrequest", "operator_routing_rule")
    op.drop_column("shopmobilebookingrequest", "job_state_code")
    op.drop_column("shopmobilebookingrequest", "job_suburb")
