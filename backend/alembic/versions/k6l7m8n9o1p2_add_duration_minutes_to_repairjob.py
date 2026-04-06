"""add duration_minutes to repairjob

Revision ID: k6l7m8n9o1p2
Revises: j5k6l7m8n9o0
Create Date: 2026-04-06

"""
from typing import Union
from alembic import op
import sqlalchemy as sa

revision: str = "k6l7m8n9o1p2"
down_revision: Union[str, None] = "j5k6l7m8n9o0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "repairjob",
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
    )
    # Backfill from existing scheduled_start / scheduled_end where both are set
    op.execute(
        """
        UPDATE repairjob
        SET duration_minutes = CAST(
            EXTRACT(EPOCH FROM (scheduled_end - scheduled_start)) / 60 AS INTEGER
        )
        WHERE scheduled_start IS NOT NULL AND scheduled_end IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_column("repairjob", "duration_minutes")
