"""refresh token rotation: previous_jti / rotated_at / revoked_reason on refreshsession

Revision ID: 20260923f_refresh_token_rotation
Revises: 20260923e_merge_heads
Create Date: 2026-09-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260923f_refresh_token_rotation"
down_revision: Union[str, None] = "20260923e_merge_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("refreshsession", sa.Column("previous_jti", sa.String(length=64), nullable=True))
    op.add_column("refreshsession", sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("refreshsession", sa.Column("revoked_reason", sa.String(length=40), nullable=True))
    op.create_index("ix_refreshsession_previous_jti", "refreshsession", ["previous_jti"])


def downgrade() -> None:
    op.drop_index("ix_refreshsession_previous_jti", table_name="refreshsession")
    op.drop_column("refreshsession", "revoked_reason")
    op.drop_column("refreshsession", "rotated_at")
    op.drop_column("refreshsession", "previous_jti")
