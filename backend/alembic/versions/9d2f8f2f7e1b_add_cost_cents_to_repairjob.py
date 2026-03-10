"""add_cost_cents_to_repairjob

Revision ID: 9d2f8f2f7e1b
Revises: 7704face0304
Create Date: 2026-03-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9d2f8f2f7e1b"
down_revision: Union[str, None] = "7704face0304"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("repairjob", sa.Column("cost_cents", sa.Integer(), nullable=False, server_default="0"))
    if op.get_bind().dialect.name != "sqlite":
        op.alter_column("repairjob", "cost_cents", server_default=None)


def downgrade() -> None:
    op.drop_column("repairjob", "cost_cents")
