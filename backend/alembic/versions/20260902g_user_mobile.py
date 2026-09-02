"""add mobile to user (personal mobile, e.g. for shop-owner invite SMS)

Revision ID: 20260902g_user_mobile
Revises: 20260902f_shop_owner_invite
Create Date: 2026-09-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260902g_user_mobile"
down_revision: Union[str, None] = "20260902f_shop_owner_invite"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user", sa.Column("mobile", sa.String(length=40), nullable=True))


def downgrade() -> None:
    op.drop_column("user", "mobile")
