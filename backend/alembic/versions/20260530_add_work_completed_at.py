"""add work_completed_at to autokeyjob

Revision ID: 20260530_work_completed_at
Revises: 7d6099a959ad
Create Date: 2026-05-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260530_work_completed_at"
down_revision: Union[str, None] = "7d6099a959ad"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("autokeyjob", sa.Column("work_completed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("autokeyjob", "work_completed_at")
