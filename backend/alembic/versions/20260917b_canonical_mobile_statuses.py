"""canonicalise legacy statuses stored on Mobile Services jobs

Revision ID: 20260917b_mobile_statuses
Revises: 20260917a_regional_cockpit
Create Date: 2026-09-17

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260917b_mobile_statuses"
down_revision: Union[str, None] = "20260917a_regional_cockpit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_STATUS_MAP = {
    "awaiting_go_ahead": "quote_sent",
    "go_ahead": "awaiting_booking_confirmation",
    "working_on": "on_site",
    "service": "on_site",
    "awaiting_parts": "booking_on_hold",
    "parts_to_order": "booking_on_hold",
    "sent_to_labanda": "booking_on_hold",
    "quoted_by_labanda": "booking_on_hold",
    "at_third_party_for_quoting": "booking_on_hold",
    "third_party_quote_approved": "booking_on_hold",
    "at_third_party_repairer": "booking_on_hold",
    "completed": "work_completed",
    "awaiting_collection": "work_completed",
    "collected": "invoice_paid",
}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "autokeyjob" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("autokeyjob")}
    if "work_completed_at" in columns:
        bind.execute(
            sa.text(
                "UPDATE autokeyjob "
                "SET work_completed_at = COALESCE(work_completed_at, updated_at, created_at) "
                "WHERE status IN ('completed', 'awaiting_collection', 'collected')"
            )
        )

    for legacy, canonical in _STATUS_MAP.items():
        bind.execute(
            sa.text("UPDATE autokeyjob SET status = :canonical WHERE status = :legacy"),
            {"canonical": canonical, "legacy": legacy},
        )


def downgrade() -> None:
    # Canonical statuses are valid application data. Reconstructing the old
    # vocabulary would be lossy, so a downgrade intentionally keeps the data.
    pass
