"""customer-facing status note on watch and shoe repair jobs

Revision ID: 20260923i_job_customer_note
Revises: 20260923h_card_payment_issue
Create Date: 2026-09-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260923i_job_customer_note"
down_revision: Union[str, None] = "20260923h_card_payment_issue"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table in ("repairjob", "shoerepairjob"):
        op.add_column(table, sa.Column("customer_note", sa.String(length=280), nullable=True))
        op.add_column(table, sa.Column("customer_note_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    for table in ("repairjob", "shoerepairjob"):
        op.drop_column(table, "customer_note_at")
        op.drop_column(table, "customer_note")
