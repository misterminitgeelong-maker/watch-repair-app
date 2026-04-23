"""add prospect_lead table

Revision ID: 20260425_prospect_leads
Revises: 20260424_intake_dispatch
Create Date: 2026-04-25
"""
from alembic import op
import sqlalchemy as sa

revision = "20260425_prospect_leads"
down_revision = "20260424_intake_dispatch"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "prospectlead",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("place_id", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("website", sa.Text(), nullable=True),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("review_count", sa.Integer(), nullable=True),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("state_code", sa.Text(), nullable=True),
        sa.Column("contact_name", sa.Text(), nullable=True),
        sa.Column("contact_email", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="new"),
        sa.Column("visit_scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_prospectlead_tenant_id", "prospectlead", ["tenant_id"])
    op.create_index("ix_prospectlead_status", "prospectlead", ["status"])


def downgrade():
    op.drop_index("ix_prospectlead_status", table_name="prospectlead")
    op.drop_index("ix_prospectlead_tenant_id", table_name="prospectlead")
    op.drop_table("prospectlead")
