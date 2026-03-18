"""merge subscription and fleet fields branches

Revision ID: ac11a07ccace
Revises: 20260318_add_subscription_fields_to_customeraccount, 20260318_merge_heads
Create Date: 2026-03-18 21:00:42.842942

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'ac11a07ccace'
down_revision: Union[str, None] = ('20260318_add_subscription_fields_to_customeraccount', '20260318_merge_heads')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
