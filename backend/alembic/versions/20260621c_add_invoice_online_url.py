"""add xero_online_invoice_url to repair invoice

Stores the Xero-hosted "view & pay online" URL so the app can show customers a
pay link (and include it in the invoice email) that routes payment through Xero.

Revision ID: 20260621c_invoice_payurl
Revises: 20260621b_invoice_xero
Create Date: 2026-06-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260621c_invoice_payurl"
down_revision: Union[str, None] = "20260621b_invoice_xero"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("invoice", sa.Column("xero_online_invoice_url", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("invoice", "xero_online_invoice_url")
