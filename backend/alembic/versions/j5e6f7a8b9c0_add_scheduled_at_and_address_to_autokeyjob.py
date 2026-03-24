"""add scheduled_at and job_address to autokeyjob (ServiceM8-style scheduling)

Revision ID: j5e6f7a8b9c0
Revises: ac11a07ccace
Create Date: 2026-03-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = "j5e6f7a8b9c0"
down_revision: Union[str, None] = "ac11a07ccace"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("autokeyjob", sa.Column("scheduled_at", sa.DateTime(), nullable=True))
    op.add_column("autokeyjob", sa.Column("job_address", sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column("autokeyjob", sa.Column("job_type", sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.create_index(op.f("ix_autokeyjob_scheduled_at"), "autokeyjob", ["scheduled_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_autokeyjob_scheduled_at"), table_name="autokeyjob")
    op.drop_column("autokeyjob", "job_type")
    op.drop_column("autokeyjob", "job_address")
    op.drop_column("autokeyjob", "scheduled_at")
