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

# Mirrors app.phone_utils.normalize_phone for a single-statement Postgres backfill.
_PG_BACKFILL = """
WITH src AS (
    SELECT id, regexp_replace(btrim(phone), '[^0-9]', '', 'g') AS d0
    FROM customer
    WHERE phone IS NOT NULL AND btrim(phone) <> ''
),
step1 AS (
    SELECT id,
        CASE
            WHEN d0 LIKE '61%' AND char_length(d0) >= 11 THEN '0' || substr(d0, 3, 9)
            ELSE d0
        END AS d1
    FROM src
),
step2 AS (
    SELECT id,
        CASE
            WHEN char_length(d1) = 9 AND substr(d1, 1, 1) IN ('3', '4') THEN '0' || d1
            ELSE d1
        END AS d2
    FROM step1
),
step3 AS (
    SELECT id,
        CASE
            WHEN char_length(d2) > 10 THEN right(d2, 10)
            ELSE d2
        END AS d3
    FROM step2
)
UPDATE customer AS c
SET phone_normalized = CASE WHEN char_length(s.d3) < 8 THEN NULL ELSE s.d3 END
FROM step3 AS s
WHERE c.id = s.id
"""


def upgrade() -> None:
    op.add_column("customer", sa.Column("phone_normalized", sa.String(length=20), nullable=True))

    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        conn.execute(sa.text(_PG_BACKFILL))
    else:
        from app.phone_utils import normalize_phone

        rows = conn.execute(sa.text("SELECT id, phone FROM customer")).fetchall()
        payload = [
            {"n": normalize_phone(phone or "") if phone else None, "id": row_id}
            for row_id, phone in rows
        ]
        if payload:
            conn.execute(
                sa.text("UPDATE customer SET phone_normalized = :n WHERE id = :id"),
                payload,
            )

    op.create_index("ix_customer_phone_normalized", "customer", ["phone_normalized"])


def downgrade() -> None:
    op.drop_index("ix_customer_phone_normalized", table_name="customer")
    op.drop_column("customer", "phone_normalized")
