"""add internal_notes, parts_eta, status_changed_at to repairjob

Revision ID: 20260511_job_fields_v2
Revises: d5e6f7a8b9c1
Create Date: 2026-05-11

"""
from alembic import op
import sqlalchemy as sa

revision = "20260511_job_fields_v2"
down_revision = "d5e6f7a8b9c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("repairjob", sa.Column("internal_notes", sa.Text(), nullable=True))
    op.add_column("repairjob", sa.Column("parts_eta", sa.Date(), nullable=True))
    op.add_column("repairjob", sa.Column("status_changed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("repairjob", "status_changed_at")
    op.drop_column("repairjob", "parts_eta")
    op.drop_column("repairjob", "internal_notes")
