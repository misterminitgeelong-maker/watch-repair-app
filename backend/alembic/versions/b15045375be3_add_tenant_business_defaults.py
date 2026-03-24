"""add tenant business defaults

Revision ID: b15045375be3
Revises: f62d271a3526
Create Date: 2026-03-24 22:41:46.825478

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b15045375be3'
down_revision: Union[str, None] = 'f62d271a3526'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenant",
        sa.Column("default_currency", sa.String(length=3), nullable=False, server_default="AUD"),
    )
    op.add_column(
        "tenant",
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="Australia/Melbourne"),
    )


def downgrade() -> None:
    op.drop_column("tenant", "timezone")
    op.drop_column("tenant", "default_currency")
