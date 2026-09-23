"""one watch invoice per quote

Revision ID: 20260923d_invoice_quote_unique
Revises: 20260923c_customer_portal_otp
Create Date: 2026-09-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260923d_invoice_quote_unique"
down_revision: Union[str, None] = "20260923c_customer_portal_otp"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    duplicates = bind.execute(
        sa.text(
            "SELECT quote_id, COUNT(*) FROM invoice WHERE quote_id IS NOT NULL "
            "GROUP BY quote_id HAVING COUNT(*) > 1"
        )
    ).fetchall()
    if duplicates:
        # Don't fail the deploy over history: the app still refuses a second
        # invoice for a quote. Clean these up, then re-run to add the index.
        print(
            f"WARNING: {len(duplicates)} quote(s) already have more than one invoice; "
            "uq_invoice_quote not created. Quote ids: "
            + ", ".join(str(row[0]) for row in duplicates[:20])
        )
        return
    op.create_index("uq_invoice_quote", "invoice", ["quote_id"], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    if "uq_invoice_quote" in {ix["name"] for ix in sa.inspect(bind).get_indexes("invoice")}:
        op.drop_index("uq_invoice_quote", table_name="invoice")
