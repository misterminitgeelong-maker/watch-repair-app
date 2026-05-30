"""add logo_url and brand_color to tenant

Revision ID: 20260530d_brand_fields
Revises: 20260530c_lead_fields
Create Date: 2026-05-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260530d_brand_fields"
down_revision: Union[str, None] = "20260530c_lead_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tenant", sa.Column("logo_url", sa.String(length=1000), nullable=True))
    op.add_column("tenant", sa.Column("brand_color", sa.String(length=9), nullable=True))


def downgrade() -> None:
    op.drop_column("tenant", "brand_color")
    op.drop_column("tenant", "logo_url")
