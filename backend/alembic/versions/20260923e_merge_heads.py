"""merge the inbound-email-secret branch with the PR #43 migration chain

Revision ID: 20260923e_merge_heads
Revises: 20260923a_inbound_email_secret, 20260923d_invoice_quote_unique
Create Date: 2026-09-23
"""
from typing import Sequence, Union

revision: str = "20260923e_merge_heads"
down_revision: Union[str, Sequence[str], None] = (
    "20260923a_inbound_email_secret",
    "20260923d_invoice_quote_unique",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
