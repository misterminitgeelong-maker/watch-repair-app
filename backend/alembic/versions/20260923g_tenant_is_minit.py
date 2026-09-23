"""tenant.is_minit: store Mister Minit identity instead of reading it off the slug

Backfills the flag for every existing Minit tenant (HQ slug + minit-* shops),
which is exactly the set the slug rule matched before.

Revision ID: 20260923g_tenant_is_minit
Revises: 20260923f_refresh_token_rotation
Create Date: 2026-09-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260923g_tenant_is_minit"
down_revision: Union[str, None] = "20260923f_refresh_token_rotation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenant",
        sa.Column("is_minit", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_tenant_is_minit", "tenant", ["is_minit"])
    op.execute(
        "UPDATE tenant SET is_minit = TRUE "
        "WHERE lower(slug) = 'mmsupport' OR lower(slug) LIKE 'minit-%' OR plan_code = 'minit_hq'"
    )


def downgrade() -> None:
    op.drop_index("ix_tenant_is_minit", table_name="tenant")
    op.drop_column("tenant", "is_minit")
