"""drop smslog foreign keys to the job tables

The SMS audit row is written in its own transaction before the provider call
(``sms._begin_sms_log``) so the attempt is recorded even if the caller later
rolls back. That independent commit cannot see the caller's uncommitted job, so
the foreign key fires and every send raises IntegrityError on a database that
enforces foreign keys. SQLite does not enforce them by default, which is why
this only surfaced once CI moved to Postgres.

Dropping the three job foreign keys is the right fix rather than reordering the
write: an audit row should be able to precede its subject and outlive it. It
also removes a pre-existing hazard, since ``routes/repair_jobs.py`` deletes
repair jobs and that delete would fail for any job carrying SMS logs.

The columns and their indexes stay. ``tenant_id`` keeps its foreign key — a
tenant always exists before a message is sent.

Revision ID: 20260915_smslog_fk
Revises: 20260914c_offline_replay
Create Date: 2026-09-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260915_smslog_fk"
down_revision: Union[str, None] = "20260914c_offline_replay"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (column, referenced table) for the constraints this migration manages.
_JOB_FKS = (
    ("repair_job_id", "repairjob"),
    ("shoe_repair_job_id", "shoerepairjob"),
    ("auto_key_job_id", "autokeyjob"),
)


def _named_fks(inspector, table: str) -> dict[str, str]:
    """Map constrained column -> constraint name for the table's foreign keys."""
    found: dict[str, str] = {}
    for fk in inspector.get_foreign_keys(table):
        name = fk.get("name")
        cols = fk.get("constrained_columns") or []
        if name and len(cols) == 1:
            found[cols[0]] = name
    return found


def upgrade() -> None:
    bind = op.get_bind()
    # SQLite cannot drop a constraint in place; the table is rebuilt by batch
    # mode, and it does not enforce these keys anyway.
    if bind.dialect.name == "sqlite":
        return

    inspector = sa.inspect(bind)
    if "smslog" not in inspector.get_table_names():
        return

    existing = _named_fks(inspector, "smslog")
    for column, _referenced in _JOB_FKS:
        name = existing.get(column)
        if name:
            op.drop_constraint(name, "smslog", type_="foreignkey")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return

    inspector = sa.inspect(bind)
    if "smslog" not in inspector.get_table_names():
        return

    existing = _named_fks(inspector, "smslog")
    for column, referenced in _JOB_FKS:
        if column in existing:
            continue
        op.create_foreign_key(
            f"smslog_{column}_fkey",
            "smslog",
            referenced,
            [column],
            ["id"],
        )
