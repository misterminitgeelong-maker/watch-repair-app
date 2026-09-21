"""Minit HQ mobile-network KPIs: trade-day / operating-week windows and per-operator rows.

Retail regional reporting is a weekly Excel upload. This module is the live
POS equivalent for mobile operator tenants: paid sales, jobs created,
jobs completed, customers, category mix and lead-source mix.

Clock (Australia/Sydney, one network CSV):

* Trade day freeze: local 21:00. Snapshot window is [00:00, 21:00] that civil date.
* Operating week: Sunday 01:00 → Saturday 23:00.
* Weekly compile: Saturday 23:05.

Live queries use the same windows with ``end = now`` so the HQ board can poll.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func as sa_func
from sqlmodel import Session, col, func, select

from .auto_key_status import AUTO_KEY_ACTIVE_STATUSES
from .minit_email_lead_parser import bookable_operators_for_parent, bucket_email_leads_by_operator
from .models import AutoKeyInvoice, AutoKeyJob, InboundEmail, ParentAccount, Tenant

NETWORK_TIMEZONE_NAME = "Australia/Sydney"
NETWORK_TZ = ZoneInfo(NETWORK_TIMEZONE_NAME)

DAILY_CLOSE_HOUR = 21
WEEK_START_WEEKDAY = 6  # datetime.weekday(): Sunday
WEEK_START_HOUR = 1
WEEK_END_HOUR = 23
WEEKLY_COMPILE_HOUR = 23
WEEKLY_COMPILE_MINUTE = 5

CATEGORY_KEYS: tuple[str, ...] = (
    "lockout",
    "all_keys_lost",
    "key_cutting",
    "remote_fob",
    "ignition",
    "transponder",
    "diagnostic",
    "other",
)
CATEGORY_LABELS: dict[str, str] = {
    "lockout": "Lockout",
    "all_keys_lost": "All Keys Lost",
    "key_cutting": "Key cutting / duplicate",
    "remote_fob": "Remote / fob",
    "ignition": "Ignition",
    "transponder": "Transponder",
    "diagnostic": "Diagnostic",
    "other": "Other",
}
_CATEGORY_MATCHERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("lockout", ("lockout",)),
    ("all_keys_lost", ("all keys lost",)),
    ("key_cutting", ("key cutting", "duplicate key")),
    ("remote_fob", ("remote", "fob")),
    ("ignition", ("ignition",)),
    ("transponder", ("transponder",)),
    ("diagnostic", ("diagnostic",)),
)

LEAD_KEYS: tuple[str, ...] = ("shop_referred", "tech_sourced", "minit_sourced", "other")
LEAD_LABELS: dict[str, str] = {
    "shop_referred": "Shop referred",
    "tech_sourced": "Tech sourced",
    "minit_sourced": "Minit sourced",
    "other": "Other lead",
}

_EXCLUDED_INVOICE_STATUSES = frozenset({"void", "refunded"})


def network_tz() -> ZoneInfo:
    return NETWORK_TZ


def as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _empty_counts(keys: Iterable[str]) -> dict[str, int]:
    return {key: 0 for key in keys}


def classify_job_type(job_type: str | None) -> str:
    text = (job_type or "").strip().lower()
    if not text:
        return "other"
    for key, needles in _CATEGORY_MATCHERS:
        if any(needle in text for needle in needles):
            return key
    return "other"


def classify_lead_source(source: str | None) -> str:
    key = (source or "").strip() or "shop_referred"
    return key if key in LEAD_KEYS[:-1] else "other"


def pct_change(current: int, prior: int) -> float | None:
    if prior == 0:
        return None
    return round(((current - prior) / prior) * 100.0, 1)


def derived_avg_sale_cents(sales_cents: int, customers_count: int) -> float | None:
    if customers_count <= 0:
        return None
    return round(sales_cents / customers_count, 2)


def derived_jobs_per_customer(jobs_created: int, customers_count: int) -> float | None:
    if customers_count <= 0:
        return None
    return round(jobs_created / customers_count, 2)


def dollars(cents: int) -> str:
    return f"{cents / 100:.2f}"


@dataclass
class OperatorKpiRow:
    operator_tenant_id: UUID
    operator_name: str
    operator_shop_number: str | None
    customers_count: int = 0
    jobs_created: int = 0
    jobs_completed: int = 0
    sales_cents: int = 0
    prior_sales_cents: int = 0
    prior_jobs_created: int = 0
    sales_pct_change: float | None = None
    avg_sale_cents: float | None = None
    jobs_per_customer: float | None = None
    category_jobs: dict[str, int] = field(default_factory=lambda: _empty_counts(CATEGORY_KEYS))
    category_sales_cents: dict[str, int] = field(default_factory=lambda: _empty_counts(CATEGORY_KEYS))
    lead_jobs: dict[str, int] = field(default_factory=lambda: _empty_counts(LEAD_KEYS))
    lead_sales_cents: dict[str, int] = field(default_factory=lambda: _empty_counts(LEAD_KEYS))
    active_jobs: int = 0
    outstanding_cents: int = 0
    enquiries_not_actioned: int = 0

    def apply_comparisons(self, prior: "OperatorKpiRow | None") -> None:
        if prior is not None:
            self.prior_sales_cents = prior.sales_cents
            self.prior_jobs_created = prior.jobs_created
        self.sales_pct_change = pct_change(self.sales_cents, self.prior_sales_cents)
        self.avg_sale_cents = derived_avg_sale_cents(self.sales_cents, self.customers_count)
        self.jobs_per_customer = derived_jobs_per_customer(self.jobs_created, self.customers_count)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["operator_tenant_id"] = str(self.operator_tenant_id)
        return payload


def operator_row_from_dict(data: dict[str, Any]) -> OperatorKpiRow:
    row = OperatorKpiRow(
        operator_tenant_id=UUID(str(data["operator_tenant_id"])),
        operator_name=data.get("operator_name") or "Operator",
        operator_shop_number=data.get("operator_shop_number"),
        customers_count=int(data.get("customers_count") or 0),
        jobs_created=int(data.get("jobs_created") or 0),
        jobs_completed=int(data.get("jobs_completed") or 0),
        sales_cents=int(data.get("sales_cents") or 0),
        prior_sales_cents=int(data.get("prior_sales_cents") or 0),
        prior_jobs_created=int(data.get("prior_jobs_created") or 0),
        sales_pct_change=data.get("sales_pct_change"),
        avg_sale_cents=data.get("avg_sale_cents"),
        jobs_per_customer=data.get("jobs_per_customer"),
        category_jobs=data.get("category_jobs") or _empty_counts(CATEGORY_KEYS),
        category_sales_cents=data.get("category_sales_cents") or _empty_counts(CATEGORY_KEYS),
        lead_jobs=data.get("lead_jobs") or _empty_counts(LEAD_KEYS),
        lead_sales_cents=data.get("lead_sales_cents") or _empty_counts(LEAD_KEYS),
        active_jobs=int(data.get("active_jobs") or 0),
        outstanding_cents=int(data.get("outstanding_cents") or 0),
        enquiries_not_actioned=int(data.get("enquiries_not_actioned") or 0),
    )
    return row


@dataclass
class NetworkKpiReport:
    start: datetime
    end: datetime
    start_ymd: str
    end_ymd: str
    timezone: str
    generated_at: datetime
    network: OperatorKpiRow
    operators: list[OperatorKpiRow]


def _local(at: datetime, tz: ZoneInfo = NETWORK_TZ) -> datetime:
    return as_utc(at).astimezone(tz)


def trade_day_snapshot_window(trade_date: date, tz: ZoneInfo = NETWORK_TZ) -> tuple[datetime, datetime]:
    """[local 00:00, local 21:00] converted to UTC."""
    start_local = datetime(trade_date.year, trade_date.month, trade_date.day, 0, 0, 0, tzinfo=tz)
    end_local = datetime(trade_date.year, trade_date.month, trade_date.day, DAILY_CLOSE_HOUR, 0, 0, tzinfo=tz)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def current_trade_day_window(at: datetime, tz: ZoneInfo = NETWORK_TZ) -> tuple[datetime, datetime, date]:
    """Live trade day: local midnight → now, labelled with the civil date."""
    local = _local(at, tz)
    trade_date = local.date()
    start_local = datetime(trade_date.year, trade_date.month, trade_date.day, 0, 0, 0, tzinfo=tz)
    return start_local.astimezone(timezone.utc), as_utc(at), trade_date


def same_weekday_last_week_window(at: datetime, tz: ZoneInfo = NETWORK_TZ) -> tuple[datetime, datetime, date]:
    return current_trade_day_window(as_utc(at) - timedelta(days=7), tz)


def _sunday_week_start_local(local: datetime, tz: ZoneInfo) -> datetime:
    days_since_sunday = (local.weekday() + 1) % 7
    this_sunday = datetime(local.year, local.month, local.day, WEEK_START_HOUR, 0, 0, tzinfo=tz) - timedelta(
        days=days_since_sunday
    )
    if local < this_sunday:
        this_sunday -= timedelta(days=7)
    return this_sunday


def operating_week_window(at: datetime, tz: ZoneInfo = NETWORK_TZ) -> tuple[datetime, datetime, str, str]:
    """Sunday 01:00 → Saturday 23:00 containing ``at`` (or the previous week if before Sunday 01:00)."""
    local = _local(at, tz)
    week_start = _sunday_week_start_local(local, tz)
    week_end = (week_start + timedelta(days=6)).replace(hour=WEEK_END_HOUR, minute=0, second=0, microsecond=0)
    start_utc = week_start.astimezone(timezone.utc)
    end_utc = week_end.astimezone(timezone.utc)
    return start_utc, end_utc, week_start.date().isoformat(), week_end.date().isoformat()


def prior_operating_week_window(at: datetime, tz: ZoneInfo = NETWORK_TZ) -> tuple[datetime, datetime, str, str]:
    start, _end, _sy, _ey = operating_week_window(at, tz)
    return operating_week_window(start - timedelta(seconds=1), tz)


def last_completed_operating_week(at: datetime, tz: ZoneInfo = NETWORK_TZ) -> tuple[datetime, datetime, str, str]:
    """The most recently finished operating week (after Saturday 23:00)."""
    start, end, start_ymd, end_ymd = operating_week_window(at, tz)
    if as_utc(at) >= end:
        return start, end, start_ymd, end_ymd
    return prior_operating_week_window(at, tz)


def daily_trade_dates_due(at: datetime, tz: ZoneInfo = NETWORK_TZ) -> list[date]:
    """Civil dates whose 21:00 close has passed and should have a snapshot."""
    local = _local(at, tz)
    due: list[date] = [local.date() - timedelta(days=1)]
    if local.hour > DAILY_CLOSE_HOUR or (local.hour == DAILY_CLOSE_HOUR and local.minute >= 0):
        due.insert(0, local.date())
    seen: set[date] = set()
    ordered: list[date] = []
    for day in due:
        if day not in seen:
            seen.add(day)
            ordered.append(day)
    return ordered


def weekly_compile_due(at: datetime, tz: ZoneInfo = NETWORK_TZ) -> bool:
    local = _local(at, tz)
    if local.weekday() != 5:
        return False
    if local.hour < WEEKLY_COMPILE_HOUR:
        return False
    if local.hour == WEEKLY_COMPILE_HOUR and local.minute < WEEKLY_COMPILE_MINUTE:
        return False
    return True


def _sale_timestamp():
    return sa_func.coalesce(AutoKeyInvoice.paid_at, AutoKeyInvoice.created_at)


def operator_kpis(
    session: Session,
    tenant: Tenant,
    start: datetime,
    end: datetime,
    *,
    enquiries_not_actioned: int = 0,
) -> OperatorKpiRow:
    start_n = as_utc(start)
    end_n = as_utc(end)
    tenant_id = tenant.id

    jobs = list(
        session.exec(
            select(AutoKeyJob)
            .where(AutoKeyJob.tenant_id == tenant_id)
            .where(AutoKeyJob.created_at >= start_n)
            .where(AutoKeyJob.created_at <= end_n)
        ).all()
    )
    completed = int(
        session.exec(
            select(func.count())
            .select_from(AutoKeyJob)
            .where(AutoKeyJob.tenant_id == tenant_id)
            .where(AutoKeyJob.work_completed_at.is_not(None))  # type: ignore[union-attr]
            .where(col(AutoKeyJob.work_completed_at) >= start_n)
            .where(col(AutoKeyJob.work_completed_at) <= end_n)
        ).one()
        or 0
    )
    paid_rows = list(
        session.exec(
            select(AutoKeyInvoice, AutoKeyJob)
            .join(AutoKeyJob, AutoKeyJob.id == AutoKeyInvoice.auto_key_job_id)
            .where(AutoKeyInvoice.tenant_id == tenant_id)
            .where(AutoKeyInvoice.status == "paid")
            .where(_sale_timestamp() >= start_n)
            .where(_sale_timestamp() <= end_n)
        ).all()
    )
    active_jobs = int(
        session.exec(
            select(func.count())
            .select_from(AutoKeyJob)
            .where(AutoKeyJob.tenant_id == tenant_id)
            .where(col(AutoKeyJob.status).in_(AUTO_KEY_ACTIVE_STATUSES))
        ).one()
        or 0
    )
    outstanding_cents = int(
        session.exec(
            select(func.coalesce(func.sum(AutoKeyInvoice.total_cents), 0))
            .where(AutoKeyInvoice.tenant_id == tenant_id)
            .where(col(AutoKeyInvoice.status).notin_(tuple(_EXCLUDED_INVOICE_STATUSES | {"paid"})))
        ).one()
        or 0
    )

    category_jobs = _empty_counts(CATEGORY_KEYS)
    lead_jobs = _empty_counts(LEAD_KEYS)
    customer_ids: set[UUID] = set()
    for job in jobs:
        customer_ids.add(job.customer_id)
        category_jobs[classify_job_type(job.job_type)] += 1
        lead_jobs[classify_lead_source(job.commission_lead_source)] += 1

    category_sales = _empty_counts(CATEGORY_KEYS)
    lead_sales = _empty_counts(LEAD_KEYS)
    sales_cents = 0
    for invoice, job in paid_rows:
        amount = int(invoice.total_cents or 0)
        sales_cents += amount
        category_sales[classify_job_type(job.job_type)] += amount
        lead_sales[classify_lead_source(job.commission_lead_source)] += amount

    row = OperatorKpiRow(
        operator_tenant_id=tenant.id,
        operator_name=tenant.name,
        operator_shop_number=tenant.shop_number,
        customers_count=len(customer_ids),
        jobs_created=len(jobs),
        jobs_completed=completed,
        sales_cents=sales_cents,
        category_jobs=category_jobs,
        category_sales_cents=category_sales,
        lead_jobs=lead_jobs,
        lead_sales_cents=lead_sales,
        active_jobs=active_jobs,
        outstanding_cents=outstanding_cents,
        enquiries_not_actioned=enquiries_not_actioned,
    )
    row.apply_comparisons(None)
    return row


def _sum_int_maps(rows: list[OperatorKpiRow], attr: str) -> dict[str, int]:
    keys = CATEGORY_KEYS if "category" in attr else LEAD_KEYS
    totals = _empty_counts(keys)
    for row in rows:
        mapping: dict[str, int] = getattr(row, attr)
        for key, value in mapping.items():
            totals[key] = totals.get(key, 0) + int(value)
    return totals


def rollup_operators(rows: list[OperatorKpiRow], *, name: str = "Network total") -> OperatorKpiRow:
    network = OperatorKpiRow(
        operator_tenant_id=UUID(int=0),
        operator_name=name,
        operator_shop_number=None,
        customers_count=sum(r.customers_count for r in rows),
        jobs_created=sum(r.jobs_created for r in rows),
        jobs_completed=sum(r.jobs_completed for r in rows),
        sales_cents=sum(r.sales_cents for r in rows),
        prior_sales_cents=sum(r.prior_sales_cents for r in rows),
        prior_jobs_created=sum(r.prior_jobs_created for r in rows),
        category_jobs=_sum_int_maps(rows, "category_jobs"),
        category_sales_cents=_sum_int_maps(rows, "category_sales_cents"),
        lead_jobs=_sum_int_maps(rows, "lead_jobs"),
        lead_sales_cents=_sum_int_maps(rows, "lead_sales_cents"),
        active_jobs=sum(r.active_jobs for r in rows),
        outstanding_cents=sum(r.outstanding_cents for r in rows),
        enquiries_not_actioned=sum(r.enquiries_not_actioned for r in rows),
    )
    network.sales_pct_change = pct_change(network.sales_cents, network.prior_sales_cents)
    network.avg_sale_cents = derived_avg_sale_cents(network.sales_cents, network.customers_count)
    network.jobs_per_customer = derived_jobs_per_customer(network.jobs_created, network.customers_count)
    return network


def _enquiry_backlog_by_tenant(session: Session, parent_id: UUID) -> dict[UUID, int]:
    emails = session.exec(select(InboundEmail).where(InboundEmail.parent_account_id == parent_id)).all()
    return {
        b.operator_tenant_id: b.new_count
        for b in bucket_email_leads_by_operator(session, parent_id=parent_id, emails=emails)
        if b.operator_tenant_id is not None
    }


def build_network_kpis(
    session: Session,
    parent: ParentAccount,
    start: datetime,
    end: datetime,
    *,
    prior_start: datetime | None = None,
    prior_end: datetime | None = None,
    generated_at: datetime | None = None,
) -> NetworkKpiReport:
    operators = bookable_operators_for_parent(session, parent.id)
    backlog = _enquiry_backlog_by_tenant(session, parent.id) if operators else {}
    prior_by_id: dict[UUID, OperatorKpiRow] = {}
    if prior_start is not None and prior_end is not None:
        for tenant in operators:
            prior_by_id[tenant.id] = operator_kpis(session, tenant, prior_start, prior_end)

    rows: list[OperatorKpiRow] = []
    for tenant in operators:
        row = operator_kpis(
            session,
            tenant,
            start,
            end,
            enquiries_not_actioned=backlog.get(tenant.id, 0),
        )
        row.apply_comparisons(prior_by_id.get(tenant.id))
        rows.append(row)

    rows.sort(key=lambda r: (-r.enquiries_not_actioned, r.sales_cents, r.operator_name.lower()))
    start_local = as_utc(start).astimezone(NETWORK_TZ)
    end_local = as_utc(end).astimezone(NETWORK_TZ)
    generated = generated_at or datetime.now(timezone.utc)
    return NetworkKpiReport(
        start=as_utc(start),
        end=as_utc(end),
        start_ymd=start_local.date().isoformat(),
        end_ymd=end_local.date().isoformat(),
        timezone=NETWORK_TIMEZONE_NAME,
        generated_at=generated,
        network=rollup_operators(rows),
        operators=rows,
    )


def report_to_payload(report: NetworkKpiReport) -> dict[str, Any]:
    return {
        "start": report.start.isoformat(),
        "end": report.end.isoformat(),
        "start_ymd": report.start_ymd,
        "end_ymd": report.end_ymd,
        "timezone": report.timezone,
        "generated_at": report.generated_at.isoformat(),
        "network": report.network.to_dict(),
        "operators": [row.to_dict() for row in report.operators],
    }


def csv_bytes_for_report(report: NetworkKpiReport, *, period_label: str | None = None) -> bytes:
    import csv
    import io

    label = period_label or f"{report.start_ymd} to {report.end_ymd}"
    headers = [
        "Operator",
        "Shop number",
        "Week start",
        "Week end",
        "Period",
        "Customers",
        "Jobs created",
        "Jobs completed",
        "Sales $",
        "Sales % chg",
        "Avg sale $",
        "Jobs per customer",
    ]
    for key in CATEGORY_KEYS:
        headers.append(f"{CATEGORY_LABELS[key]} jobs")
        headers.append(f"{CATEGORY_LABELS[key]} sales $")
    for key in LEAD_KEYS:
        headers.append(f"{LEAD_LABELS[key]} jobs")
        headers.append(f"{LEAD_LABELS[key]} sales $")
    headers.extend(["Enquiries not actioned", "Active jobs", "Outstanding $"])

    def _row(item: OperatorKpiRow) -> list[Any]:
        avg_dollars = "" if item.avg_sale_cents is None else f"{item.avg_sale_cents / 100:.2f}"
        jpc = "" if item.jobs_per_customer is None else f"{item.jobs_per_customer:.2f}"
        pct = "" if item.sales_pct_change is None else f"{item.sales_pct_change:.1f}"
        out: list[Any] = [
            item.operator_name,
            item.operator_shop_number or "",
            report.start_ymd,
            report.end_ymd,
            label,
            item.customers_count,
            item.jobs_created,
            item.jobs_completed,
            dollars(item.sales_cents),
            pct,
            avg_dollars,
            jpc,
        ]
        for key in CATEGORY_KEYS:
            out.append(item.category_jobs.get(key, 0))
            out.append(dollars(item.category_sales_cents.get(key, 0)))
        for key in LEAD_KEYS:
            out.append(item.lead_jobs.get(key, 0))
            out.append(dollars(item.lead_sales_cents.get(key, 0)))
        out.extend([item.enquiries_not_actioned, item.active_jobs, dollars(item.outstanding_cents)])
        return out

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    for row in report.operators:
        writer.writerow(_row(row))
    if report.operators:
        writer.writerow(_row(report.network))
    return ("\ufeff" + buf.getvalue()).encode("utf-8")
