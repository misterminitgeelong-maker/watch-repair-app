"""delete-linked-rows rules on foreign keys to tenant

Deleting a shop relied on the app deleting ~80 tables in the right order
(and retrying when it guessed wrong). The database now does it: every
foreign key to ``tenant`` gets an ON DELETE rule matching the models:

* the shop's own rows (``tenant_id`` NOT NULL) and rows that only mean
  something with that shop (booking requests, suburb routes, KPI snapshots)
  -> CASCADE
* optional pointers from other shops' / the network's rows (HQ default and
  escalation site, referring shop, uploader, parent event log) -> SET NULL

``current_operator_tenant_id`` and ``claimed_by_tenant_id`` keep NO ACTION;
the delete endpoint removes those rows explicitly first.

Postgres only: SQLite can't alter constraints, and dev/test SQLite databases
are built from the models (which carry the same rules).

Each constraint is re-added NOT VALID and then validated, so the long scan
doesn't hold an exclusive lock.

Revision ID: 20260923j_tenant_fk_on_delete
Revises: 20260923i_job_customer_note
Create Date: 2026-09-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260923j_tenant_fk_on_delete"
down_revision: Union[str, None] = "20260923i_job_customer_note"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CASCADE_COLUMNS = {"tenant_id", "target_tenant_id", "requesting_tenant_id", "target_operator_tenant_id", "operator_tenant_id"}
_SET_NULL_COLUMNS = {"mobile_lead_default_tenant_id", "mobile_lead_escalation_tenant_id", "referring_shop_tenant_id", "uploaded_by_tenant_id"}

_FK_QUERY = sa.text(
    """
    SELECT con.conname, rel.relname, att.attname, att.attnotnull, con.confdeltype
    FROM pg_constraint con
    JOIN pg_class rel ON rel.oid = con.conrelid
    JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
    JOIN pg_class ref ON ref.oid = con.confrelid
    JOIN pg_attribute att ON att.attrelid = con.conrelid AND att.attnum = con.conkey[1]
    WHERE con.contype = 'f'
      AND nsp.nspname = current_schema()
      AND ref.relname = 'tenant'
      AND array_length(con.conkey, 1) = 1
    """
)


def _rule_for(column: str, not_null: bool) -> str | None:
    if column in _CASCADE_COLUMNS:
        return "CASCADE" if (not_null or column != "tenant_id") else "SET NULL"
    if column in _SET_NULL_COLUMNS:
        return "SET NULL"
    return None


def _rewrite(rule_for) -> None:
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return
    for conname, table, column, not_null, current in conn.execute(_FK_QUERY).fetchall():
        rule = rule_for(column, bool(not_null))
        if rule is None:
            continue
        wanted = {"CASCADE": "c", "SET NULL": "n", "NO ACTION": "a"}[rule]
        if current == wanted:
            continue
        op.execute(f'ALTER TABLE "{table}" DROP CONSTRAINT "{conname}"')
        op.execute(
            f'ALTER TABLE "{table}" ADD CONSTRAINT "{conname}" FOREIGN KEY ("{column}") '
            f'REFERENCES tenant (id) ON DELETE {rule} NOT VALID'
        )
        op.execute(f'ALTER TABLE "{table}" VALIDATE CONSTRAINT "{conname}"')


def upgrade() -> None:
    _rewrite(_rule_for)


def downgrade() -> None:
    _rewrite(lambda column, not_null: "NO ACTION" if _rule_for(column, not_null) else None)
