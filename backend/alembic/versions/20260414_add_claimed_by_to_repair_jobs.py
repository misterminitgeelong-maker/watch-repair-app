"""add claimed_by_user_id to repairjob and shoerepairjob for queue claim feature

Revision ID: 20260414_add_claimed_by
Revises: 20260414_merge_e1f2_z1a2
Create Date: 2026-04-14

"""
from alembic import op
import sqlalchemy as sa

revision = "20260414_add_claimed_by"
down_revision = "20260414_merge_e1f2_z1a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "repairjob",
        sa.Column("claimed_by_user_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "shoerepairjob",
        sa.Column("claimed_by_user_id", sa.Uuid(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("shoerepairjob", "claimed_by_user_id")
    op.drop_column("repairjob", "claimed_by_user_id")
