"""mobile services pricing catalogue tables and autokeyjob pricing fields

Revision ID: 20260601_mobile_services_pricing
Revises: 20260531_refresh_session
Create Date: 2026-06-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260601_mobile_services_pricing"
down_revision: Union[str, None] = "20260531_refresh_session"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Skip if Supabase already provisioned these catalogue tables.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    if "oem_key_pricing" not in existing:
        op.create_table(
            "oem_key_pricing",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("make", sa.String(), nullable=False),
            sa.Column("model_variant", sa.String(), nullable=True),
            sa.Column("job_type", sa.String(), nullable=False),
            sa.Column("chip_type", sa.String(), nullable=True),
            sa.Column("key_type", sa.String(), nullable=True),
            sa.Column("service_location", sa.String(), nullable=True),
            sa.Column("tool_required", sa.String(), nullable=True),
            sa.Column("retail_price", sa.Float(), nullable=True),
            sa.Column("callout_inclusive", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("notes", sa.String(), nullable=True),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_oem_key_pricing_make", "oem_key_pricing", ["make"])

    if "service_pricing" not in existing:
        op.create_table(
            "service_pricing",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("category", sa.String(), nullable=False),
            sa.Column("service_name", sa.String(), nullable=False),
            sa.Column("unit", sa.String(), nullable=True),
            sa.Column("retail_price", sa.Float(), nullable=True),
            sa.Column("callout_inclusive", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("notes", sa.String(), nullable=True),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_service_pricing_category", "service_pricing", ["category"])

    if "garage_servicing_pricing" not in existing:
        op.create_table(
            "garage_servicing_pricing",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("service_name", sa.String(), nullable=False),
            sa.Column("description", sa.String(), nullable=True),
            sa.Column("part_cost_notes", sa.String(), nullable=True),
            sa.Column("labour_time", sa.String(), nullable=True),
            sa.Column("retail_price", sa.Float(), nullable=False),
            sa.Column("callout_inclusive", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("notes", sa.String(), nullable=True),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_garage_servicing_pricing_service_name", "garage_servicing_pricing", ["service_name"])

    autokey_cols = {c["name"] for c in inspector.get_columns("autokeyjob")}
    if "pricing_ref_id" not in autokey_cols:
        op.add_column("autokeyjob", sa.Column("pricing_ref_id", sa.Uuid(), nullable=True))
        op.create_index("ix_autokeyjob_pricing_ref_id", "autokeyjob", ["pricing_ref_id"])
    if "pricing_type" not in autokey_cols:
        op.add_column("autokeyjob", sa.Column("pricing_type", sa.String(length=32), nullable=True))
    if "quoted_price" not in autokey_cols:
        op.add_column("autokeyjob", sa.Column("quoted_price", sa.Float(), nullable=True))
    if "callout_inclusive" not in autokey_cols:
        op.add_column("autokeyjob", sa.Column("callout_inclusive", sa.Boolean(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    autokey_cols = {c["name"] for c in inspector.get_columns("autokeyjob")}
    if "pricing_ref_id" in autokey_cols:
        op.drop_index("ix_autokeyjob_pricing_ref_id", table_name="autokeyjob")
        op.drop_column("autokeyjob", "pricing_ref_id")
    if "callout_inclusive" in autokey_cols:
        op.drop_column("autokeyjob", "callout_inclusive")
    if "quoted_price" in autokey_cols:
        op.drop_column("autokeyjob", "quoted_price")
    if "pricing_type" in autokey_cols:
        op.drop_column("autokeyjob", "pricing_type")

    existing = set(inspector.get_table_names())
    if "garage_servicing_pricing" in existing:
        op.drop_index("ix_garage_servicing_pricing_service_name", table_name="garage_servicing_pricing")
        op.drop_table("garage_servicing_pricing")
    if "service_pricing" in existing:
        op.drop_index("ix_service_pricing_category", table_name="service_pricing")
        op.drop_table("service_pricing")
    if "oem_key_pricing" in existing:
        op.drop_index("ix_oem_key_pricing_make", table_name="oem_key_pricing")
        op.drop_table("oem_key_pricing")
