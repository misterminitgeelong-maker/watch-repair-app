"""add collection_date to autokeyjob

Revision ID: i4d5e6f7a8b9c
Revises: h3c4d5e6f7a8b
Create Date: 2026-03-17 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "i4d5e6f7a8b9c"
down_revision: Union[str, None] = "h3c4d5e6f7a8b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("autokeyjob", sa.Column("collection_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("autokeyjob", "collection_date")
