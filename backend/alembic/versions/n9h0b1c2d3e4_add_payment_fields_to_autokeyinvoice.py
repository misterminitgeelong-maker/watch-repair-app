"""add payment_method and paid_at to autokeyinvoice

Revision ID: n9h0b1c2d3e4
Revises: m8g9a0b1c2d3
Create Date: 2026-03-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = "n9h0b1c2d3e4"
down_revision: Union[str, None] = "m8g9a0b1c2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("autokeyinvoice", sa.Column("payment_method", sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column("autokeyinvoice", sa.Column("paid_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("autokeyinvoice", "paid_at")
    op.drop_column("autokeyinvoice", "payment_method")
