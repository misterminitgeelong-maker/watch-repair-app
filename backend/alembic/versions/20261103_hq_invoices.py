"""HQ bundled invoices and per-HQ billing settings

Adds hqinvoice (one frozen monthly invoice per HQ) and the add-on / billing
email / Stripe customer columns on parentaccount.

Revision ID: 20261103_hq_invoices
Revises: 20261101_engraving_events
Create Date: 2026-11-03

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261103_hq_invoices"
down_revision: Union[str, None] = "20261101_engraving_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("parentaccount", sa.Column("billing_routing_addon", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("parentaccount", sa.Column("billing_prospecting_addon", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("parentaccount", sa.Column("billing_email", sa.String(), nullable=True))
    op.add_column("parentaccount", sa.Column("stripe_customer_id", sa.String(), nullable=True))
    op.create_index("ix_parentaccount_stripe_customer_id", "parentaccount", ["stripe_customer_id"])
    op.create_table(
        "hqinvoice",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("parent_account_id", sa.Uuid(), sa.ForeignKey("parentaccount.id", ondelete="CASCADE"), nullable=False),
        sa.Column("billing_month", sa.Date(), nullable=False),
        sa.Column("invoice_number", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column("snapshot_json", sa.String(), nullable=False, server_default="{}"),
        sa.Column("operator_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("subtotal_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("gst_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="AUD"),
        sa.Column("stripe_invoice_id", sa.String(), nullable=True),
        sa.Column("stripe_hosted_url", sa.String(), nullable=True),
        sa.Column("stripe_pdf_url", sa.String(), nullable=True),
        sa.Column("issued_at", sa.DateTime(), nullable=True),
        sa.Column("due_at", sa.DateTime(), nullable=True),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("parent_account_id", "billing_month", name="uq_hqinvoice_parent_month"),
    )
    op.create_index("ix_hqinvoice_parent_account_id", "hqinvoice", ["parent_account_id"])
    op.create_index("ix_hqinvoice_invoice_number", "hqinvoice", ["invoice_number"])
    op.create_index("ix_hqinvoice_status", "hqinvoice", ["status"])
    op.create_index("ix_hqinvoice_stripe_invoice_id", "hqinvoice", ["stripe_invoice_id"])


def downgrade() -> None:
    op.drop_table("hqinvoice")
    op.drop_index("ix_parentaccount_stripe_customer_id", table_name="parentaccount")
    for c in ("stripe_customer_id", "billing_email", "billing_prospecting_addon", "billing_routing_addon"):
        op.drop_column("parentaccount", c)
