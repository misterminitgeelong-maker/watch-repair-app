import csv
import io
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlmodel import Session, func, select

from ..database import get_session
from ..dependencies import AuthContext, get_auth_context, require_manager_or_above
from ..models import AutoKeyInvoice, AutoKeyJob, Customer, Invoice, Payment, Quote, RepairJob, ShoeRepairJob, TenantEventLog, TenantEventLogRead, User, Watch, WorkLog

router = APIRouter(prefix="/v1/reports", tags=["reports"])


@router.get("/summary")
def get_reports_summary(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    tenant_id = auth.tenant_id

    jobs_total = int(
        session.exec(
            select(func.count()).select_from(RepairJob).where(RepairJob.tenant_id == tenant_id)
        ).one()
    )
    customers_total = int(
        session.exec(
            select(func.count()).select_from(Customer).where(Customer.tenant_id == tenant_id)
        ).one()
    )
    watches_total = int(
        session.exec(
            select(func.count()).select_from(Watch).where(Watch.tenant_id == tenant_id)
        ).one()
    )
    quotes_total = int(
        session.exec(
            select(func.count()).select_from(Quote).where(Quote.tenant_id == tenant_id)
        ).one()
    )
    invoices_total = int(
        session.exec(
            select(func.count()).select_from(Invoice).where(Invoice.tenant_id == tenant_id)
        ).one()
    )

    jobs_by_status_rows = session.exec(
        select(RepairJob.status, func.count())
        .where(RepairJob.tenant_id == tenant_id)
        .group_by(RepairJob.status)
    ).all()
    jobs_by_status = {status: int(count) for status, count in jobs_by_status_rows}

    quote_status_rows = session.exec(
        select(Quote.status, func.count())
        .where(Quote.tenant_id == tenant_id)
        .group_by(Quote.status)
    ).all()
    quotes_by_status = {status: int(count) for status, count in quote_status_rows}

    billed_cents = int(
        session.exec(
            select(func.coalesce(func.sum(Invoice.total_cents), 0)).where(Invoice.tenant_id == tenant_id)
        ).one()
    )
    revenue_cents = int(
        session.exec(
            select(func.coalesce(func.sum(Payment.amount_cents), 0))
            .where(Payment.tenant_id == tenant_id)
            .where(Payment.status == "succeeded")
        ).one()
    )
    cost_cents = int(
        session.exec(
            select(func.coalesce(func.sum(RepairJob.cost_cents), 0)).where(RepairJob.tenant_id == tenant_id)
        ).one()
    )
    outstanding_cents = max(billed_cents - revenue_cents, 0)
    gross_profit_cents = revenue_cents - cost_cents
    gross_margin_percent = round((gross_profit_cents / revenue_cents) * 100, 2) if revenue_cents > 0 else 0.0

    approved_quotes = quotes_by_status.get("approved", 0)
    sent_quotes = quotes_by_status.get("sent", 0)
    declined_quotes = quotes_by_status.get("declined", 0)
    approval_rate_percent = round((approved_quotes / max(approved_quotes + sent_quotes + declined_quotes, 1)) * 100, 2)

    work_minutes = int(
        session.exec(
            select(func.coalesce(func.sum(WorkLog.minutes_spent), 0)).where(WorkLog.tenant_id == tenant_id)
        ).one()
    )

    return {
        "counts": {
            "jobs": jobs_total,
            "customers": customers_total,
            "watches": watches_total,
            "quotes": quotes_total,
            "invoices": invoices_total,
        },
        "jobs_by_status": jobs_by_status,
        "quotes_by_status": quotes_by_status,
        "sales_funnel": {
            "approved_quotes": approved_quotes,
            "sent_quotes": sent_quotes,
            "declined_quotes": declined_quotes,
            "approval_rate_percent": approval_rate_percent,
        },
        "financials": {
            "billed_cents": billed_cents,
            "revenue_cents": revenue_cents,
            "cost_cents": cost_cents,
            "outstanding_cents": outstanding_cents,
            "gross_profit_cents": gross_profit_cents,
            "gross_margin_percent": gross_margin_percent,
        },
        "operations": {
            "work_minutes": work_minutes,
            "avg_revenue_per_job_cents": int(revenue_cents / jobs_total) if jobs_total > 0 else 0,
        },
    }


def _ym(dt: datetime) -> str:
    return f"{dt.year:04d}-{dt.month:02d}"


def _as_utc(dt: datetime) -> datetime:
    """Normalize DB datetimes to UTC-aware for safe comparisons."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _month_labels(n_months: int) -> list[str]:
    """Return YYYY-MM strings for the last n_months (oldest first)."""
    now = datetime.now(timezone.utc)
    result = []
    for i in range(n_months - 1, -1, -1):
        month = now.month - i
        year = now.year
        while month <= 0:
            month += 12
            year -= 1
        result.append(f"{year:04d}-{month:02d}")
    return result


@router.get("/trends")
def get_reports_trends(
    months: int = Query(default=6, ge=1, le=24),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    tenant_id = auth.tenant_id
    cutoff = datetime.now(timezone.utc) - timedelta(days=months * 31)

    # Fetch jobs created in the window
    job_dates = session.exec(
        select(RepairJob.created_at)
        .where(RepairJob.tenant_id == tenant_id)
        .where(RepairJob.created_at >= cutoff)
    ).all()

    # Fetch shoe jobs created in the window
    shoe_job_dates = session.exec(
        select(ShoeRepairJob.created_at)
        .where(ShoeRepairJob.tenant_id == tenant_id)
        .where(ShoeRepairJob.created_at >= cutoff)
    ).all()

    # Fetch auto key jobs created in the window
    ak_job_dates = session.exec(
        select(AutoKeyJob.created_at)
        .where(AutoKeyJob.tenant_id == tenant_id)
        .where(AutoKeyJob.created_at >= cutoff)
    ).all()

    # Fetch succeeded payments in the window
    payment_rows = session.exec(
        select(Payment.amount_cents, Payment.created_at)
        .where(Payment.tenant_id == tenant_id)
        .where(Payment.status == "succeeded")
        .where(Payment.created_at >= cutoff)
    ).all()

    labels = _month_labels(months)
    jobs_by_month: dict[str, int] = {m: 0 for m in labels}
    revenue_by_month: dict[str, int] = {m: 0 for m in labels}

    for dt in job_dates:
        key = _ym(dt)
        if key in jobs_by_month:
            jobs_by_month[key] += 1
    for dt in shoe_job_dates:
        key = _ym(dt)
        if key in jobs_by_month:
            jobs_by_month[key] += 1
    for dt in ak_job_dates:
        key = _ym(dt)
        if key in jobs_by_month:
            jobs_by_month[key] += 1
    for amount, dt in payment_rows:
        key = _ym(dt)
        if key in revenue_by_month:
            revenue_by_month[key] += amount

    return {
        "months": [
            {
                "month": m,
                "jobs_opened": jobs_by_month[m],
                "revenue_cents": revenue_by_month[m],
            }
            for m in labels
        ]
    }


@router.get("/widgets", summary="Dashboard action widgets")
def get_dashboard_widgets(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    """Counts for overdue jobs, quotes sent 7+ days not approved, and unpaid invoices."""
    tenant_id = auth.tenant_id
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)
    fourteen_days_ago = now - timedelta(days=14)

    # Jobs in awaiting_go_ahead or awaiting_parts for 14+ days
    overdue_jobs = session.exec(
        select(func.count())
        .select_from(RepairJob)
        .where(RepairJob.tenant_id == tenant_id)
        .where(RepairJob.status.in_(["awaiting_go_ahead", "awaiting_parts"]))
        .where(RepairJob.created_at <= fourteen_days_ago)
    ).one()
    overdue_jobs_count = int(overdue_jobs)

    # Quotes sent 7+ days ago still in 'sent' (not approved/declined)
    quotes_pending = session.exec(
        select(func.count())
        .select_from(Quote)
        .where(Quote.tenant_id == tenant_id)
        .where(Quote.status == "sent")
        .where(Quote.sent_at <= seven_days_ago)
    ).one()
    quotes_pending_7d_count = int(quotes_pending)

    # Unpaid invoices (overdue for follow-up)
    overdue_invoices = session.exec(
        select(func.count()).select_from(Invoice).where(Invoice.tenant_id == tenant_id).where(Invoice.status == "unpaid")
    ).one()
    overdue_invoices_count = int(overdue_invoices)

    return {
        "overdue_jobs_count": overdue_jobs_count,
        "quotes_pending_7d_count": quotes_pending_7d_count,
        "overdue_invoices_count": overdue_invoices_count,
    }


@router.get("/activity", response_model=list[TenantEventLogRead], summary="Audit log (owner/manager)")
def get_tenant_activity(
    limit: int = Query(default=50, ge=1, le=200),
    auth: AuthContext = Depends(require_manager_or_above),
    session: Session = Depends(get_session),
):
    rows = session.exec(
        select(TenantEventLog)
        .where(TenantEventLog.tenant_id == auth.tenant_id)
        .order_by(TenantEventLog.created_at.desc())
        .limit(limit)
    ).all()
    return rows


@router.get("/export/jobs", summary="Export jobs as CSV")
def export_jobs_csv(
    auth: AuthContext = Depends(require_manager_or_above),
    session: Session = Depends(get_session),
):
    rows = session.exec(
        select(RepairJob).where(RepairJob.tenant_id == auth.tenant_id).order_by(RepairJob.created_at.desc())
    ).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "job_number", "title", "status", "priority", "created_at"])
    for r in rows:
        w.writerow([str(r.id), r.job_number, r.title or "", r.status, r.priority, r.created_at.isoformat() if r.created_at else ""])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=jobs.csv"},
    )


@router.get("/export/customers", summary="Export customers as CSV")
def export_customers_csv(
    auth: AuthContext = Depends(require_manager_or_above),
    session: Session = Depends(get_session),
):
    rows = session.exec(
        select(Customer).where(Customer.tenant_id == auth.tenant_id).order_by(Customer.created_at.desc())
    ).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "full_name", "email", "phone", "address", "created_at"])
    for r in rows:
        w.writerow([str(r.id), r.full_name or "", r.email or "", r.phone or "", r.address or "", r.created_at.isoformat() if r.created_at else ""])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=customers.csv"},
    )


@router.get("/auto-key-summary", summary="Auto Key jobs and revenue by tech, mobile vs shop")
def get_auto_key_summary(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    tenant_id = auth.tenant_id
    jobs = list(session.exec(
        select(AutoKeyJob).where(AutoKeyJob.tenant_id == tenant_id)
    ).all())
    assigned_user_ids = {j.assigned_user_id for j in jobs if j.assigned_user_id}
    users_by_id = {}
    if assigned_user_ids:
        users = session.exec(
            select(User).where(User.id.in_(assigned_user_ids))
        ).all()
        users_by_id = {u.id: u for u in users}
    invoices = list(session.exec(
        select(AutoKeyInvoice)
        .where(AutoKeyInvoice.tenant_id == tenant_id)
        .where(AutoKeyInvoice.status == "paid")
    ).all())
    revenue_by_job = {inv.auto_key_job_id: inv.total_cents for inv in invoices}
    jobs_by_tech: dict[str, list] = {}
    job_type_breakdown: dict[str, int] = {}
    total_revenue_cents = 0
    for j in jobs:
        tech_id = str(j.assigned_user_id) if j.assigned_user_id else "unassigned"
        user = users_by_id.get(j.assigned_user_id) if j.assigned_user_id else None
        tech_name = user.full_name if user else "Unassigned"
        key = tech_id
        if key not in jobs_by_tech:
            jobs_by_tech[key] = {"tech_name": tech_name, "job_count": 0, "revenue_cents": 0}
        jobs_by_tech[key]["job_count"] += 1
        rev = revenue_by_job.get(j.id, 0)
        jobs_by_tech[key]["revenue_cents"] += rev
        total_revenue_cents += rev
        type_key = j.job_type or "Not set"
        job_type_breakdown[type_key] = job_type_breakdown.get(type_key, 0) + 1
    return {
        "jobs_by_tech": [
            {"tech_id": k, "tech_name": v["tech_name"], "job_count": v["job_count"], "revenue_cents": v["revenue_cents"]}
            for k, v in sorted(jobs_by_tech.items(), key=lambda x: -x[1]["job_count"])
        ],
        "job_type_breakdown": dict(sorted(job_type_breakdown.items(), key=lambda x: -x[1])),
        "total_jobs": len(jobs),
        "total_revenue_cents": total_revenue_cents,
    }


# Mobile job types (require job address)
_MOBILE_JOB_TYPES = {
    "Lockout – Car",
    "Lockout – Boot/Trunk",
    "Lockout – Roadside",
    "All Keys Lost",
    "Remote / Fob Sync",
    "Ignition Repair",
    "Ignition Replace",
    "Broken Key Extraction",
    "Door Lock Change",
    "Diagnostic",
}

# Full job type list for reports
_AUTO_KEY_REPORT_JOB_TYPES = [
    "Key Cutting (in-store)",
    "Transponder Programming",
    "Lockout – Car",
    "Lockout – Boot/Trunk",
    "Lockout – Roadside",
    "All Keys Lost",
    "Remote / Fob Sync",
    "Ignition Repair",
    "Ignition Replace",
    "Duplicate Key",
    "Broken Key Extraction",
    "Door Lock Change",
    "Diagnostic",
    "Not Set",
]

_AUTO_KEY_STATUS_LABELS = {
    "awaiting_quote": "Awaiting Quote",
    "awaiting_go_ahead": "Awaiting Go Ahead",
    "go_ahead": "Go Ahead Given",
    "working_on": "Started Work",
    "en_route": "En Route",
    "on_site": "On Site",
    "awaiting_parts": "Awaiting Parts",
    "completed": "Work Completed",
    "collected": "Collected",
    "no_go": "No Go",
}


@router.get("/auto-key-reports", summary="Auto Key reports dashboard with date range")
def get_auto_key_reports(
    date_from: str | None = Query(default=None, description="YYYY-MM-DD"),
    date_to: str | None = Query(default=None, description="YYYY-MM-DD"),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    """Full auto-key reports: summary tiles, jobs by type, by tech, by status, week-on-week trend."""
    tenant_id = auth.tenant_id
    now = datetime.now(timezone.utc)

    # Default to this month
    if not date_from or not date_to:
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        next_month = (start_of_month.replace(day=28) + timedelta(days=4)).replace(day=1)
        end_of_month = next_month - timedelta(days=1)
        end_of_month = end_of_month.replace(hour=23, minute=59, second=59, microsecond=999999)
        date_from = start_of_month.strftime("%Y-%m-%d")
        date_to = end_of_month.strftime("%Y-%m-%d")

    try:
        start_dt = datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        end_dt = datetime.strptime(date_to + " 23:59:59", "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        start_dt = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_dt = now

    jobs_in_range = list(session.exec(
        select(AutoKeyJob)
        .where(AutoKeyJob.tenant_id == tenant_id)
        .where(AutoKeyJob.created_at >= start_dt)
        .where(AutoKeyJob.created_at <= end_dt)
    ).all())
    assigned_user_ids = {j.assigned_user_id for j in jobs_in_range if j.assigned_user_id}
    users_by_id = {}
    if assigned_user_ids:
        users = session.exec(
            select(User).where(User.id.in_(assigned_user_ids))
        ).all()
        users_by_id = {u.id: u for u in users}

    job_ids_in_range = [j.id for j in jobs_in_range]
    invoices = []
    if job_ids_in_range:
        invoices = list(session.exec(
            select(AutoKeyInvoice)
            .where(AutoKeyInvoice.tenant_id == tenant_id)
            .where(AutoKeyInvoice.auto_key_job_id.in_(job_ids_in_range))
        ).all())

    revenue_by_job: dict[UUID, int] = {}
    for inv in invoices:
        revenue_by_job[inv.auto_key_job_id] = revenue_by_job.get(inv.auto_key_job_id, 0) + inv.total_cents

    total_jobs = len(jobs_in_range)
    total_revenue_cents = sum(revenue_by_job.values())

    completed_jobs = [j for j in jobs_in_range if j.status in ("completed", "collected")]
    completed_count = len(completed_jobs)
    avg_job_value_cents = int(total_revenue_cents / completed_count) if completed_count > 0 else 0

    mobile_count = sum(1 for j in jobs_in_range if j.job_type in _MOBILE_JOB_TYPES)
    shop_count = total_jobs - mobile_count
    mobile_pct = round(100 * mobile_count / total_jobs, 1) if total_jobs > 0 else 0
    shop_pct = round(100 * shop_count / total_jobs, 1) if total_jobs > 0 else 0

    job_type_rows: dict[str, dict] = {t: {"count": 0, "revenue_cents": 0} for t in _AUTO_KEY_REPORT_JOB_TYPES}
    for j in jobs_in_range:
        key = j.job_type or "Not Set"
        if key not in job_type_rows:
            job_type_rows[key] = {"count": 0, "revenue_cents": 0}
        job_type_rows[key]["count"] += 1
        job_type_rows[key]["revenue_cents"] += revenue_by_job.get(j.id, 0)

    jobs_by_type = [
        {
            "job_type": t,
            "jobs": job_type_rows[t]["count"],
            "revenue_cents": job_type_rows[t]["revenue_cents"],
            "avg_value_cents": int(job_type_rows[t]["revenue_cents"] / job_type_rows[t]["count"])
            if job_type_rows[t]["count"] > 0 else 0,
        }
        for t in _AUTO_KEY_REPORT_JOB_TYPES
    ]

    jobs_by_tech_map: dict[str, dict] = {}
    for j in jobs_in_range:
        tech_id = str(j.assigned_user_id) if j.assigned_user_id else "unassigned"
        user = users_by_id.get(j.assigned_user_id) if j.assigned_user_id else None
        tech_name = user.full_name if user else "Unassigned"
        if tech_id not in jobs_by_tech_map:
            jobs_by_tech_map[tech_id] = {"tech_name": tech_name, "job_count": 0, "revenue_cents": 0}
        jobs_by_tech_map[tech_id]["job_count"] += 1
        jobs_by_tech_map[tech_id]["revenue_cents"] += revenue_by_job.get(j.id, 0)

    jobs_by_tech = [
        {"tech_id": k, "tech_name": v["tech_name"], "job_count": v["job_count"], "revenue_cents": v["revenue_cents"]}
        for k, v in sorted(jobs_by_tech_map.items(), key=lambda x: -x[1]["job_count"])
    ]

    # Jobs by status - current pipeline (NOT date filtered)
    status_rows = session.exec(
        select(AutoKeyJob.status, func.count())
        .where(AutoKeyJob.tenant_id == tenant_id)
        .group_by(AutoKeyJob.status)
    ).all()
    status_counts = {status: int(count) for status, count in status_rows}

    pipeline_statuses = [
        "awaiting_quote", "awaiting_go_ahead", "go_ahead", "working_on",
        "en_route", "on_site", "awaiting_parts", "completed", "collected", "no_go",
    ]
    jobs_by_status = [
        {"status": s, "label": _AUTO_KEY_STATUS_LABELS.get(s, s.replace("_", " ").title()), "count": status_counts.get(s, 0)}
        for s in pipeline_statuses
    ]

    # Week on week - last 8 weeks
    week_labels: list[str] = []
    week_ranges: list[tuple[datetime, datetime]] = []
    for i in range(7, -1, -1):
        week_end = now - timedelta(weeks=i)
        week_start = week_end - timedelta(days=6)
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_end.replace(hour=23, minute=59, second=59, microsecond=999999)
        label = f"{week_start.strftime('%d %b')} – {week_end.strftime('%d %b')}"
        week_labels.append(label)
        week_ranges.append((week_start, week_end))

    earliest_week_start = week_ranges[0][0]
    latest_week_end = week_ranges[-1][1]
    week_job_dates = session.exec(
        select(AutoKeyJob.created_at)
        .where(AutoKeyJob.tenant_id == tenant_id)
        .where(AutoKeyJob.created_at >= earliest_week_start)
        .where(AutoKeyJob.created_at <= latest_week_end)
    ).all()
    week_invoice_rows = session.exec(
        select(AutoKeyInvoice.created_at, AutoKeyInvoice.total_cents)
        .where(AutoKeyInvoice.tenant_id == tenant_id)
        .where(AutoKeyInvoice.created_at >= earliest_week_start)
        .where(AutoKeyInvoice.created_at <= latest_week_end)
    ).all()
    week_jobs_list = [0] * len(week_ranges)
    week_revenue_list = [0] * len(week_ranges)
    for created_at in week_job_dates:
        created_at_utc = _as_utc(created_at)
        for idx, (start, end) in enumerate(week_ranges):
            if start <= created_at_utc <= end:
                week_jobs_list[idx] += 1
                break
    for created_at, total_cents in week_invoice_rows:
        created_at_utc = _as_utc(created_at)
        for idx, (start, end) in enumerate(week_ranges):
            if start <= created_at_utc <= end:
                week_revenue_list[idx] += int(total_cents)
                break

    week_on_week = [
        {"week_label": week_labels[i], "jobs": week_jobs_list[i], "revenue_cents": week_revenue_list[i]}
        for i in range(len(week_labels))
    ]

    return {
        "date_from": date_from,
        "date_to": date_to,
        "summary": {
            "total_jobs": total_jobs,
            "total_revenue_cents": total_revenue_cents,
            "avg_job_value_cents": avg_job_value_cents,
            "completed_jobs": completed_count,
            "mobile_count": mobile_count,
            "mobile_pct": mobile_pct,
            "shop_count": shop_count,
            "shop_pct": shop_pct,
        },
        "jobs_by_type": jobs_by_type,
        "jobs_by_tech": jobs_by_tech,
        "jobs_by_status": jobs_by_status,
        "week_on_week": week_on_week,
    }


@router.get("/export/invoices", summary="Export invoices as CSV")
def export_invoices_csv(
    auth: AuthContext = Depends(require_manager_or_above),
    session: Session = Depends(get_session),
):
    rows = session.exec(
        select(Invoice).where(Invoice.tenant_id == auth.tenant_id).order_by(Invoice.created_at.desc())
    ).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "invoice_number", "status", "total_cents", "created_at"])
    for r in rows:
        w.writerow([str(r.id), r.invoice_number or "", r.status, r.total_cents, r.created_at.isoformat() if r.created_at else ""])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=invoices.csv"},
    )
