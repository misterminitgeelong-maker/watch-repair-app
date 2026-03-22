"""add_visit_order_to_autokeyjob

Revision ID: l7f8a9b0c1d2
Revises: k6f7a8b9c0d1
Create Date: 2026-03-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "l7f8a9b0c1d2"
down_revision: Union[str, None] = "k6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("autokeyjob", sa.Column("visit_order", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("autokeyjob", "visit_order")
