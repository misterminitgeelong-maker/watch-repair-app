"""ensure legacy columns present (remove need for runtime patch)

Revision ID: h3c4d5e6f7a8b
Revises: g2b3c4d5e6f7
Create Date: 2026-03-17 12:00:00.000000

Adds any columns that were previously added at runtime by database._ensure_runtime_columns()
so that the runtime patch can be removed. Idempotent: only adds columns that are missing.
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect, text


revision: str = "h3c4d5e6f7a8b"
down_revision: Union[str, None] = "g2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    table_names = inspector.get_table_names()

    if "repairjob" in table_names:
        repairjob_cols = {c["name"] for c in inspector.get_columns("repairjob")}
        if "salesperson" not in repairjob_cols:
            op.execute(text("ALTER TABLE repairjob ADD COLUMN salesperson VARCHAR"))
        if "collection_date" not in repairjob_cols:
            op.execute(text("ALTER TABLE repairjob ADD COLUMN collection_date DATE"))
        if "deposit_cents" not in repairjob_cols:
            op.execute(text("ALTER TABLE repairjob ADD COLUMN deposit_cents INTEGER NOT NULL DEFAULT 0"))
        if "cost_cents" not in repairjob_cols:
            op.execute(text("ALTER TABLE repairjob ADD COLUMN cost_cents INTEGER NOT NULL DEFAULT 0"))
        if "pre_quote_cents" not in repairjob_cols:
            op.execute(text("ALTER TABLE repairjob ADD COLUMN pre_quote_cents INTEGER NOT NULL DEFAULT 0"))
        if "status_token" not in repairjob_cols:
            op.execute(text("ALTER TABLE repairjob ADD COLUMN status_token VARCHAR"))
            op.execute(text("UPDATE repairjob SET status_token = id WHERE status_token IS NULL OR status_token = ''"))

    if "customer" in table_names:
        customer_cols = {c["name"] for c in inspector.get_columns("customer")}
        if "address" not in customer_cols:
            op.execute(text("ALTER TABLE customer ADD COLUMN address VARCHAR"))


def downgrade() -> None:
    # Do not drop columns to avoid data loss; these are now part of the schema.
    pass
