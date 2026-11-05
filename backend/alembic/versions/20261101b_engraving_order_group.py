"""engraving orders: group id and ticket number for medals ordered together

Revision ID: 20261101b_engraving_order_group
Revises: 20261101_engraving_events
Create Date: 2026-11-01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261101b_engraving_order_group"
down_revision: Union[str, None] = "20261011b_hq_stock"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("engravingorder", sa.Column("group_id", sa.Uuid(), nullable=True))
    op.create_index("ix_engravingorder_group_id", "engravingorder", ["group_id"])
    op.add_column("engravingorder", sa.Column("ticket_number", sa.String(), nullable=True))
    op.create_index("ix_engravingorder_ticket_number", "engravingorder", ["ticket_number"])


def downgrade() -> None:
    op.drop_index("ix_engravingorder_ticket_number", table_name="engravingorder")
    op.drop_column("engravingorder", "ticket_number")
    op.drop_index("ix_engravingorder_group_id", table_name="engravingorder")
    op.drop_column("engravingorder", "group_id")
