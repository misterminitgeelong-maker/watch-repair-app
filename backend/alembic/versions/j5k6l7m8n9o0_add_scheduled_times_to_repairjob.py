"""add scheduled_start and scheduled_end to repairjob

Revision ID: j5k6l7m8n9o0
Revises: i4d5e6f7a8b9c
Create Date: 2026-04-06 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "j5k6l7m8n9o0"
down_revision: Union[str, None] = "i4d5e6f7a8b9c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("repairjob", sa.Column("scheduled_start", sa.DateTime(), nullable=True))
    op.add_column("repairjob", sa.Column("scheduled_end", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("repairjob", "scheduled_end")
    op.drop_column("repairjob", "scheduled_start")
