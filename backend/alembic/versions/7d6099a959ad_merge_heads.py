"""merge heads

Revision ID: 7d6099a959ad
Revises: 20260519_minit_area_region, 20260521_add_shop_identity
Create Date: 2026-05-22 07:25:58.541809

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '7d6099a959ad'
down_revision: Union[str, None] = ('20260519_minit_area_region', '20260521_add_shop_identity')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
