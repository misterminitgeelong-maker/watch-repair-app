"""add a dedicated inbound-email webhook secret to parentaccount

Revision ID: 20260923a_inbound_email_secret
Revises: 20260921a_mobile_kpi_snapshots
Create Date: 2026-09-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260923a_inbound_email_secret"
down_revision: Union[str, None] = "20260921a_mobile_kpi_snapshots"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("parentaccount", sa.Column("inbound_email_secret_hash", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("parentaccount", "inbound_email_secret_hash")
