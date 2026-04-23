"""add intake dispatch: ring-map fields on tenant + IntakeJob pool table

Revision ID: 20260424_intake_dispatch
Revises: 20260423_merge_heads
Create Date: 2026-04-24

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260424_intake_dispatch"
down_revision: Union[str, None] = "20260423_merge_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ring-map dispatch fields on tenant (operator base location)
    op.add_column("tenant", sa.Column("base_lat", sa.Float(), nullable=True))
    op.add_column("tenant", sa.Column("base_lng", sa.Float(), nullable=True))
    op.add_column("tenant", sa.Column("ring_radius_km", sa.Integer(), nullable=False, server_default="10"))

    # Public intake job pool (tenant-agnostic, claimed by operators via ring routing)
    op.create_table(
        "intakejob",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("customer_name", sa.String(length=300), nullable=False),
        sa.Column("customer_phone", sa.String(length=80), nullable=True),
        sa.Column("customer_email", sa.String(length=320), nullable=True),
        sa.Column("job_address", sa.String(length=2000), nullable=False),
        sa.Column("job_lat", sa.Float(), nullable=False),
        sa.Column("job_lng", sa.Float(), nullable=False),
        sa.Column("vehicle_make", sa.String(length=120), nullable=True),
        sa.Column("vehicle_model", sa.String(length=120), nullable=True),
        sa.Column("vehicle_year", sa.String(length=10), nullable=True),
        sa.Column("registration_plate", sa.String(length=32), nullable=True),
        sa.Column("description", sa.String(length=4000), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="unclaimed"),
        sa.Column("current_ring", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("ring_escalated_at", sa.DateTime(), nullable=True),
        sa.Column("claimed_by_tenant_id", sa.Uuid(), nullable=True),
        sa.Column("claimed_at", sa.DateTime(), nullable=True),
        sa.Column("resulting_job_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["claimed_by_tenant_id"], ["tenant.id"]),
        sa.ForeignKeyConstraint(["resulting_job_id"], ["autokeyjob.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_intakejob_status"), "intakejob", ["status"], unique=False)
    op.create_index(op.f("ix_intakejob_claimed_by_tenant_id"), "intakejob", ["claimed_by_tenant_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_intakejob_claimed_by_tenant_id"), table_name="intakejob")
    op.drop_index(op.f("ix_intakejob_status"), table_name="intakejob")
    op.drop_table("intakejob")

    op.drop_column("tenant", "ring_radius_km")
    op.drop_column("tenant", "base_lng")
    op.drop_column("tenant", "base_lat")
