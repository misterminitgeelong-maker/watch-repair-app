import csv
import io
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlmodel import Session, func, select, col

from ..database import get_session
from ..dependencies import AuthContext, get_auth_context, require_manager_or_above
from ..mobile_commission import DEFAULT_ELIGIBLE_STATUSES, commission_for_period_lines, parse_mobile_commission_rules
from ..models import AutoKeyInvoice, AutoKeyJob, Customer, Invoice, JobStatusHistory, Payment, Quote, RepairJob, ShoeRepairJob, ShoeRepairJobItem, TenantEventLog, TenantEventLogRead, User, Watch, WorkLog

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

    # Billed: watch invoices + auto-key invoices + shoe service items
    watch_billed = int(
        session.exec(
            select(func.coalesce(func.sum(Invoice.total_cents), 0)).where(Invoice.tenant_id == tenant_id)
        ).one()
    )
    ak_billed = int(
        session.exec(
            select(func.coalesce(func.sum(AutoKeyInvoice.total_cents), 0)).where(AutoKeyInvoice.tenant_id == tenant_id)
        ).one()
    )
    shoe_billed = int(
        session.exec(
            select(func.coalesce(func.sum(ShoeRepairJobItem.unit_price_cents * ShoeRepairJobItem.quantity), 0))
            .where(ShoeRepairJobItem.tenant_id == tenant_id)
            .where(ShoeRepairJobItem.unit_price_cents.isnot(None))
        ).one() or 0
    )
    billed_cents = watch_billed + ak_billed + shoe_billed
    # Revenue = succeeded payments + paid invoices that have no payment record (seed / legacy data)
    payment_revenue = int(
        session.exec(
            select(func.coalesce(func.sum(Payment.amount_cents), 0))
            .where(Payment.tenant_id == tenant_id)
            .where(Payment.status == "succeeded")
        ).one()
    )
    invoiced_payment_ids = select(Payment.invoice_id).where(Payment.status == "succeeded")
    orphan_paid_cents = int(
        session.exec(
            select(func.coalesce(func.sum(Invoice.total_cents), 0))
            .where(Invoice.tenant_id == tenant_id)
            .where(Invoice.status == "paid")
            .where(Invoice.id.not_in(invoiced_payment_ids))
        ).one()
    )
    # Paid auto-key invoices (no Payment table for auto-key jobs)
    ak_revenue = int(
        session.exec(
            select(func.coalesce(func.sum(AutoKeyInvoice.total_cents), 0))
            .where(AutoKeyInvoice.tenant_id == tenant_id)
            .where(AutoKeyInvoice.status == "paid")
        ).one()
    )
    # Shoe revenue = service items on collected/completed jobs
    _SHOE_PAID_STATUSES = ("collected", "awaiting_collection", "completed")
    shoe_revenue = int(
        session.exec(
            select(func.coalesce(func.sum(ShoeRepairJobItem.unit_price_cents * ShoeRepairJobItem.quantity), 0))
            .join(ShoeRepairJob, ShoeRepairJobItem.shoe_repair_job_id == ShoeRepairJob.id)
            .where(ShoeRepairJobItem.tenant_id == tenant_id)
            .where(ShoeRepairJobItem.unit_price_cents.isnot(None))
            .where(ShoeRepairJob.status.in_(_SHOE_PAID_STATUSES))
        ).one() or 0
    )
    revenue_cents = payment_revenue + orphan_paid_cents + ak_revenue + shoe_revenue
    # Cost: watch + shoe + auto-key jobs
    watch_cost = int(session.exec(select(func.coalesce(func.sum(RepairJob.cost_cents), 0)).where(RepairJob.tenant_id == tenant_id)).one())
    shoe_cost = int(session.exec(select(func.coalesce(func.sum(ShoeRepairJob.cost_cents), 0)).where(ShoeRepairJob.tenant_id == tenant_id)).one())
    ak_cost = int(session.exec(select(func.coalesce(func.sum(AutoKeyJob.cost_cents), 0)).where(AutoKeyJob.tenant_id == tenant_id)).one())
    cost_cents = watch_cost + shoe_cost + ak_cost
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

    # avg_turnaround_days: average days from job created_at to first 'collected' status history entry
    collected_rows = session.exec(
        select(RepairJob.id, RepairJob.created_at, JobStatusHistory.created_at)
        .join(JobStatusHistory, JobStatusHistory.repair_job_id == RepairJob.id)
        .where(RepairJob.tenant_id == tenant_id)
        .where(JobStatusHistory.tenant_id == tenant_id)
        .where(JobStatusHistory.new_status == "collected")
        .order_by(RepairJob.id, JobStatusHistory.created_at.asc())
    ).all()
    # Keep only the first collected entry per job
    seen_job_ids: set = set()
    turnaround_days_list: list[float] = []
    for row in collected_rows:
        job_id_val, job_created, collected_at = row[0], row[1], row[2]
        if job_id_val in seen_job_ids:
            continue
        seen_job_ids.add(job_id_val)
        if job_created and collected_at:
            delta = collected_at - job_created
            turnaround_days_list.append(delta.total_seconds() / 86400)
    avg_turnaround_days = round(sum(turnaround_days_list) / len(turnaround_days_list), 2) if turnaround_days_list else None

    # quote_to_invoice_pct: percentage of approved quotes whose job also has an invoice
    invoiced_job_ids = set(
        session.exec(
            select(Invoice.repair_job_id)
            .where(Invoice.tenant_id == tenant_id)
            .where(Invoice.repair_job_id.isnot(None))
        ).all()
    )
    approved_job_ids = set(
        session.exec(
            select(Quote.repair_job_id)
            .where(Quote.tenant_id == tenant_id)
            .where(Quote.status == "approved")
        ).all()
    )
    converted = len(approved_job_ids & invoiced_job_ids)
    quote_to_invoice_pct = round((converted / max(len(approved_job_ids), 1)) * 100, 1)

    # Avg hours from job creation to first quote sent
    quote_pairs = session.exec(
        select(RepairJob.created_at, Quote.sent_at)
        .join(Quote, Quote.repair_job_id == RepairJob.id)
        .where(RepairJob.tenant_id == tenant_id)
        .where(Quote.sent_at.isnot(None))
    ).all()
    if quote_pairs:
        hours_list = [
            (sent - created).total_seconds() / 3600
            for created, sent in quote_pairs
            if sent and created and sent > created
        ]
        avg_quote_response_hours = round(sum(hours_list) / len(hours_list), 1) if hours_list else None
    else:
        avg_quote_response_hours = None

    # Shoe-specific metrics
    shoe_jobs_total = int(
        session.exec(
            select(func.count()).select_from(ShoeRepairJob).where(ShoeRepairJob.tenant_id == tenant_id)
        ).one()
    )
    shoe_jobs_by_status_rows = session.exec(
        select(ShoeRepairJob.status, func.count())
        .where(ShoeRepairJob.tenant_id == tenant_id)
        .group_by(ShoeRepairJob.status)
    ).all()
    shoe_jobs_by_status = {status: int(count) for status, count in shoe_jobs_by_status_rows}

    shoe_quote_status_rows = session.exec(
        select(ShoeRepairJob.quote_status, func.count())
        .where(ShoeRepairJob.tenant_id == tenant_id)
        .where(ShoeRepairJob.quote_status != "none")
        .group_by(ShoeRepairJob.quote_status)
    ).all()
    shoe_quotes_by_status = {status: int(count) for status, count in shoe_quote_status_rows}

    shoe_approved = shoe_quotes_by_status.get("approved", 0)
    shoe_sent = shoe_quotes_by_status.get("sent", 0)
    shoe_declined = shoe_quotes_by_status.get("declined", 0)
    shoe_approval_rate = round(
        (shoe_approved / max(shoe_approved + shoe_sent + shoe_declined, 1)) * 100, 1
    )

    return {
        "counts": {
            "jobs": jobs_total,
            "customers": customers_total,
            "watches": watches_total,
            "quotes": quotes_total,
            "invoices": invoices_total,
            "shoe_jobs": shoe_jobs_total,
        },
        "jobs_by_status": jobs_by_status,
        "shoe_jobs_by_status": shoe_jobs_by_status,
        "shoe_quotes": {
            "by_status": shoe_quotes_by_status,
            "approval_rate_percent": shoe_approval_rate,
        },
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
            "avg_turnaround_days": avg_turnaround_days,
            "quote_to_invoice_pct": quote_to_invoice_pct,
            "avg_quote_response_hours": avg_quote_response_hours,
        },
    }


@router.get("/tech-breakdown")
def get_tech_breakdown(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    tenant_id = auth.tenant_id

    rows = session.exec(
        select(
            WorkLog.user_id,
            func.coalesce(func.sum(WorkLog.minutes_spent), 0).label("total_minutes"),
            func.count(WorkLog.repair_job_id).label("jobs_count"),
        )
        .where(WorkLog.tenant_id == tenant_id)
        .where(WorkLog.user_id.isnot(None))
        .group_by(WorkLog.user_id)
    ).all()

    if not rows:
        return []

    user_ids = [row[0] for row in rows]
    users = session.exec(select(User).where(User.id.in_(user_ids))).all()
    user_name_map = {str(u.id): u.full_name for u in users}

    result = [
        {
            "user_id": str(row[0]),
            "user_name": user_name_map.get(str(row[0]), "Unknown"),
            "total_minutes": int(row[1]),
            "jobs_count": int(row[2]),
        }
        for row in rows
    ]
    result.sort(key=lambda x: x["total_minutes"], reverse=True)
    return result


def _ym(dt: datetime) -> str:
    return f"{dt.year:04d}-{dt.month:02d}"


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
    # Also fetch paid invoices with no payment record (seed/legacy), use created_at as revenue date
    orphan_ids_subq = select(Payment.invoice_id).where(Payment.status == "succeeded")
    orphan_invoice_rows = session.exec(
        select(Invoice.total_cents, Invoice.created_at)
        .where(Invoice.tenant_id == tenant_id)
        .where(Invoice.status == "paid")
        .where(Invoice.id.not_in(orphan_ids_subq))
        .where(Invoice.created_at >= cutoff)
    ).all()
    # Paid auto-key invoices (separate revenue stream, no Payment table)
    ak_invoice_rows = session.exec(
        select(AutoKeyInvoice.total_cents, AutoKeyInvoice.created_at)
        .where(AutoKeyInvoice.tenant_id == tenant_id)
        .where(AutoKeyInvoice.status == "paid")
        .where(AutoKeyInvoice.created_at >= cutoff)
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
    for amount, dt in orphan_invoice_rows:
        key = _ym(dt)
        if key in revenue_by_month:
            revenue_by_month[key] += amount
    for amount, dt in ak_invoice_rows:
        key = _ym(dt)
        if key in revenue_by_month:
            revenue_by_month[key] += int(amount)

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

    # Jobs past their collection_date that haven't been collected or cancelled
    today = now.date()
    overdue_collection = session.exec(
        select(func.count())
        .select_from(RepairJob)
        .where(RepairJob.tenant_id == tenant_id)
        .where(RepairJob.collection_date.isnot(None))
        .where(RepairJob.collection_date < today)
        .where(RepairJob.status.not_in(["collected", "no_go"]))
    ).one()
    overdue_collection_count = int(overdue_collection)

    return {
        "overdue_jobs_count": overdue_jobs_count,
        "quotes_pending_7d_count": quotes_pending_7d_count,
        "overdue_invoices_count": overdue_invoices_count,
        "overdue_collection_count": overdue_collection_count,
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


@router.get("/auto-key")
def get_auto_key_reports(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    tenant_id = auth.tenant_id

    stmt = select(AutoKeyJob).where(AutoKeyJob.tenant_id == tenant_id)
    if date_from:
        try:
            df = datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            stmt = stmt.where(AutoKeyJob.created_at >= df)
        except ValueError:
            pass
    if date_to:
        try:
            dt = datetime.strptime(date_to, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
            stmt = stmt.where(AutoKeyJob.created_at <= dt)
        except ValueError:
            pass

    jobs = session.exec(stmt).all()
    job_ids = [j.id for j in jobs]

    invoices_map: dict[UUID, AutoKeyInvoice] = {}
    if job_ids:
        invs = session.exec(
            select(AutoKeyInvoice).where(
                AutoKeyInvoice.auto_key_job_id.in_(job_ids),
                AutoKeyInvoice.tenant_id == tenant_id,
            )
        ).all()
        invoices_map = {inv.auto_key_job_id: inv for inv in invs}

    def job_revenue(job: AutoKeyJob) -> int:
        inv = invoices_map.get(job.id)
        return inv.total_cents if inv else 0

    def is_mobile(job: AutoKeyJob) -> bool:
        return bool(job.job_address and job.job_address.strip())

    def pct(a: int | float, total: int | float) -> float:
        return round(a / total * 100, 1) if total else 0.0

    total_jobs = len(jobs)
    total_revenue = sum(job_revenue(j) for j in jobs)
    mobile_jobs = [j for j in jobs if is_mobile(j)]
    shop_jobs = [j for j in jobs if not is_mobile(j)]
    mobile_revenue = sum(job_revenue(j) for j in mobile_jobs)
    shop_revenue = sum(job_revenue(j) for j in shop_jobs)

    type_map: dict[str, dict] = {}
    for j in jobs:
        t = j.job_type or "Unknown"
        if t not in type_map:
            type_map[t] = {"job_type": t, "jobs": 0, "revenue_cents": 0}
        type_map[t]["jobs"] += 1
        type_map[t]["revenue_cents"] += job_revenue(j)
    for v in type_map.values():
        v["avg_value_cents"] = v["revenue_cents"] // v["jobs"] if v["jobs"] else 0

    tech_ids = {j.assigned_user_id for j in jobs if j.assigned_user_id}
    tech_names: dict[UUID, str] = {}
    if tech_ids:
        users = session.exec(select(User).where(col(User.id).in_(tech_ids))).all()
        tech_names = {u.id: u.full_name for u in users}

    tech_map: dict[UUID, dict] = {}
    for j in jobs:
        uid = j.assigned_user_id
        if not uid:
            continue
        if uid not in tech_map:
            tech_map[uid] = {"tech_id": str(uid), "tech_name": tech_names.get(uid, "Unknown"), "job_count": 0, "revenue_cents": 0}
        tech_map[uid]["job_count"] += 1
        tech_map[uid]["revenue_cents"] += job_revenue(j)
    for v in tech_map.values():
        v["revenue_share_pct"] = pct(v["revenue_cents"], total_revenue)

    status_map: dict[str, int] = {}
    for j in jobs:
        status_map[j.status] = status_map.get(j.status, 0) + 1

    week_map: dict[str, dict] = {}
    for j in jobs:
        dt = j.created_at
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        week_start = (dt - timedelta(days=dt.weekday())).date().isoformat()
        if week_start not in week_map:
            week_map[week_start] = {"week_start": week_start, "week_label": week_start, "jobs": 0, "revenue_cents": 0}
        week_map[week_start]["jobs"] += 1
        week_map[week_start]["revenue_cents"] += job_revenue(j)

    return {
        "summary": {
            "total_jobs": total_jobs,
            "total_revenue_cents": total_revenue,
            "avg_job_value_cents": total_revenue // total_jobs if total_jobs else 0,
            "mobile_count": len(mobile_jobs),
            "mobile_pct": pct(len(mobile_jobs), total_jobs),
            "shop_count": len(shop_jobs),
            "shop_pct": pct(len(shop_jobs), total_jobs),
            "mobile_revenue_cents": mobile_revenue,
            "mobile_revenue_pct": pct(mobile_revenue, total_revenue),
            "shop_revenue_cents": shop_revenue,
            "shop_revenue_pct": pct(shop_revenue, total_revenue),
        },
        "jobs_by_type": sorted(type_map.values(), key=lambda x: -x["revenue_cents"]),
        "jobs_by_tech": sorted(tech_map.values(), key=lambda x: -x["revenue_cents"]),
        "jobs_by_status": [{"status": s, "count": c} for s, c in status_map.items()],
        "week_on_week": sorted(week_map.values(), key=lambda x: x["week_start"]),
    }


@router.get("/auto-key/commission")
def get_auto_key_commission_report(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    tenant_id = auth.tenant_id

    users = session.exec(
        select(User).where(
            User.tenant_id == tenant_id,
            col(User.mobile_commission_rules_json).isnot(None),
        )
    ).all()

    stmt = select(AutoKeyJob).where(AutoKeyJob.tenant_id == tenant_id)
    if date_from:
        try:
            df = datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            stmt = stmt.where(AutoKeyJob.created_at >= df)
        except ValueError:
            pass
    if date_to:
        try:
            dt = datetime.strptime(date_to, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
            stmt = stmt.where(AutoKeyJob.created_at <= dt)
        except ValueError:
            pass

    all_jobs = session.exec(stmt).all()
    job_ids = [j.id for j in all_jobs]

    invoices_map: dict[UUID, AutoKeyInvoice] = {}
    if job_ids:
        invs = session.exec(
            select(AutoKeyInvoice).where(
                AutoKeyInvoice.auto_key_job_id.in_(job_ids),
                AutoKeyInvoice.tenant_id == tenant_id,
            )
        ).all()
        invoices_map = {inv.auto_key_job_id: inv for inv in invs}

    technicians = []
    for user in users:
        rules = parse_mobile_commission_rules(user.mobile_commission_rules_json)
        if not rules or not rules.get("enabled"):
            continue

        eligible_statuses = rules.get("eligible_job_statuses", list(DEFAULT_ELIGIBLE_STATUSES))
        user_jobs = [j for j in all_jobs if j.assigned_user_id == user.id and j.status in eligible_statuses]

        lines_data = [
            (j.id, j.job_number, invoices_map[j.id].id, invoices_map[j.id].total_cents, j.commission_lead_source, j.status)
            for j in user_jobs
            if j.id in invoices_map and invoices_map[j.id].total_cents > 0
        ]

        raw_commission, commission_lines = commission_for_period_lines(rules=rules, lines_data=lines_data)
        retainer = rules.get("retainer_cents_per_period", 0)
        labels: dict[str, str] = rules.get("labels", {})

        technicians.append({
            "user_id": str(user.id),
            "full_name": user.full_name,
            "raw_commission_cents": raw_commission,
            "retainer_cents": retainer,
            "bonus_payable_cents": max(0, raw_commission - retainer),
            "lines": [
                {
                    "job_id": str(line.job_id),
                    "invoice_id": str(line.invoice_id),
                    "job_number": line.job_number,
                    "lead_source_label": labels.get(line.lead_source, line.lead_source),
                    "revenue_cents": line.revenue_cents,
                    "rate_bp": line.rate_bp,
                    "commission_cents": line.commission_cents,
                }
                for line in commission_lines
            ],
        })

    return {"technicians": technicians}
