"""backfill foreign keys into the shoe tables on databases built from scratch

The shoe tables (shoe, shoerepairjob, ...) were historically created by runtime
create_all and only added to the migration chain in 20260612_reconcile_shoe_tables.
Three earlier migrations add foreign keys *into* those tables; on a database
built purely from migrations the tables do not exist yet at that point, so those
migrations now skip the FK. This revision adds whichever of them are missing.

Every operation is existence-guarded, so on production (where the tables
pre-dated the referencing migrations and the FKs were created then) this is a
no-op. SQLite is skipped entirely: it cannot ADD CONSTRAINT and never enforced
these FKs anyway.

Revision ID: 20260914b_shoe_fk_backfill
Revises: 20260914a_stripe_webhook_event
Create Date: 2026-09-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260914b_shoe_fk_backfill"
down_revision: Union[str, None] = "20260914a_stripe_webhook_event"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (constraint name, source table, source column, referred table)
_FOREIGN_KEYS = [
    ("fk_attachment_shoe_repair_job_id", "attachment", "shoe_repair_job_id", "shoerepairjob"),
    ("fk_shoerepairjobshoe_job_id", "shoerepairjobshoe", "shoe_repair_job_id", "shoerepairjob"),
    ("fk_shoerepairjobshoe_shoe_id", "shoerepairjobshoe", "shoe_id", "shoe"),
    ("fk_jobmessage_shoe_repair_job_id", "jobmessage", "shoe_repair_job_id", "shoerepairjob"),
    ("fk_smslog_shoe_repair_job_id", "smslog", "shoe_repair_job_id", "shoerepairjob"),
]


def _fk_exists(inspector, table: str, column: str, referred_table: str) -> bool:
    return any(
        fk["constrained_columns"] == [column] and fk["referred_table"] == referred_table
        for fk in inspector.get_foreign_keys(table)
    )


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return
    inspector = sa.inspect(bind)
    for name, table, column, referred_table in _FOREIGN_KEYS:
        if not inspector.has_table(table) or not inspector.has_table(referred_table):
            continue
        if _fk_exists(inspector, table, column, referred_table):
            continue
        op.create_foreign_key(name, table, referred_table, [column], ["id"])


def downgrade() -> None:
    # The FKs also exist on databases that never needed this backfill, so
    # dropping them here would change production; leave them in place.
    pass
