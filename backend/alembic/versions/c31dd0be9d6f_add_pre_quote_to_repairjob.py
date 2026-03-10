"""add_pre_quote_to_repairjob

Revision ID: c31dd0be9d6f
Revises: b7b5e6f3a9f2
Create Date: 2026-03-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c31dd0be9d6f"
down_revision: Union[str, None] = "b7b5e6f3a9f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("repairjob", sa.Column("pre_quote_cents", sa.Integer(), nullable=False, server_default="0"))
    op.alter_column("repairjob", "pre_quote_cents", server_default=None)


def downgrade() -> None:
    op.drop_column("repairjob", "pre_quote_cents")
