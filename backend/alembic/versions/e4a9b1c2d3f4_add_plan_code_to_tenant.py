"""add_plan_code_to_tenant

Revision ID: e4a9b1c2d3f4
Revises: c9d4e5f6a7b8
Create Date: 2026-03-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e4a9b1c2d3f4"
down_revision: Union[str, None] = "c9d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenant",
        sa.Column("plan_code", sa.String(length=32), nullable=False, server_default="enterprise"),
    )
    op.execute("UPDATE tenant SET plan_code = 'enterprise' WHERE plan_code IS NULL OR plan_code = ''")


def downgrade() -> None:
    op.drop_column("tenant", "plan_code")
