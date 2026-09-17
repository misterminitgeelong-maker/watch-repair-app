"""Mobile Services cockpit: fold duplicate booking statuses, add tenant catalogue + target settings

Revision ID: 20260918a_mobile_ops_cockpit
Revises: 20260917b_mobile_statuses
Create Date: 2026-09-18

Two booking flows had grown parallel stored values for the same stage
(``pending_booking``/``booked`` from the booking-SMS flow, ``job_delayed`` and
``booking_completed`` from early dispatch work). ``app.auto_key_status`` keeps
every one of them readable as an alias, so this rewrite is a tidy-up, not a
prerequisite: an un-migrated deployment still presents and reports correctly.

Two nullable tenant columns back owner-controlled settings:

* ``mobile_catalogue_categories_json`` — JSON list of POS catalogue categories
  the shop sells (``vehicle_key``, ``general_service``, ``garage_door``).
  NULL means the default (vehicle key + general service).
* ``mobile_weekly_target_cents`` — weekly collected-cash target for the
  operations cockpit. NULL means no target is set.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260918a_mobile_ops_cockpit"
down_revision: Union[str, None] = "20260917b_mobile_statuses"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_STATUS_MAP = {
    "pending_booking": "awaiting_booking_confirmation",
    "booked": "booking_confirmed",
    "job_delayed": "booking_on_hold",
    "booking_completed": "work_completed",
}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "autokeyjob" in tables:
        columns = {column["name"] for column in inspector.get_columns("autokeyjob")}
        if "work_completed_at" in columns:
            bind.execute(
                sa.text(
                    "UPDATE autokeyjob "
                    "SET work_completed_at = COALESCE(work_completed_at, updated_at, created_at) "
                    "WHERE status = 'booking_completed'"
                )
            )
        for legacy, canonical in _STATUS_MAP.items():
            bind.execute(
                sa.text("UPDATE autokeyjob SET status = :canonical WHERE status = :legacy"),
                {"canonical": canonical, "legacy": legacy},
            )

    if "tenant" in tables:
        tenant_columns = {column["name"] for column in inspector.get_columns("tenant")}
        with op.batch_alter_table("tenant") as batch:
            if "mobile_catalogue_categories_json" not in tenant_columns:
                batch.add_column(sa.Column("mobile_catalogue_categories_json", sa.String(), nullable=True))
            if "mobile_weekly_target_cents" not in tenant_columns:
                batch.add_column(sa.Column("mobile_weekly_target_cents", sa.Integer(), nullable=True))


def downgrade() -> None:
    # The canonical statuses remain valid application data (see 20260917b), so
    # only the new tenant columns are removed.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "tenant" not in inspector.get_table_names():
        return
    tenant_columns = {column["name"] for column in inspector.get_columns("tenant")}
    with op.batch_alter_table("tenant") as batch:
        if "mobile_weekly_target_cents" in tenant_columns:
            batch.drop_column("mobile_weekly_target_cents")
        if "mobile_catalogue_categories_json" in tenant_columns:
            batch.drop_column("mobile_catalogue_categories_json")
