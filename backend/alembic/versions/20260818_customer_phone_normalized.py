"""add indexed customer.phone_normalized and backfill

Revision ID: 20260818_phone_normalized
Revises: 20260808_mobile_weekly_report
Create Date: 2026-08-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260818_phone_normalized"
down_revision: Union[str, None] = "20260808_mobile_weekly_report"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("customer", sa.Column("phone_normalized", sa.String(length=20), nullable=True))
    op.create_index("ix_customer_phone_normalized", "customer", ["phone_normalized"])

    from app.phone_utils import normalize_phone

    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, phone FROM customer")).fetchall()
    for row_id, phone in rows:
        normalized = normalize_phone(phone or "") if phone else None
        conn.execute(
            sa.text("UPDATE customer SET phone_normalized = :n WHERE id = :id"),
            {"n": normalized, "id": row_id},
        )


def downgrade() -> None:
    op.drop_index("ix_customer_phone_normalized", table_name="customer")
    op.drop_column("customer", "phone_normalized")
