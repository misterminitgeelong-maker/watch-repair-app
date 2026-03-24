"""add stripe fields to tenant

Revision ID: g2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-03-12 02:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "g2b3c4d5e6f7"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("tenant") as batch_op:
        batch_op.add_column(sa.Column("stripe_customer_id", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("stripe_subscription_id", sa.String(), nullable=True))
        batch_op.create_index("ix_tenant_stripe_customer_id", ["stripe_customer_id"], unique=False)
        batch_op.create_index("ix_tenant_stripe_subscription_id", ["stripe_subscription_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("tenant") as batch_op:
        batch_op.drop_index("ix_tenant_stripe_subscription_id")
        batch_op.drop_index("ix_tenant_stripe_customer_id")
        batch_op.drop_column("stripe_subscription_id")
        batch_op.drop_column("stripe_customer_id")
