"""Weekly "mobile services network" scorecard — one row per operator, emailed to
Minit HQ once each week ends. Modelled on Mister Minit's own weekly retail-shop
export (VSWT-WSS): customers, jobs, sales for the completed week, compared to
the week before, plus the email-enquiry backlog from
``minit_email_lead_parser.py`` so a shop that's going unanswered stands out.

Revenue = paid AutoKeyInvoice totals created in the period (matches the
convention already used by ``app/routes/reports.py``'s tenant-level reports —
quoted-but-unpaid work is not counted as "sales").

Opt-in per parent account (``ParentAccount.mobile_weekly_report_opt_in``);
idempotent per ISO week via ``last_mobile_weekly_report_sent_at``, same pattern
as ``services/sales_report_email.py``.
"""

from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlmodel import Session, func, select

from .. import email_client
from ..minit_email_lead_parser import bookable_operators_for_parent, bucket_email_leads_by_operator
from ..models import AutoKeyInvoice, AutoKeyJob, InboundEmail, ParentAccount

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


def _previous_week_bounds(today: "datetime.date") -> tuple[datetime, datetime, str, str]:
    """[Mon, Sun] of the most recently *completed* week, same as sales_report_email.py."""
    from ..report_periods import resolve_period_bounds

    reference = today - timedelta(days=7)
    return resolve_period_bounds("week", reference)


def _week_stats_for_tenant(session: Session, tenant_id: UUID, start_dt: datetime, end_dt: datetime) -> tuple[int, int, int]:
    """(customers_count, jobs_count, sales_cents) for one operator tenant in [start, end]."""
    jobs_count = int(
        session.exec(
            select(func.count())
            .select_from(AutoKeyJob)
            .where(AutoKeyJob.tenant_id == tenant_id)
            .where(AutoKeyJob.created_at >= start_dt)
            .where(AutoKeyJob.created_at <= end_dt)
        ).one()
    )
    customers_count = int(
        session.exec(
            select(func.count(func.distinct(AutoKeyJob.customer_id)))
            .where(AutoKeyJob.tenant_id == tenant_id)
            .where(AutoKeyJob.created_at >= start_dt)
            .where(AutoKeyJob.created_at <= end_dt)
        ).one()
    )
    sales_cents = int(
        session.exec(
            select(func.coalesce(func.sum(AutoKeyInvoice.total_cents), 0))
            .where(AutoKeyInvoice.tenant_id == tenant_id)
            .where(AutoKeyInvoice.status == "paid")
            .where(AutoKeyInvoice.created_at >= start_dt)
            .where(AutoKeyInvoice.created_at <= end_dt)
        ).one()
    )
    return customers_count, jobs_count, sales_cents


def build_mobile_weekly_report(
    session: Session,
    *,
    parent: ParentAccount,
    start_dt: datetime,
    end_dt: datetime,
) -> list[OperatorWeeklyStats]:
    operators = bookable_operators_for_parent(session, parent.id)
    if not operators:
        return []

    prior_start = start_dt - timedelta(days=7)
    prior_end = end_dt - timedelta(days=7)

    # Current backlog (all-time, not period-bound — "not actioned" is a point-in-time gauge).
    all_emails = session.exec(
        select(InboundEmail).where(InboundEmail.parent_account_id == parent.id)
    ).all()
    buckets_by_tenant = {
        b.operator_tenant_id: b for b in bucket_email_leads_by_operator(session, parent_id=parent.id, emails=all_emails)
        if b.operator_tenant_id is not None
    }

    rows: list[OperatorWeeklyStats] = []
    for tenant in operators:
        customers, jobs, sales = _week_stats_for_tenant(session, tenant.id, start_dt, end_dt)
        _prior_customers, prior_jobs, prior_sales = _week_stats_for_tenant(session, tenant.id, prior_start, prior_end)
        backlog = buckets_by_tenant.get(tenant.id)
        rows.append(
            OperatorWeeklyStats(
                operator_tenant_id=tenant.id,
                operator_name=tenant.name,
                customers_count=customers,
                jobs_count=jobs,
                sales_cents=sales,
                prior_week_sales_cents=prior_sales,
                prior_week_jobs_count=prior_jobs,
                enquiries_not_actioned=backlog.new_count if backlog else 0,
            )
        )

    # Worst-performing-first: biggest backlog, then lowest sales — the shops that need attention.
    rows.sort(key=lambda r: (-r.enquiries_not_actioned, r.sales_cents))
    return rows


def _build_csv_bytes(rows: list[OperatorWeeklyStats], start_ymd: str, end_ymd: str) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "Operator", "Week", "Customers", "Jobs", "Sales ($)",
            "Prior week jobs", "Prior week sales ($)", "Enquiries not actioned",
        ]
    )
    for row in rows:
        writer.writerow(
            [
                row.operator_name,
                f"{start_ymd} to {end_ymd}",
                row.customers_count,
                row.jobs_count,
                f"{row.sales_cents / 100:.2f}",
                row.prior_week_jobs_count,
                f"{row.prior_week_sales_cents / 100:.2f}",
                row.enquiries_not_actioned,
            ]
        )
    return buf.getvalue().encode("utf-8")


def _is_due(last_sent_at: datetime | None, today) -> bool:
    if last_sent_at is None:
        return True
    last_sent_date = last_sent_at.astimezone(timezone.utc).date() if last_sent_at.tzinfo else last_sent_at.date()
    return last_sent_date.isocalendar()[:2] != today.isocalendar()[:2]


def send_weekly_report_for_parent(session: Session, parent: ParentAccount) -> bool:
    """Build + send this parent's weekly report right now, regardless of due-ness. Commits."""
    today = datetime.now(timezone.utc).date()
    start_dt, end_dt, start_ymd, end_ymd = _previous_week_bounds(today)
    rows = build_mobile_weekly_report(session, parent=parent, start_dt=start_dt, end_dt=end_dt)
    csv_bytes = _build_csv_bytes(rows, start_ymd, end_ymd)
    sent, _err = email_client.send_mobile_weekly_report_email(
        to_email=parent.owner_email,
        period_start=start_ymd,
        period_end=end_ymd,
        rows=[
            {
                "operator_name": r.operator_name,
                "customers_count": r.customers_count,
                "jobs_count": r.jobs_count,
                "sales_cents": r.sales_cents,
                "prior_week_sales_cents": r.prior_week_sales_cents,
                "enquiries_not_actioned": r.enquiries_not_actioned,
            }
            for r in rows
        ],
        csv_bytes=csv_bytes,
        csv_filename=f"mobile-services-weekly-report-{start_ymd}_{end_ymd}.csv",
    )
    parent.last_mobile_weekly_report_sent_at = datetime.now(timezone.utc)
    session.add(parent)
    session.commit()
    return sent


def send_due_mobile_weekly_reports(session: Session, parent_id: UUID | None = None) -> dict[str, int]:
    """Send all due weekly mobile-network report emails. Caller-agnostic: used by
    the in-app scheduler (all opted-in parent accounts) and can target one for tests."""
    today = datetime.now(timezone.utc).date()
    summary = {"sent": 0, "skipped": 0}

    query = select(ParentAccount).where(ParentAccount.mobile_weekly_report_opt_in.is_(True))
    if parent_id:
        query = query.where(ParentAccount.id == parent_id)

    for parent in session.exec(query).all():
        if not _is_due(parent.last_mobile_weekly_report_sent_at, today):
            summary["skipped"] += 1
            continue
        try:
            if send_weekly_report_for_parent(session, parent):
                summary["sent"] += 1
            else:
                summary["skipped"] += 1
        except Exception:
            logger.exception("mobile_weekly_report.send_failed parent=%s", parent.id)
            summary["skipped"] += 1

    return summary
