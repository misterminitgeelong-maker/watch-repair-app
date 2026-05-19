"""Add Xero OAuth fields on tenant and sync fields on autokeyinvoice.

Revision ID: 20260519_xero
Revises: 20260511_job_fields_v2
Create Date: 2026-05-19

"""
from alembic import op
import sqlalchemy as sa

revision = "20260519_xero"
down_revision = "20260511_job_fields_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenant", sa.Column("xero_tenant_id", sa.Text(), nullable=True))
    op.add_column("tenant", sa.Column("xero_access_token", sa.Text(), nullable=True))
    op.add_column("tenant", sa.Column("xero_refresh_token", sa.Text(), nullable=True))
    op.add_column("tenant", sa.Column("xero_token_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tenant", sa.Column("xero_connection_status", sa.Text(), nullable=True))
    op.add_column("tenant", sa.Column("xero_default_sales_account_code", sa.Text(), nullable=True))
    op.add_column("tenant", sa.Column("xero_default_tax_type", sa.Text(), nullable=True))

    op.add_column("autokeyinvoice", sa.Column("xero_invoice_id", sa.Text(), nullable=True))
    op.add_column("autokeyinvoice", sa.Column("xero_sync_status", sa.Text(), nullable=True))
    op.add_column("autokeyinvoice", sa.Column("xero_sync_error", sa.Text(), nullable=True))
    op.add_column("autokeyinvoice", sa.Column("xero_synced_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_autokeyinvoice_xero_invoice_id", "autokeyinvoice", ["xero_invoice_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_autokeyinvoice_xero_invoice_id", table_name="autokeyinvoice")
    op.drop_column("autokeyinvoice", "xero_synced_at")
    op.drop_column("autokeyinvoice", "xero_sync_error")
    op.drop_column("autokeyinvoice", "xero_sync_status")
    op.drop_column("autokeyinvoice", "xero_invoice_id")
    op.drop_column("tenant", "xero_default_tax_type")
    op.drop_column("tenant", "xero_default_sales_account_code")
    op.drop_column("tenant", "xero_connection_status")
    op.drop_column("tenant", "xero_token_expires_at")
    op.drop_column("tenant", "xero_refresh_token")
    op.drop_column("tenant", "xero_access_token")
    op.drop_column("tenant", "xero_tenant_id")
