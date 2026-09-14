"""add job_message table for two-way per-job SMS thread

Revision ID: d5e6f7a8b9c1
Revises: 20260503_customer_orders
Create Date: 2026-05-09

"""
from alembic import op
import sqlalchemy as sa

revision = "d5e6f7a8b9c1"
down_revision = "20260503_customer_orders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # shoerepairjob is created later in the chain (20260612_reconcile_shoe_tables)
    # on a fresh database; 20260914b_shoe_fk_backfill adds the FK afterwards.
    shoe_fk = []
    if sa.inspect(op.get_bind()).has_table("shoerepairjob"):
        shoe_fk.append(sa.ForeignKeyConstraint(["shoe_repair_job_id"], ["shoerepairjob.id"]))
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
        *shoe_fk,
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
