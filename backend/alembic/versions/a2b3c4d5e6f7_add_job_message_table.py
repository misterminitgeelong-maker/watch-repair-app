"""add job_message table for two-way per-job SMS thread

Revision ID: a2b3c4d5e6f7
Revises: z1a2b3c4d5e6
Create Date: 2026-05-09

"""
from alembic import op
import sqlalchemy as sa

revision = "a2b3c4d5e6f7"
down_revision = "z1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jobmessage",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("repair_job_id", sa.Uuid(), nullable=True),
        sa.Column("shoe_repair_job_id", sa.Uuid(), nullable=True),
        sa.Column("auto_key_job_id", sa.Uuid(), nullable=True),
        sa.Column("direction", sa.String(), nullable=False),
        sa.Column("body", sa.String(), nullable=False),
        sa.Column("from_phone", sa.String(), nullable=True),
        sa.Column("to_phone", sa.String(), nullable=True),
        sa.Column("twilio_sid", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["auto_key_job_id"], ["autokeyjob.id"]),
        sa.ForeignKeyConstraint(["repair_job_id"], ["repairjob.id"]),
        sa.ForeignKeyConstraint(["shoe_repair_job_id"], ["shoerepairjob.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_jobmessage_tenant_id", "jobmessage", ["tenant_id"])
    op.create_index("ix_jobmessage_repair_job_id", "jobmessage", ["repair_job_id"])
    op.create_index("ix_jobmessage_shoe_repair_job_id", "jobmessage", ["shoe_repair_job_id"])
    op.create_index("ix_jobmessage_auto_key_job_id", "jobmessage", ["auto_key_job_id"])


def downgrade() -> None:
    op.drop_index("ix_jobmessage_auto_key_job_id", "jobmessage")
    op.drop_index("ix_jobmessage_shoe_repair_job_id", "jobmessage")
    op.drop_index("ix_jobmessage_repair_job_id", "jobmessage")
    op.drop_index("ix_jobmessage_tenant_id", "jobmessage")
    op.drop_table("jobmessage")
