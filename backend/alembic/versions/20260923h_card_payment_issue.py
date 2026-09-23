"""cardpaymentissue: unmatched card payments staff can refund or apply

Revision ID: 20260923h_card_payment_issue
Revises: 20260923g_tenant_is_minit
Create Date: 2026-09-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260923h_card_payment_issue"
down_revision: Union[str, None] = "20260923g_tenant_is_minit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cardpaymentissue",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("auto_key_invoice_id", sa.Uuid(), nullable=True),
        sa.Column("checkout_session_id", sa.String(length=255), nullable=False),
        sa.Column("payment_intent_id", sa.String(length=255), nullable=True),
        sa.Column("stripe_account_id", sa.String(length=255), nullable=True),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("problem", sa.String(length=300), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.ForeignKeyConstraint(["auto_key_invoice_id"], ["autokeyinvoice.id"]),
        sa.ForeignKeyConstraint(["resolved_by_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("checkout_session_id"),
    )
    op.create_index("ix_cardpaymentissue_tenant_id", "cardpaymentissue", ["tenant_id"])
    op.create_index("ix_cardpaymentissue_auto_key_invoice_id", "cardpaymentissue", ["auto_key_invoice_id"])
    op.create_index("ix_cardpaymentissue_status", "cardpaymentissue", ["status"])


def downgrade() -> None:
    op.drop_index("ix_cardpaymentissue_status", table_name="cardpaymentissue")
    op.drop_index("ix_cardpaymentissue_auto_key_invoice_id", table_name="cardpaymentissue")
    op.drop_index("ix_cardpaymentissue_tenant_id", table_name="cardpaymentissue")
    op.drop_table("cardpaymentissue")
