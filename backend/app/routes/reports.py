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
    invoices = list(session.exec(
        select(AutoKeyInvoice)
        .where(AutoKeyInvoice.tenant_id == tenant_id)
        .where(AutoKeyInvoice.status == "paid")
    ).all())
    revenue_by_job = {inv.auto_key_job_id: inv.total_cents for inv in invoices}
    jobs_by_tech: dict[str, list] = {}
    mobile_count = 0
    shop_count = 0
    total_revenue_cents = 0
    for j in jobs:
        tech_id = str(j.assigned_user_id) if j.assigned_user_id else "unassigned"
        user = session.get(User, j.assigned_user_id) if j.assigned_user_id else None
        tech_name = user.full_name if user else "Unassigned"
        key = tech_id
        if key not in jobs_by_tech:
            jobs_by_tech[key] = {"tech_name": tech_name, "job_count": 0, "revenue_cents": 0}
        jobs_by_tech[key]["job_count"] += 1
        rev = revenue_by_job.get(j.id, 0)
        jobs_by_tech[key]["revenue_cents"] += rev
        total_revenue_cents += rev
        if j.job_type == "mobile":
            mobile_count += 1
        elif j.job_type == "shop":
            shop_count += 1
    return {
        "jobs_by_tech": [
            {"tech_id": k, "tech_name": v["tech_name"], "job_count": v["job_count"], "revenue_cents": v["revenue_cents"]}
            for k, v in sorted(jobs_by_tech.items(), key=lambda x: -x[1]["job_count"])
        ],
        "mobile_vs_shop": {"mobile": mobile_count, "shop": shop_count, "other": len(jobs) - mobile_count - shop_count},
        "total_jobs": len(jobs),
        "total_revenue_cents": total_revenue_cents,
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
