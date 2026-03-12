from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, func, select

from ..database import get_session
from ..dependencies import AuthContext, get_auth_context
from ..models import AutoKeyJob, Customer, Invoice, Payment, Quote, RepairJob, ShoeRepairJob, TenantEventLog, TenantEventLogRead, Watch, WorkLog

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


@router.get("/activity", response_model=list[TenantEventLogRead])
def get_tenant_activity(
    limit: int = Query(default=50, ge=1, le=200),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    rows = session.exec(
        select(TenantEventLog)
        .where(TenantEventLog.tenant_id == auth.tenant_id)
        .order_by(TenantEventLog.created_at.desc())
        .limit(limit)
    ).all()
    return rows
