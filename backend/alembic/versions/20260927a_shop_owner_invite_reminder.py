"""remember when a shop-owner invite was chased before it expired

Revision ID: 20260927a_shop_owner_invite_reminder
Revises: 20260923j_tenant_fk_on_delete
Create Date: 2026-09-27
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260927a_shop_owner_invite_reminder"
down_revision: Union[str, None] = "20260923j_tenant_fk_on_delete"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("shopownerinvite", sa.Column("reminder_sent_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("shopownerinvite", "reminder_sent_at")
