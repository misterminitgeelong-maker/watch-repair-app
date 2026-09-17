"""Mobile Services financial reporting.

Period-based money, conversion, receivables, trends, technician and duration
figures for one shop, in its own timezone. Pure functions over pre-fetched rows
so every calculation is unit-testable; ``routes/reports.py`` fetches and calls.

Honesty rules baked in here:

* Percentages are ``None`` (never a division by zero) when the baseline is 0.
* No cost of goods is recorded on mobile jobs, so *gross margin is not reported*;
  the closest real figure is contribution after technician commission, and it
  is labelled as such.
* Actual job durations come from status-change events (En Route → On Site →
  Work Completed) and are only reported where those events exist; the sample
  size is always returned alongside.
* Working days are Monday–Saturday within the period (to date when the period
  is still in progress) — a stated convention, not a measurement.
"""
from __future__ import annotations

import csv
import io
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from .auto_key_status import AUTO_KEY_FINAL_STATUSES, canonical_auto_key_status, mobile_status_category, statuses_in_category
from .mobile_cockpit import (
    ASSUMED_JOB_MINUTES,
    INVOICE_OVERDUE_DAYS,
    TECH_DAY_MINUTES,
    Direction,
    Tone,
    as_utc,
    day_bounds_utc,
    delta,
    tone_for,
    week_start,
)
from .mobile_commission import DEFAULT_ELIGIBLE_STATUSES, commission_for_period_lines, parse_mobile_commission_rules
from .models import AutoKeyInvoice, AutoKeyJob, AutoKeyQuote, Tenant, TenantEventLog, User

FinancePreset = Literal["week", "last_week", "month", "last_month", "quarter", "last_4_weeks", "last_13_weeks", "custom"]
FINANCE_PRESETS: tuple[str, ...] = ("week", "last_week", "month", "last_month", "quarter", "last_4_weeks", "last_13_weeks", "custom")
DateField = Literal["created", "scheduled", "completed", "invoiced", "paid"]
DATE_FIELDS: tuple[str, ...] = ("created", "scheduled", "completed", "invoiced", "paid")

_EXCLUDED_INVOICE_STATUSES = ("void", "refunded")
LOST_STATUSES = statuses_in_category("lost")
BOOKED_OR_LATER = (
    statuses_in_category("booking") - {"awaiting_booking_confirmation", "pending_booking", "go_ahead"}
) | statuses_in_category("field") | statuses_in_category("completed") | statuses_in_category("paid")
AR_BUCKETS: tuple[tuple[str, str, int, int | None], ...] = (
    ("current", "0–7 days", 0, INVOICE_OVERDUE_DAYS),
    ("d8_30", "8–30 days", INVOICE_OVERDUE_DAYS + 1, 30),
    ("d31_60", "31–60 days", 31, 60),
    ("d61_plus", "61+ days", 61, None),
)


# ── Periods ──────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Period:
    start: date
    end: date  # inclusive
    label: str

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    def bounds_utc(self, tz: ZoneInfo) -> tuple[datetime, datetime]:
        start_utc, _ = day_bounds_utc(self.start, tz)
        _, end_utc = day_bounds_utc(self.end, tz)
        return start_utc, end_utc

    def contains(self, dt: datetime | None, tz: ZoneInfo) -> bool:
        if dt is None:
            return False
        local = as_utc(dt).astimezone(tz).date()
        return self.start <= local <= self.end

    def previous(self) -> "Period":
        """The same number of days immediately before this period."""
        end = self.start - timedelta(days=1)
        return Period(end - timedelta(days=self.days - 1), end, "previous period")


def _month_start(d: date) -> date:
    return d.replace(day=1)


def _month_end(d: date) -> date:
    nxt = d.replace(year=d.year + 1, month=1, day=1) if d.month == 12 else d.replace(month=d.month + 1, day=1)
    return nxt - timedelta(days=1)


def resolve_period(preset: str, today: date, date_from: str | None = None, date_to: str | None = None) -> Period:
    """Shop-local civil period for a preset. Raises ValueError on bad input."""
    if preset == "week":
        monday = week_start(today)
        return Period(monday, monday + timedelta(days=6), "This week")
    if preset == "last_week":
        monday = week_start(today) - timedelta(days=7)
        return Period(monday, monday + timedelta(days=6), "Last week")
    if preset == "month":
        return Period(_month_start(today), _month_end(today), "This month")
    if preset == "last_month":
        last = _month_start(today) - timedelta(days=1)
        return Period(_month_start(last), last, "Last month")
    if preset == "quarter":
        q_start_month = ((today.month - 1) // 3) * 3 + 1
        start = date(today.year, q_start_month, 1)
        return Period(start, _month_end(date(today.year, q_start_month + 2, 1)), "This quarter")
    if preset == "last_4_weeks":
        end = week_start(today) - timedelta(days=1)  # last completed Sunday
        return Period(end - timedelta(days=27), end, "Last 4 weeks")
    if preset == "last_13_weeks":
        end = week_start(today) - timedelta(days=1)
        return Period(end - timedelta(days=13 * 7 - 1), end, "Last 13 weeks")
    if preset == "custom":
        if not date_from or not date_to:
            raise ValueError("custom period needs date_from and date_to")
        start = datetime.strptime(date_from, "%Y-%m-%d").date()
        end = datetime.strptime(date_to, "%Y-%m-%d").date()
        if end < start:
            raise ValueError("date_to must not be before date_from")
        if (end - start).days > 400:
            raise ValueError("custom period may not exceed 400 days")
        return Period(start, end, f"{start.isoformat()} – {end.isoformat()}")
    raise ValueError(f"Unknown period preset: {preset}")


def working_days(period: Period, today: date) -> int:
    """Mon–Sat days in the period, counted only up to today when in progress."""
    end = min(period.end, today)
    if end < period.start:
        return 0
    count = 0
    d = period.start
    while d <= end:
        if d.weekday() < 6:
            count += 1
        d += timedelta(days=1)
    return count


def list_date_filter(date_field: str, date_from: str, date_to: str, *, tenant_id: UUID, tz: ZoneInfo):
    """SQL clause for the list endpoint matching a finance drill-down (shop-local civil dates)."""
    from sqlalchemy import and_
    from sqlmodel import select as sql_select

    from .mobile_cockpit import naive_utc

    period = resolve_period("custom", date.today(), date_from, date_to)
    start_utc, end_utc = period.bounds_utc(tz)
    lo, hi = naive_utc(start_utc), naive_utc(end_utc)
    if date_field == "created":
        return and_(AutoKeyJob.created_at >= lo, AutoKeyJob.created_at < hi)
    if date_field == "scheduled":
        return and_(AutoKeyJob.scheduled_at >= lo, AutoKeyJob.scheduled_at < hi)
    if date_field == "completed":
        return and_(AutoKeyJob.work_completed_at >= lo, AutoKeyJob.work_completed_at < hi)
    if date_field == "invoiced":
        raised = (
            sql_select(AutoKeyInvoice.auto_key_job_id)
            .where(AutoKeyInvoice.tenant_id == tenant_id)
            .where(AutoKeyInvoice.status.notin_(_EXCLUDED_INVOICE_STATUSES))
            .where(AutoKeyInvoice.created_at >= lo, AutoKeyInvoice.created_at < hi)
        )
        return AutoKeyJob.id.in_(raised)
    if date_field == "paid":
        paid = (
            sql_select(AutoKeyInvoice.auto_key_job_id)
            .where(AutoKeyInvoice.tenant_id == tenant_id)
            .where(AutoKeyInvoice.status == "paid")
            .where(AutoKeyInvoice.paid_at >= lo, AutoKeyInvoice.paid_at < hi)
        )
        return AutoKeyJob.id.in_(paid)
    raise ValueError(f"Unknown date_field: {date_field}")


# ── Metric assembly ──────────────────────────────────────────────────────────
def compare(
    *,
    key: str,
    label: str,
    unit: Literal["cents", "count", "pct", "minutes"],
    current: float | None,
    previous: float | None,
    direction: Direction,
    definition: str,
    drill: dict[str, Any] | None = None,
    sample: int | None = None,
) -> dict[str, Any]:
    vs = None if current is None or previous is None else delta(current, previous)
    return {
        "key": key,
        "label": label,
        "unit": unit,
        "definition": definition,
        "direction": direction,
        "current": current,
        "previous": previous,
        "vs_previous": vs,
        "vs_previous_tone": tone_for(direction, vs["abs"] if vs else None),
        "drill": drill,
        "sample": sample,
    }


def _local_day(dt: datetime | None, tz: ZoneInfo) -> date | None:
    u = as_utc(dt)
    return u.astimezone(tz).date() if u else None


def _invoice_value(job: AutoKeyJob, inv: AutoKeyInvoice | None) -> int:
    if inv and inv.status not in _EXCLUDED_INVOICE_STATUSES:
        return inv.total_cents
    return max(0, job.cost_cents or 0)


@dataclass
class PeriodFigures:
    booked: int = 0
    booked_jobs: int = 0
    completed: int = 0
    completed_jobs: int = 0
    invoiced: int = 0
    invoices: int = 0
    collected: int = 0
    paid_invoices: int = 0
    jobs_created: int = 0
    quotes_sent: int = 0
    quotes_approved: int = 0
    quotes_sent_value: int = 0
    leads_booked: int = 0  # jobs created in period that reached a confirmed booking or later
    bookings_completed: int = 0  # jobs scheduled in period whose work is completed
    commission: int = 0


def period_figures(
    *,
    period: Period,
    tz: ZoneInfo,
    jobs: list[AutoKeyJob],
    invoices: list[AutoKeyInvoice],
    invoice_by_job: dict[UUID, AutoKeyInvoice],
    quotes: list[AutoKeyQuote],
    commission_by_invoice: dict[UUID, int],
) -> PeriodFigures:
    f = PeriodFigures()
    for job in jobs:
        if period.contains(job.created_at, tz):
            f.jobs_created += 1
            if job.status in BOOKED_OR_LATER:
                f.leads_booked += 1
        if job.scheduled_at and job.status not in LOST_STATUSES and period.contains(job.scheduled_at, tz):
            f.booked += max(0, job.cost_cents or 0)
            f.booked_jobs += 1
            if job.work_completed_at:
                f.bookings_completed += 1
        if job.work_completed_at and period.contains(job.work_completed_at, tz):
            f.completed += _invoice_value(job, invoice_by_job.get(job.id))
            f.completed_jobs += 1
    for inv in invoices:
        if inv.status in _EXCLUDED_INVOICE_STATUSES:
            continue
        if period.contains(inv.created_at, tz):
            f.invoiced += inv.total_cents
            f.invoices += 1
        if inv.status == "paid" and inv.paid_at and period.contains(inv.paid_at, tz):
            f.collected += inv.total_cents
            f.paid_invoices += 1
            f.commission += commission_by_invoice.get(inv.id, 0)
    for q in quotes:
        sent = q.sent_at or (q.created_at if q.status != "draft" else None)
        if sent and period.contains(sent, tz):
            f.quotes_sent += 1
            f.quotes_sent_value += q.total_cents
            if q.status == "approved":
                f.quotes_approved += 1
    return f


def pct(numerator: float, denominator: float) -> float | None:
    if not denominator:
        return None
    return round(numerator / denominator * 100, 1)


def outstanding_as_of(invoices: Iterable[AutoKeyInvoice], as_of: datetime) -> tuple[int, int]:
    """(cents, count) of invoices raised by ``as_of`` and not paid by then."""
    cents = count = 0
    for inv in invoices:
        if inv.status in _EXCLUDED_INVOICE_STATUSES:
            continue
        created = as_utc(inv.created_at)
        if created is None or created > as_of:
            continue
        paid_at = as_utc(inv.paid_at) if inv.status == "paid" else None
        if paid_at is not None and paid_at <= as_of:
            continue
        cents += inv.total_cents
        count += 1
    return cents, count


def ar_ageing(invoices: Iterable[AutoKeyInvoice], now: datetime) -> dict[str, Any]:
    buckets = {key: {"key": key, "label": label, "cents": 0, "count": 0} for key, label, _lo, _hi in AR_BUCKETS}
    total = 0
    for inv in invoices:
        if inv.status in ("paid", *_EXCLUDED_INVOICE_STATUSES):
            continue
        age = (now - as_utc(inv.created_at)).days if inv.created_at else 0
        for key, _label, lo, hi in AR_BUCKETS:
            if age >= lo and (hi is None or age <= hi):
                buckets[key]["cents"] += inv.total_cents
                buckets[key]["count"] += 1
                break
        total += inv.total_cents
    overdue = total - buckets["current"]["cents"]
    return {
        "total_cents": total,
        "overdue_cents": overdue,
        "overdue_pct": pct(overdue, total),
        "buckets": list(buckets.values()),
    }


def weekly_trend(
    *,
    weeks: int,
    end_week_start: date,
    tz: ZoneInfo,
    jobs: list[AutoKeyJob],
    invoices: list[AutoKeyInvoice],
    invoice_by_job: dict[UUID, AutoKeyInvoice],
) -> list[dict[str, Any]]:
    """Per-week rows for the ``weeks`` Monday-weeks ending with ``end_week_start``."""
    starts = [end_week_start - timedelta(days=7 * n) for n in range(weeks - 1, -1, -1)]
    rows = {s: {"week_start": s.isoformat(), "booked_cents": 0, "completed_cents": 0, "invoiced_cents": 0, "collected_cents": 0, "jobs_completed": 0, "jobs_created": 0} for s in starts}

    def bucket(dt: datetime | None) -> dict | None:
        d = _local_day(dt, tz)
        if d is None:
            return None
        return rows.get(week_start(d))

    for job in jobs:
        if (r := bucket(job.created_at)) is not None:
            r["jobs_created"] += 1
        if job.scheduled_at and job.status not in LOST_STATUSES and (r := bucket(job.scheduled_at)) is not None:
            r["booked_cents"] += max(0, job.cost_cents or 0)
        if job.work_completed_at and (r := bucket(job.work_completed_at)) is not None:
            r["jobs_completed"] += 1
            r["completed_cents"] += _invoice_value(job, invoice_by_job.get(job.id))
    for inv in invoices:
        if inv.status in _EXCLUDED_INVOICE_STATUSES:
            continue
        if (r := bucket(inv.created_at)) is not None:
            r["invoiced_cents"] += inv.total_cents
        if inv.status == "paid" and inv.paid_at and (r := bucket(inv.paid_at)) is not None:
            r["collected_cents"] += inv.total_cents
    return [rows[s] for s in starts]


def trend_averages(rows: list[dict[str, Any]], key: str) -> dict[str, float | None]:
    values = [r[key] for r in rows]
    def avg(n: int) -> float | None:
        tail = values[-n:]
        return round(sum(tail) / len(tail), 2) if len(tail) == n else None
    return {"last_4_avg": avg(4), "last_13_avg": avg(13), "latest": values[-1] if values else None}


# ── Durations from the job event log ─────────────────────────────────────────
@dataclass
class JobTimeline:
    en_route_at: datetime | None = None
    on_site_at: datetime | None = None


def timelines_from_events(events: Iterable[TenantEventLog]) -> dict[UUID, JobTimeline]:
    """Earliest En Route / On Site transition per job, from status-change events.

    The event summary is the only record of the transition time today
    (``"Status changed from X to On Site"``); this reads it back rather than
    inventing a new table for a figure we already log.
    """
    timelines: dict[UUID, JobTimeline] = defaultdict(JobTimeline)
    for ev in events:
        if ev.entity_id is None or ev.event_type != "auto_key_status_changed":
            continue
        summary = ev.event_summary or ""
        target = summary.split(" to ", 1)[1] if " to " in summary else ""
        target = target.split(" — ", 1)[0].strip().lower()
        when = as_utc(ev.created_at)
        if when is None:
            continue
        tl = timelines[ev.entity_id]
        if target == "on site" and (tl.on_site_at is None or when < tl.on_site_at):
            tl.on_site_at = when
        elif target == "en route" and (tl.en_route_at is None or when < tl.en_route_at):
            tl.en_route_at = when
    return dict(timelines)


def duration_stats(minutes: list[float]) -> dict[str, Any]:
    if not minutes:
        return {"count": 0, "avg_minutes": None, "median_minutes": None, "p90_minutes": None}
    ordered = sorted(minutes)
    p90_index = min(len(ordered) - 1, int(round(0.9 * (len(ordered) - 1))))
    return {
        "count": len(ordered),
        "avg_minutes": round(sum(ordered) / len(ordered), 1),
        "median_minutes": round(statistics.median(ordered), 1),
        "p90_minutes": round(ordered[p90_index], 1),
    }


def job_durations(jobs: Iterable[AutoKeyJob], timelines: dict[UUID, JobTimeline]) -> dict[str, Any]:
    """On-site minutes (On Site → Work Completed) and travel minutes (En Route → On Site)."""
    on_site: list[float] = []
    travel: list[float] = []
    by_type: dict[str, list[float]] = defaultdict(list)
    by_tech: dict[UUID, list[float]] = defaultdict(list)
    for job in jobs:
        tl = timelines.get(job.id)
        if not tl:
            continue
        done = as_utc(job.work_completed_at)
        if tl.on_site_at and done and done > tl.on_site_at:
            mins = (done - tl.on_site_at).total_seconds() / 60
            if mins <= 12 * 60:  # anything longer is a forgotten status, not a job
                on_site.append(mins)
                by_type[job.job_type or "Unknown"].append(mins)
                if job.assigned_user_id:
                    by_tech[job.assigned_user_id].append(mins)
        if tl.en_route_at and tl.on_site_at and tl.on_site_at > tl.en_route_at:
            mins = (tl.on_site_at - tl.en_route_at).total_seconds() / 60
            if mins <= 4 * 60:
                travel.append(mins)
    return {
        "estimated_minutes": ASSUMED_JOB_MINUTES,
        "estimate_source": "assumed",
        "on_site": duration_stats(on_site),
        "travel": duration_stats(travel),
        "by_job_type": sorted(
            ({"job_type": t, **duration_stats(v)} for t, v in by_type.items()),
            key=lambda r: -r["count"],
        ),
        "_by_tech": {uid: duration_stats(v) for uid, v in by_tech.items()},
    }


# ── Technician table ─────────────────────────────────────────────────────────
def technician_table(
    *,
    users: Iterable[User],
    period: Period,
    tz: ZoneInfo,
    jobs: list[AutoKeyJob],
    invoices: list[AutoKeyInvoice],
    job_by_id: dict[UUID, AutoKeyJob],
    commission_by_invoice: dict[UUID, int],
    durations_by_tech: dict[UUID, dict[str, Any]],
    working_day_count: int,
) -> list[dict[str, Any]]:
    stats: dict[UUID, dict[str, Any]] = {}

    def row(uid: UUID) -> dict[str, Any]:
        return stats.setdefault(uid, {"jobs_scheduled": 0, "jobs_completed": 0, "invoiced_cents": 0, "collected_cents": 0, "commission_cents": 0, "booked_minutes": 0})

    for job in jobs:
        if not job.assigned_user_id:
            continue
        if job.scheduled_at and job.status not in LOST_STATUSES and period.contains(job.scheduled_at, tz):
            r = row(job.assigned_user_id)
            r["jobs_scheduled"] += 1
            r["booked_minutes"] += ASSUMED_JOB_MINUTES
        if job.work_completed_at and period.contains(job.work_completed_at, tz):
            row(job.assigned_user_id)["jobs_completed"] += 1
    for inv in invoices:
        if inv.status in _EXCLUDED_INVOICE_STATUSES:
            continue
        job = job_by_id.get(inv.auto_key_job_id)
        if not job or not job.assigned_user_id:
            continue
        if period.contains(inv.created_at, tz):
            row(job.assigned_user_id)["invoiced_cents"] += inv.total_cents
        if inv.status == "paid" and inv.paid_at and period.contains(inv.paid_at, tz):
            r = row(job.assigned_user_id)
            r["collected_cents"] += inv.total_cents
            r["commission_cents"] += commission_by_invoice.get(inv.id, 0)

    capacity = working_day_count * TECH_DAY_MINUTES
    out = []
    for user in users:
        if not user.is_active or (user.role != "tech" and user.id not in stats):
            continue
        r = stats.get(user.id, {"jobs_scheduled": 0, "jobs_completed": 0, "invoiced_cents": 0, "collected_cents": 0, "commission_cents": 0, "booked_minutes": 0})
        out.append(
            {
                "user_id": str(user.id),
                "name": user.full_name,
                **r,
                "capacity_minutes": capacity,
                "utilisation_pct": pct(min(r["booked_minutes"], capacity), capacity) if capacity else None,
                "revenue_per_job_cents": round(r["collected_cents"] / r["jobs_completed"]) if r["jobs_completed"] else None,
                "on_site": durations_by_tech.get(user.id, duration_stats([])),
            }
        )
    out.sort(key=lambda r: (-r["collected_cents"], -r["jobs_completed"], r["name"].lower()))
    return out


# ── Commission (contribution after commission, the only real cost data) ──────
def commission_by_invoice_for(users: Iterable[User], jobs: list[AutoKeyJob], invoice_by_job: dict[UUID, AutoKeyInvoice]) -> tuple[dict[UUID, int], bool]:
    """Commission cents per invoice under each technician's rules; flag whether any rules are enabled."""
    result: dict[UUID, int] = {}
    any_rules = False
    jobs_by_user: dict[UUID, list[AutoKeyJob]] = defaultdict(list)
    for job in jobs:
        if job.assigned_user_id:
            jobs_by_user[job.assigned_user_id].append(job)
    for user in users:
        rules = parse_mobile_commission_rules(user.mobile_commission_rules_json)
        if not rules or not rules.get("enabled"):
            continue
        any_rules = True
        eligible = set(rules.get("eligible_job_statuses", list(DEFAULT_ELIGIBLE_STATUSES)))
        lines = [
            (j.id, j.job_number, invoice_by_job[j.id].id, invoice_by_job[j.id].total_cents, j.commission_lead_source, j.status)
            for j in jobs_by_user.get(user.id, [])
            if j.status in eligible and j.id in invoice_by_job and invoice_by_job[j.id].total_cents > 0
        ]
        _total, commission_lines = commission_for_period_lines(rules=rules, lines_data=lines)
        for line in commission_lines:
            result[line.invoice_id] = line.commission_cents
    return result, any_rules


# ── CSV ──────────────────────────────────────────────────────────────────────
def summary_csv(report: dict[str, Any]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    p = report["period"]
    w.writerow(["Mobile Services finance summary", p["label"], f"{p['start']} to {p['end']}", f"timezone {report['timezone']}"])
    w.writerow(["metric", "current", "previous", "change", "change_pct", "unit", "definition"])
    for m in report["metrics"]:
        vs = m["vs_previous"] or {}
        w.writerow([m["label"], _csv_number(m["current"], m["unit"]), _csv_number(m["previous"], m["unit"]), _csv_number(vs.get("abs"), m["unit"]), vs.get("pct", ""), m["unit"], m["definition"]])
    w.writerow([])
    w.writerow(["conversion", "numerator", "denominator", "pct"])
    for c in report["conversion"]:
        w.writerow([c["label"], c["numerator"], c["denominator"], "" if c["pct"] is None else c["pct"]])
    w.writerow([])
    w.writerow(["receivables bucket", "invoices", "amount"])
    for b in report["ar_ageing"]["buckets"]:
        w.writerow([b["label"], b["count"], _csv_number(b["cents"], "cents")])
    w.writerow([])
    w.writerow(["week_start", "booked", "completed", "invoiced", "collected", "jobs_completed", "jobs_created"])
    for r in report["trend"]["weeks"]:
        w.writerow([r["week_start"], _csv_number(r["booked_cents"], "cents"), _csv_number(r["completed_cents"], "cents"), _csv_number(r["invoiced_cents"], "cents"), _csv_number(r["collected_cents"], "cents"), r["jobs_completed"], r["jobs_created"]])
    w.writerow([])
    w.writerow(["technician", "jobs_scheduled", "jobs_completed", "invoiced", "collected", "commission", "utilisation_pct", "avg_on_site_minutes", "on_site_sample"])
    for t in report["technicians"]:
        w.writerow([t["name"], t["jobs_scheduled"], t["jobs_completed"], _csv_number(t["invoiced_cents"], "cents"), _csv_number(t["collected_cents"], "cents"), _csv_number(t["commission_cents"], "cents"), "" if t["utilisation_pct"] is None else t["utilisation_pct"], "" if t["on_site"]["avg_minutes"] is None else t["on_site"]["avg_minutes"], t["on_site"]["count"]])
    return buf.getvalue()


def _csv_number(value: Any, unit: str) -> Any:
    if value is None or value == "":
        return ""
    if unit == "cents":
        return f"{value / 100:.2f}"
    return value


def invoices_csv(rows: list[dict[str, Any]]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["invoice_number", "job_number", "customer", "technician", "job_status", "invoice_status", "raised_on", "paid_on", "age_days", "total", "payment_method"])
    for r in rows:
        w.writerow([r["invoice_number"], r["job_number"], r["customer_name"] or "", r["technician"] or "", r["job_status"], r["invoice_status"], r["raised_on"], r["paid_on"] or "", r["age_days"], f"{r['total_cents'] / 100:.2f}", r["payment_method"] or ""])
    return buf.getvalue()


# ── Whole report ─────────────────────────────────────────────────────────────
DEFINITIONS: dict[str, str] = {
    "booked": "Sell value (job price) of jobs scheduled in the period; failed / no-go excluded.",
    "completed": "Value of jobs whose work was completed in the period (invoice total, else job price).",
    "invoiced": "Invoices raised in the period, excluding void/refunded.",
    "collected": "Invoices paid in the period, by paid date.",
    "outstanding": "Unpaid invoices at the end of the period (raised by then, not paid by then).",
    "commission": "Technician commission on cash collected in the period, under each technician's rules.",
    "contribution": "Cash collected minus technician commission. Not a gross margin: no parts or cost of goods are recorded on mobile jobs.",
    "aov": "Average paid invoice in the period.",
    "jobs_per_working_day": "Jobs completed divided by Mon–Sat days in the period (to date when in progress).",
    "jobs_created": "Jobs created in the period (leads and bookings).",
    "jobs_completed": "Jobs whose work was completed in the period.",
    "quotes_sent": "Quotes sent in the period (by sent date).",
    "target": "Weekly cash-collected target pro-rated to the period's days.",
}


def build_finance_report(
    *,
    tenant: Tenant | None,
    tz: ZoneInfo,
    now: datetime,
    period: Period,
    preset: str,
    jobs: list[AutoKeyJob],
    invoices: list[AutoKeyInvoice],
    quotes: list[AutoKeyQuote],
    users: list[User],
    events: list[TenantEventLog],
    customer_names: dict[UUID, str],
) -> dict[str, Any]:
    today = now.astimezone(tz).date()
    previous = period.previous()
    invoice_by_job: dict[UUID, AutoKeyInvoice] = {}
    for inv in sorted(invoices, key=lambda i: as_utc(i.created_at) or now):
        invoice_by_job[inv.auto_key_job_id] = inv
    job_by_id = {j.id: j for j in jobs}
    commission_by_invoice, commission_enabled = commission_by_invoice_for(users, jobs, invoice_by_job)

    cur = period_figures(period=period, tz=tz, jobs=jobs, invoices=invoices, invoice_by_job=invoice_by_job, quotes=quotes, commission_by_invoice=commission_by_invoice)
    prev = period_figures(period=previous, tz=tz, jobs=jobs, invoices=invoices, invoice_by_job=invoice_by_job, quotes=quotes, commission_by_invoice=commission_by_invoice)
    _cur_start, cur_end_utc = period.bounds_utc(tz)
    _prev_start, prev_end_utc = previous.bounds_utc(tz)
    out_cents, out_count = outstanding_as_of(invoices, min(cur_end_utc, now))
    prev_out_cents, _ = outstanding_as_of(invoices, min(prev_end_utc, now))
    wd = working_days(period, today)
    prev_wd = working_days(previous, today)
    target_weekly = tenant.mobile_weekly_target_cents if tenant else None
    target = None if target_weekly is None else round(target_weekly * period.days / 7)
    elapsed_days = max(0, (min(period.end, today) - period.start).days + 1)
    target_to_date = None if target_weekly is None else round(target_weekly * elapsed_days / 7)

    def drill(date_field: str, p: Period, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        return {"date_field": date_field, "date_from": p.start.isoformat(), "date_to": p.end.isoformat(), "directory": "all", **(extra or {})}

    metrics = [
        compare(key="booked", label="Booked", unit="cents", current=cur.booked, previous=prev.booked, direction="higher_is_better", definition=DEFINITIONS["booked"], drill=drill("scheduled", period), sample=cur.booked_jobs),
        compare(key="completed", label="Completed", unit="cents", current=cur.completed, previous=prev.completed, direction="higher_is_better", definition=DEFINITIONS["completed"], drill=drill("completed", period), sample=cur.completed_jobs),
        compare(key="invoiced", label="Invoiced", unit="cents", current=cur.invoiced, previous=prev.invoiced, direction="higher_is_better", definition=DEFINITIONS["invoiced"], drill=drill("invoiced", period), sample=cur.invoices),
        compare(key="collected", label="Cash collected", unit="cents", current=cur.collected, previous=prev.collected, direction="higher_is_better", definition=DEFINITIONS["collected"], drill=drill("paid", period), sample=cur.paid_invoices),
        compare(key="outstanding", label="Outstanding at period end", unit="cents", current=out_cents, previous=prev_out_cents, direction="lower_is_better", definition=DEFINITIONS["outstanding"], drill={"focus": "unpaid_invoices"}, sample=out_count),
        compare(key="commission", label="Technician commission", unit="cents", current=cur.commission if commission_enabled else None, previous=prev.commission if commission_enabled else None, direction="neutral", definition=DEFINITIONS["commission"]),
        compare(key="contribution", label="After commission", unit="cents", current=(cur.collected - cur.commission) if commission_enabled else None, previous=(prev.collected - prev.commission) if commission_enabled else None, direction="higher_is_better", definition=DEFINITIONS["contribution"]),
        compare(key="aov", label="Average order value", unit="cents", current=round(cur.collected / cur.paid_invoices) if cur.paid_invoices else None, previous=round(prev.collected / prev.paid_invoices) if prev.paid_invoices else None, direction="higher_is_better", definition=DEFINITIONS["aov"], sample=cur.paid_invoices),
        compare(key="jobs_completed", label="Jobs completed", unit="count", current=cur.completed_jobs, previous=prev.completed_jobs, direction="higher_is_better", definition=DEFINITIONS["jobs_completed"], drill=drill("completed", period)),
        compare(key="jobs_per_working_day", label="Jobs per working day", unit="count", current=round(cur.completed_jobs / wd, 2) if wd else None, previous=round(prev.completed_jobs / prev_wd, 2) if prev_wd else None, direction="higher_is_better", definition=DEFINITIONS["jobs_per_working_day"], sample=wd),
        compare(key="jobs_created", label="Jobs created", unit="count", current=cur.jobs_created, previous=prev.jobs_created, direction="neutral", definition=DEFINITIONS["jobs_created"], drill=drill("created", period)),
        compare(key="quotes_sent", label="Quotes sent", unit="count", current=cur.quotes_sent, previous=prev.quotes_sent, direction="neutral", definition=DEFINITIONS["quotes_sent"], sample=cur.quotes_sent_value),
    ]

    conversion = [
        {"key": "quote_to_approved", "label": "Quote → approved", "numerator": cur.quotes_approved, "denominator": cur.quotes_sent, "pct": pct(cur.quotes_approved, cur.quotes_sent), "previous_pct": pct(prev.quotes_approved, prev.quotes_sent), "definition": "Quotes sent in the period that are approved (so far)."},
        {"key": "lead_to_booking", "label": "Lead → booking", "numerator": cur.leads_booked, "denominator": cur.jobs_created, "pct": pct(cur.leads_booked, cur.jobs_created), "previous_pct": pct(prev.leads_booked, prev.jobs_created), "definition": "Jobs created in the period that reached a confirmed booking or later."},
        {"key": "booking_to_completion", "label": "Booking → completed", "numerator": cur.bookings_completed, "denominator": cur.booked_jobs, "pct": pct(cur.bookings_completed, cur.booked_jobs), "previous_pct": pct(prev.bookings_completed, prev.booked_jobs), "definition": "Jobs scheduled in the period whose work is completed (so far)."},
    ]
    for c in conversion:
        c["vs_previous_tone"] = tone_for("higher_is_better", None if c["pct"] is None or c["previous_pct"] is None else c["pct"] - c["previous_pct"])

    trend_end = week_start(min(period.end, today))
    weeks = weekly_trend(weeks=13, end_week_start=trend_end, tz=tz, jobs=jobs, invoices=invoices, invoice_by_job=invoice_by_job)
    trend = {"weeks": weeks, "averages": {k: trend_averages(weeks, k) for k in ("booked_cents", "completed_cents", "invoiced_cents", "collected_cents", "jobs_completed", "jobs_created")}}

    timelines = timelines_from_events(events)
    completed_in_period = [j for j in jobs if j.work_completed_at and period.contains(j.work_completed_at, tz)]
    durations = job_durations(completed_in_period, timelines)
    by_tech_durations = durations.pop("_by_tech")
    techs = technician_table(users=users, period=period, tz=tz, jobs=jobs, invoices=invoices, job_by_id=job_by_id, commission_by_invoice=commission_by_invoice, durations_by_tech=by_tech_durations, working_day_count=wd)

    ageing = ar_ageing(invoices, now)
    open_rows = []
    for inv in invoices:
        if inv.status in ("paid", *_EXCLUDED_INVOICE_STATUSES):
            continue
        job = job_by_id.get(inv.auto_key_job_id)
        if not job:
            continue
        open_rows.append({
            "invoice_id": str(inv.id), "invoice_number": inv.invoice_number, "job_id": str(job.id), "job_number": job.job_number,
            "customer_name": customer_names.get(job.customer_id), "total_cents": inv.total_cents,
            "age_days": (now - as_utc(inv.created_at)).days if inv.created_at else 0,
            "raised_on": _local_day(inv.created_at, tz).isoformat() if inv.created_at else None,
        })
    open_rows.sort(key=lambda r: -r["age_days"])

    unpriced = sum(1 for j in jobs if j.scheduled_at and (j.cost_cents or 0) <= 0 and j.status not in LOST_STATUSES and period.contains(j.scheduled_at, tz))
    paid_without_date = sum(1 for i in invoices if i.status == "paid" and not i.paid_at)
    data_quality = [
        {"code": "no_cost_data", "message": "No parts or cost-of-goods figures are recorded on mobile jobs, so gross margin is not reported. After-commission uses technician commission rules as the only real cost.", "count": None},
    ]
    if not commission_enabled:
        data_quality.append({"code": "no_commission_rules", "message": "No technician has commission rules enabled, so commission and after-commission figures are hidden.", "count": None})
    if unpriced:
        data_quality.append({"code": "unpriced_bookings", "message": "Scheduled jobs in the period with no price understate Booked.", "count": unpriced})
    if paid_without_date:
        data_quality.append({"code": "paid_without_date", "message": "Paid invoices with no paid date are excluded from Cash collected.", "count": paid_without_date})
    if durations["on_site"]["count"] < len(completed_in_period):
        data_quality.append({"code": "duration_sample", "message": f"On-site durations exist for {durations['on_site']['count']} of {len(completed_in_period)} completed jobs (needs an On Site status change); estimated duration is an assumed {ASSUMED_JOB_MINUTES} min.", "count": len(completed_in_period) - durations["on_site"]["count"]})
    if target_weekly is None:
        data_quality.append({"code": "no_target", "message": "No weekly cash target is set; target variance is hidden until an owner sets one.", "count": None})
    data_quality.append({"code": "no_geocoding", "message": "Job locations are not geocoded; travel minutes come only from En Route to On Site status changes, and no clustering is estimated.", "count": None})

    return {
        "preset": preset,
        "timezone": str(tz.key),
        "generated_at": now.isoformat(),
        "period": {"label": period.label, "start": period.start.isoformat(), "end": period.end.isoformat(), "days": period.days, "elapsed_days": elapsed_days, "working_days": wd, "complete": period.end < today, "previous_start": previous.start.isoformat(), "previous_end": previous.end.isoformat()},
        "metrics": metrics,
        "target": None if target is None else {
            "weekly_cents": target_weekly,
            "period_cents": target,
            "to_date_cents": target_to_date,
            "collected_cents": cur.collected,
            "variance_cents": cur.collected - (target_to_date or 0),
            "attainment_pct": pct(cur.collected, target_to_date or 0),
            "tone": tone_for("higher_is_better", cur.collected - (target_to_date or 0)),
        },
        "conversion": conversion,
        "ar_ageing": {**ageing, "open_invoices": open_rows[:25]},
        "trend": trend,
        "technicians": techs,
        "durations": durations,
        "definitions": DEFINITIONS,
        "data_quality": data_quality,
    }
