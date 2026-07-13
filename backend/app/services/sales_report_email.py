"""Scheduled weekly/monthly sales-by-category report emails.

Runs from the in-app scheduler (see main.py). Idempotent per user/period via
UserNotificationPreference.last_{weekly,monthly}_sales_report_sent_at — running
this more than once within the same ISO week/month is a no-op for that user.

Each report covers the most recently *completed* week (Mon-Sun) or calendar
month, generated from the same rows the manual /export/sales CSV would return.
"""
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from sqlmodel import Session, select

from .. import email_client
from ..models import Tenant, User, UserNotificationPreference

logger = logging.getLogger(__name__)

PeriodKind = Literal["week", "month"]
_PERIOD_LABELS: dict[PeriodKind, str] = {"week": "Weekly", "month": "Monthly"}


def _previous_period_bounds(period: PeriodKind, today: date) -> tuple[datetime, datetime, str, str]:
    """Bounds for the most recently completed week/month relative to today."""
    from ..report_periods import resolve_period_bounds

    if period == "week":
        reference = today - timedelta(days=7)
    else:
        reference = today.replace(day=1) - timedelta(days=1)  # any day in the previous month
    return resolve_period_bounds(period, reference)


def _is_due(last_sent_at: datetime | None, period: PeriodKind, today: date) -> bool:
    if last_sent_at is None:
        return True
    last_sent_date = last_sent_at.astimezone(timezone.utc).date() if last_sent_at.tzinfo else last_sent_at.date()
    if period == "week":
        return last_sent_date.isocalendar()[:2] != today.isocalendar()[:2]
    return (last_sent_date.year, last_sent_date.month) != (today.year, today.month)


def _shop_name(session: Session, cache: dict[UUID, str], tenant_id: UUID) -> str:
    if tenant_id not in cache:
        tenant = session.get(Tenant, tenant_id)
        cache[tenant_id] = (tenant.name if tenant else None) or "Your repair shop"
    return cache[tenant_id]


def _send_one_report(session: Session, tenant_id: UUID, to_email: str, shop_name: str, period: PeriodKind) -> bool:
    from ..routes.reports import _build_sales_csv_bytes, _compute_category_summary

    start_dt, end_dt, start_ymd, end_ymd = _previous_period_bounds(period, datetime.now(timezone.utc).date())
    category_summary = _compute_category_summary(session, tenant_id, start_dt, end_dt)
    csv_bytes = _build_sales_csv_bytes(session, tenant_id, "all", start_dt, end_dt)
    sent, _err = email_client.send_sales_report_email(
        to_email=to_email,
        shop_name=shop_name,
        period_label=_PERIOD_LABELS[period],
        period_start=start_ymd,
        period_end=end_ymd,
        category_summary=category_summary,
        csv_bytes=csv_bytes,
        csv_filename=f"sales-report-{start_ymd}_{end_ymd}.csv",
    )
    return sent


def send_due_sales_report_emails(session: Session, tenant_id: UUID | None = None) -> dict[str, int]:
    """Send all due weekly/monthly sales report emails. Caller-agnostic: used by
    the in-app scheduler (all tenants) and can be pointed at one tenant for tests."""
    now = datetime.now(timezone.utc)
    today = now.date()
    shop_names: dict[UUID, str] = {}
    summary = {"weekly_sent": 0, "monthly_sent": 0, "skipped": 0}

    query = select(UserNotificationPreference).where(
        (UserNotificationPreference.email_weekly_sales_report.is_(True))
        | (UserNotificationPreference.email_monthly_sales_report.is_(True))
    )
    if tenant_id:
        query = query.where(UserNotificationPreference.tenant_id == tenant_id)

    for pref in session.exec(query).all():
        user = session.get(User, pref.user_id)
        if not user or not user.is_active or not (user.email or "").strip():
            continue
        shop_name = _shop_name(session, shop_names, pref.tenant_id)

        if pref.email_weekly_sales_report and _is_due(pref.last_weekly_sales_report_sent_at, "week", today):
            sent = _send_one_report(session, pref.tenant_id, user.email, shop_name, "week")
            pref.last_weekly_sales_report_sent_at = now
            session.add(pref)
            summary["weekly_sent" if sent else "skipped"] += 1

        if pref.email_monthly_sales_report and _is_due(pref.last_monthly_sales_report_sent_at, "month", today):
            sent = _send_one_report(session, pref.tenant_id, user.email, shop_name, "month")
            pref.last_monthly_sales_report_sent_at = now
            session.add(pref)
            summary["monthly_sent" if sent else "skipped"] += 1

    session.commit()
    return summary
