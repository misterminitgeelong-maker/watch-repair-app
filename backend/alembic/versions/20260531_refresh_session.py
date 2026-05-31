"""add refresh_session table for per-device refresh-token revocation

Revision ID: 20260531_refresh_session
Revises: 20260530d_brand_fields
Create Date: 2026-05-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260531_refresh_session"
down_revision: Union[str, None] = "20260530d_brand_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "refreshsession",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("jti", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_agent", sa.String(length=400), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("jti"),
    )
    op.create_index("ix_refreshsession_jti", "refreshsession", ["jti"])
    op.create_index("ix_refreshsession_tenant_id", "refreshsession", ["tenant_id"])
    op.create_index("ix_refreshsession_user_id", "refreshsession", ["user_id"])
    op.create_index("ix_refreshsession_revoked_at", "refreshsession", ["revoked_at"])


def downgrade() -> None:
    op.drop_index("ix_refreshsession_revoked_at", table_name="refreshsession")
    op.drop_index("ix_refreshsession_user_id", table_name="refreshsession")
    op.drop_index("ix_refreshsession_tenant_id", table_name="refreshsession")
    op.drop_index("ix_refreshsession_jti", table_name="refreshsession")
    op.drop_table("refreshsession")
