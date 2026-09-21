"""Weekly Mobile Services network scorecard — thin wrapper over the KPI engine.

The live board, daily 21:00 freeze and Saturday 23:05 CSV live in
``mobile_network_kpis`` / ``services.mobile_kpi_close``. This module keeps the
older function names used by tests and the existing send-now endpoint.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlmodel import Session, select

from ..mobile_network_kpis import (
    OperatorKpiRow,
    build_network_kpis,
    last_completed_operating_week,
)
from ..models import ParentAccount
from .mobile_kpi_close import run_mobile_kpi_close, send_weekly_now

logger = logging.getLogger(__name__)


@dataclass
class OperatorWeeklyStats:
    operator_tenant_id: UUID
    operator_name: str
    customers_count: int
    jobs_count: int
    sales_cents: int
    prior_week_sales_cents: int
    prior_week_jobs_count: int
    enquiries_not_actioned: int


def _row_to_legacy(row: OperatorKpiRow) -> OperatorWeeklyStats:
    return OperatorWeeklyStats(
        operator_tenant_id=row.operator_tenant_id,
        operator_name=row.operator_name,
        customers_count=row.customers_count,
        jobs_count=row.jobs_created,
        sales_cents=row.sales_cents,
        prior_week_sales_cents=row.prior_sales_cents,
        prior_week_jobs_count=row.prior_jobs_created,
        enquiries_not_actioned=row.enquiries_not_actioned,
    )


def _previous_week_bounds(today) -> tuple[datetime, datetime, str, str]:
    """Last completed operating week as of UTC midnight on ``today``."""
    at = datetime(today.year, today.month, today.day, tzinfo=timezone.utc)
    return last_completed_operating_week(at)


def build_mobile_weekly_report(
    session: Session,
    *,
    parent: ParentAccount,
    start_dt: datetime,
    end_dt: datetime,
) -> list[OperatorWeeklyStats]:
    prior_start = start_dt - timedelta(days=7)
    prior_end = end_dt - timedelta(days=7)
    report = build_network_kpis(
        session,
        parent,
        start_dt,
        end_dt,
        prior_start=prior_start,
        prior_end=prior_end,
    )
    return [_row_to_legacy(row) for row in report.operators]


def send_weekly_report_for_parent(session: Session, parent: ParentAccount) -> bool:
    """Compile + attempt email for the last completed operating week. Commits."""
    snap = send_weekly_now(session, parent)
    return snap.emailed_at is not None


def send_due_mobile_weekly_reports(session: Session, parent_id: UUID | None = None) -> dict[str, int]:
    """Sweep-compatible wrapper: runs the close-of-trade compile for one or all parents."""
    return run_mobile_kpi_close(session, parent_id=parent_id)
