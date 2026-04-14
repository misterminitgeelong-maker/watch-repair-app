"""merge heads and add tenant.mobile_services_customer_sms_enabled

Revision ID: d5e6f7a8b9c0
Revises: c3d4e5f6a7b8, c3f4e5a6b7d8
Create Date: 2026-04-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, tuple[str, ...], None] = ("c3d4e5f6a7b8", "c3f4e5a6b7d8")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenant",
        sa.Column(
            "mobile_services_customer_sms_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    with op.batch_alter_table("tenant") as batch_op:
        batch_op.drop_column("mobile_services_customer_sms_enabled")
