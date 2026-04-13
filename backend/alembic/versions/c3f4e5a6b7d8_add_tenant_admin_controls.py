"""add tenant admin controls

Revision ID: c3f4e5a6b7d8
Revises: b2c3d4e5f6a7
Create Date: 2026-04-08
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c3f4e5a6b7d8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tenant", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("tenant", sa.Column("auth_revoked_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("tenant") as batch_op:
        batch_op.drop_column("auth_revoked_at")
        batch_op.drop_column("is_active")
