"""add prospectlead table for tenant-scoped prospect pipeline

Revision ID: 20260421_prospect_lead
Revises: 20260415_queue_day
Create Date: 2026-04-21

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260421_prospect_lead"
down_revision: Union[str, None] = "20260415_queue_day"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "prospectlead",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("place_id", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("address", sa.String(), nullable=True),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("website", sa.String(), nullable=True),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("state_code", sa.String(), nullable=True),
        sa.Column("suburb_name", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="new"),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("next_follow_up_on", sa.Date(), nullable=True),
        sa.Column("customer_account_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.ForeignKeyConstraint(["customer_account_id"], ["customeraccount.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "place_id", name="uq_prospectlead_tenant_place"),
    )
    op.create_index(op.f("ix_prospectlead_tenant_id"), "prospectlead", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_prospectlead_place_id"), "prospectlead", ["place_id"], unique=False)
    op.create_index(op.f("ix_prospectlead_status"), "prospectlead", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_prospectlead_status"), table_name="prospectlead")
    op.drop_index(op.f("ix_prospectlead_place_id"), table_name="prospectlead")
    op.drop_index(op.f("ix_prospectlead_tenant_id"), table_name="prospectlead")
    op.drop_table("prospectlead")
