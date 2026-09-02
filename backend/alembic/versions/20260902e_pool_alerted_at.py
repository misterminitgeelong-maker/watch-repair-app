"""add alerted_at to intakejob (Dispatch Pool digest alert bookkeeping)

Revision ID: 20260902e_pool_alerted_at
Revises: 20260902d_email_log
Create Date: 2026-09-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260902e_pool_alerted_at"
down_revision: Union[str, None] = "20260902d_email_log"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "intakejob",
        sa.Column("alerted_at", sa.DateTime(), nullable=True),
    )
    op.create_index(op.f("ix_intakejob_alerted_at"), "intakejob", ["alerted_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_intakejob_alerted_at"), table_name="intakejob")
    op.drop_column("intakejob", "alerted_at")
