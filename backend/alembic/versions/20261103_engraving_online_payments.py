"""engraving: online card payments

Revision ID: 20261103_engraving_payments
Revises: 20261101b_engraving_order_group
Create Date: 2026-11-03

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261103_engraving_payments"
down_revision: Union[str, None] = "20261101b_engraving_order_group"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "engravingevent",
        sa.Column("online_payments", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column("engravingorder", sa.Column("payment_method", sa.String(), nullable=True))
    op.add_column("engravingorder", sa.Column("stripe_checkout_id", sa.String(), nullable=True))
    # Orders already marked paid before this change were paid at the stall.
    op.execute("UPDATE engravingorder SET payment_method = 'stall' WHERE paid = true")


def downgrade() -> None:
    op.drop_column("engravingorder", "stripe_checkout_id")
    op.drop_column("engravingorder", "payment_method")
    op.drop_column("engravingevent", "online_payments")
