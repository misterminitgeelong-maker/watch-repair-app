"""add attempt tracking (and email payload) for notification redelivery

Revision ID: 20260914b_notification_retry
Revises: 20260914b_shoe_fk_backfill
Create Date: 2026-09-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260914b_notification_retry"
down_revision: Union[str, None] = "20260914b_shoe_fk_backfill"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("smslog", sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("smslog", sa.Column("last_attempt_at", sa.DateTime(), nullable=True))
    op.add_column("emaillog", sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("emaillog", sa.Column("last_attempt_at", sa.DateTime(), nullable=True))
    op.add_column("emaillog", sa.Column("payload_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("emaillog", "payload_json")
    op.drop_column("emaillog", "last_attempt_at")
    op.drop_column("emaillog", "attempt_count")
    op.drop_column("smslog", "last_attempt_at")
    op.drop_column("smslog", "attempt_count")
