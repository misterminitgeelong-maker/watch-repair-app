"""add xero sync fields to customer account invoice

Revision ID: 20260530b_cai_xero
Revises: 20260530_work_completed_at
Create Date: 2026-05-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260530b_cai_xero"
down_revision: Union[str, None] = "20260530_work_completed_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("customeraccountinvoice", sa.Column("xero_invoice_id", sa.String(), nullable=True))
    op.add_column("customeraccountinvoice", sa.Column("xero_sync_status", sa.String(), nullable=True))
    op.add_column("customeraccountinvoice", sa.Column("xero_sync_error", sa.String(), nullable=True))
    op.add_column("customeraccountinvoice", sa.Column("xero_synced_at", sa.DateTime(), nullable=True))
    op.create_index(
        "ix_customeraccountinvoice_xero_invoice_id",
        "customeraccountinvoice",
        ["xero_invoice_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_customeraccountinvoice_xero_invoice_id", table_name="customeraccountinvoice")
    op.drop_column("customeraccountinvoice", "xero_synced_at")
    op.drop_column("customeraccountinvoice", "xero_sync_error")
    op.drop_column("customeraccountinvoice", "xero_sync_status")
    op.drop_column("customeraccountinvoice", "xero_invoice_id")
