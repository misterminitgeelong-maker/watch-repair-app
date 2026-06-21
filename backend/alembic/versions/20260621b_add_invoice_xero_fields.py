"""add xero sync fields to repair invoice

Brings the core watch/shoe repair Invoice table to parity with auto-key and
customer-account invoices so it can sync to Xero.

Revision ID: 20260621b_invoice_xero
Revises: 20260621_aki_invoice_uniq
Create Date: 2026-06-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260621b_invoice_xero"
down_revision: Union[str, None] = "20260621_aki_invoice_uniq"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("invoice", sa.Column("xero_invoice_id", sa.String(), nullable=True))
    op.add_column("invoice", sa.Column("xero_sync_status", sa.String(), nullable=True))
    op.add_column("invoice", sa.Column("xero_sync_error", sa.String(), nullable=True))
    op.add_column("invoice", sa.Column("xero_synced_at", sa.DateTime(), nullable=True))
    op.create_index("ix_invoice_xero_invoice_id", "invoice", ["xero_invoice_id"])


def downgrade() -> None:
    op.drop_index("ix_invoice_xero_invoice_id", table_name="invoice")
    op.drop_column("invoice", "xero_synced_at")
    op.drop_column("invoice", "xero_sync_error")
    op.drop_column("invoice", "xero_sync_status")
    op.drop_column("invoice", "xero_invoice_id")
