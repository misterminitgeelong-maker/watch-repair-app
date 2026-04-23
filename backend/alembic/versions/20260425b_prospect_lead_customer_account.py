"""add customer_account_id to prospect_lead

Revision ID: 20260425b_prospect_lead_customer_account
Revises: 20260425_prospect_leads
Create Date: 2026-04-25
"""
from alembic import op
import sqlalchemy as sa

revision = "20260425b_prospect_lead_customer_account"
down_revision = "20260425_prospect_leads"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "prospectlead",
        sa.Column("customer_account_id", sa.UUID(), nullable=True),
    )
    op.create_index(
        "ix_prospectlead_customer_account_id",
        "prospectlead",
        ["customer_account_id"],
    )


def downgrade():
    op.drop_index("ix_prospectlead_customer_account_id", table_name="prospectlead")
    op.drop_column("prospectlead", "customer_account_id")
