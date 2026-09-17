"""Mobile Services operations cockpit.

One place that answers, for a shop, in its own timezone:

* what needs attention now (late, unscheduled, unassigned, on hold, in the field),
* which quotes, bookings and invoices need a follow-up,
* who has technician capacity today,
* how the money ladder (booked → completed → invoiced → collected → outstanding)
  is tracking this week against last week, the four-week average and the target.

Every headline number is defined here as a *focus* — a SQL filter over
``AutoKeyJob`` that the paginated list endpoint applies verbatim — so a tile
always drills into exactly the rows it counted. Period arithmetic is pure and
unit-tested; the route in ``routes/reports.py`` only fetches rows and calls in.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import and_, or_
from sqlmodel import select

from .auto_key_status import (
    AUTO_KEY_AWAITING_CONFIRMATION_STATUSES,
    AUTO_KEY_COMPLETED_UNPAID_STATUSES,
    AUTO_KEY_FINAL_STATUSES,
    MOBILE_STATUS_DEFINITIONS,
    canonical_auto_key_status,
    mobile_status_category,
    statuses_in_category,
)
from .config import settings
from .models import AutoKeyInvoice, AutoKeyJob, AutoKeyQuote, Tenant, User

# ── Assumptions the cockpit is honest about ──────────────────────────────────
#: No estimated duration is recorded on a job yet, so capacity maths assumes this.
ASSUMED_JOB_MINUTES = 60
#: Working day used for technician capacity.
TECH_DAY_MINUTES = 8 * 60
#: A quote with no decision after this many days is a follow-up.
QUOTE_FOLLOW_UP_DAYS = 2
#: A booking request the customer has not confirmed after this long is a follow-up.
CONFIRMATION_FOLLOW_UP_HOURS = 24
#: An unpaid invoice older than this is overdue.
INVOICE_OVERDUE_DAYS = 7
#: Two bookings for one technician closer than this are a schedule conflict.
CONFLICT_WINDOW_MINUTES = ASSUMED_JOB_MINUTES

FIELD_STATUSES = statuses_in_category("field")
LOST_STATUSES = statuses_in_category("lost")
ON_HOLD_STATUSES = frozenset({"booking_on_hold"} | set(next(d for d in MOBILE_STATUS_DEFINITIONS if d.key == "booking_on_hold").aliases))
QUOTE_SENT_STATUSES = frozenset({"quote_sent", "awaiting_go_ahead"})
NEEDS_QUOTE_STATUSES = frozenset({"awaiting_quote", "awaiting_customer_details"})
_EXCLUDED_INVOICE_STATUSES = ("void", "refunded")

Tone = Literal["bad", "warn", "good", "neutral"]
Direction = Literal["higher_is_better", "lower_is_better", "neutral"]


def tenant_timezone(tenant: Tenant | None) -> ZoneInfo:
    """The shop's configured zone, falling back to the platform schedule zone."""
    for name in ((getattr(tenant, "timezone", None) or "").strip(), settings.schedule_calendar_timezone):
        if not name:
            continue
        try:
            return ZoneInfo(name)
        except Exception:
            continue
    return ZoneInfo("UTC")


def as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def naive_utc(dt: datetime) -> datetime:
    """SQL comparisons: scheduled_at / created_at are stored as naive UTC."""
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def day_bounds_utc(day: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """Inclusive-exclusive UTC bounds of a shop-local civil day."""
    start = datetime(day.year, day.month, day.day, tzinfo=tz)
    return start.astimezone(timezone.utc), (start + timedelta(days=1)).astimezone(timezone.utc)


def week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def week_bounds_utc(now: datetime, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """UTC bounds of the shop-local Monday-Sunday week containing ``now``."""
    start = week_start(now.astimezone(tz).date())
    start_utc, _ = day_bounds_utc(start, tz)
    _, end_utc = day_bounds_utc(start + timedelta(days=6), tz)
    return start_utc, end_utc


# ── Focus definitions (shared by cockpit tiles and the list endpoint) ─────────
@dataclass(frozen=True)
class FocusDefinition:
    key: str
    label: str
    description: str
    tone: Tone
    #: Which directory the list should show when drilling in.
    directory: Literal["active", "completed", "all"] = "active"
    #: attention = needs action now; follow_up = commercial chase; period = this-week drill-downs.
    group: Literal["attention", "follow_up", "period"] = "attention"


FOCUS_DEFINITIONS: tuple[FocusDefinition, ...] = (
    FocusDefinition("late", "Late", "Booked time has passed and the technician is not yet en route.", "bad"),
    FocusDefinition("today", "Booked today", "Active jobs scheduled today.", "neutral"),
    FocusDefinition("in_field", "In the field", "Technician en route or on site right now.", "good"),
    FocusDefinition("unscheduled", "Unscheduled", "Active jobs with no booking time.", "warn"),
    FocusDefinition("unassigned", "Unassigned", "Active jobs with no technician.", "warn"),
    FocusDefinition("on_hold", "On hold", "Bookings waiting on parts, a third party or the customer.", "warn"),
    FocusDefinition("needs_quote", "Needs a quote", "New work that has not been priced.", "warn"),
    FocusDefinition("quote_follow_up", "Quote follow-up", f"Quote sent, no answer for {QUOTE_FOLLOW_UP_DAYS}+ days.", "warn", "active", "follow_up"),
    FocusDefinition(
        "confirmation_follow_up",
        "Confirmation follow-up",
        f"Booking sent to the customer, unconfirmed for {CONFIRMATION_FOLLOW_UP_HOURS}+ hours.",
        "warn",
        "active",
        "follow_up",
    ),
    FocusDefinition("completed_unpaid", "Completed, not paid", "Work is done; the invoice is not paid.", "warn", "completed", "follow_up"),
    FocusDefinition(
        "overdue_invoices",
        "Overdue invoices",
        f"Unpaid invoice older than {INVOICE_OVERDUE_DAYS} days.",
        "bad",
        "all",
        "follow_up",
    ),
    FocusDefinition("unpaid_invoices", "Unpaid invoices", "Any invoice not yet paid (excluding void/refunded).", "warn", "all", "period"),
    FocusDefinition("this_week", "Booked this week", "Jobs scheduled in the current shop week (failed / no-go excluded).", "neutral", "all", "period"),
    FocusDefinition("completed_this_week", "Completed this week", "Jobs whose work was completed in the current shop week.", "neutral", "all", "period"),
    FocusDefinition("invoiced_this_week", "Invoiced this week", "Jobs with an invoice raised in the current shop week.", "neutral", "all", "period"),
    FocusDefinition("collected_this_week", "Paid this week", "Jobs with an invoice paid in the current shop week.", "neutral", "all", "period"),
)
FOCUS_BY_KEY: dict[str, FocusDefinition] = {f.key: f for f in FOCUS_DEFINITIONS}
FOCUS_KEYS: tuple[str, ...] = tuple(FOCUS_BY_KEY)


def focus_filter(key: str, *, tenant_id: UUID, now: datetime, tz: ZoneInfo):
    """SQLAlchemy clause selecting the ``AutoKeyJob`` rows a focus counts.

    ``now`` must be timezone-aware. Raises ``KeyError`` for an unknown focus.
    """
    if key not in FOCUS_BY_KEY:
        raise KeyError(key)
    now_naive = naive_utc(now)
    active = AutoKeyJob.status.notin_(AUTO_KEY_FINAL_STATUSES)
    if key == "late":
        return and_(
            active,
            AutoKeyJob.status.notin_(FIELD_STATUSES | ON_HOLD_STATUSES),
            AutoKeyJob.scheduled_at.is_not(None),
            AutoKeyJob.scheduled_at < now_naive,
        )
    if key == "today":
        start, end = day_bounds_utc(now.astimezone(tz).date(), tz)
        return and_(active, AutoKeyJob.scheduled_at >= naive_utc(start), AutoKeyJob.scheduled_at < naive_utc(end))
    if key == "in_field":
        return AutoKeyJob.status.in_(FIELD_STATUSES)
    if key == "unscheduled":
        return and_(active, AutoKeyJob.scheduled_at.is_(None))
    if key == "unassigned":
        return and_(active, AutoKeyJob.assigned_user_id.is_(None))
    if key == "on_hold":
        return AutoKeyJob.status.in_(ON_HOLD_STATUSES)
    if key == "needs_quote":
        return AutoKeyJob.status.in_(NEEDS_QUOTE_STATUSES)
    if key == "quote_follow_up":
        return and_(
            AutoKeyJob.status.in_(QUOTE_SENT_STATUSES),
            AutoKeyJob.updated_at < now_naive - timedelta(days=QUOTE_FOLLOW_UP_DAYS),
        )
    if key == "confirmation_follow_up":
        return and_(
            AutoKeyJob.status.in_(AUTO_KEY_AWAITING_CONFIRMATION_STATUSES),
            AutoKeyJob.updated_at < now_naive - timedelta(hours=CONFIRMATION_FOLLOW_UP_HOURS),
        )
    if key == "completed_unpaid":
        return AutoKeyJob.status.in_(AUTO_KEY_COMPLETED_UNPAID_STATUSES)
    if key == "overdue_invoices":
        overdue = (
            select(AutoKeyInvoice.auto_key_job_id)
            .where(AutoKeyInvoice.tenant_id == tenant_id)
            .where(AutoKeyInvoice.status.notin_(("paid", *_EXCLUDED_INVOICE_STATUSES)))
            .where(AutoKeyInvoice.created_at < now_naive - timedelta(days=INVOICE_OVERDUE_DAYS))
        )
        return AutoKeyJob.id.in_(overdue)
    if key == "unpaid_invoices":
        unpaid = (
            select(AutoKeyInvoice.auto_key_job_id)
            .where(AutoKeyInvoice.tenant_id == tenant_id)
            .where(AutoKeyInvoice.status.notin_(("paid", *_EXCLUDED_INVOICE_STATUSES)))
        )
        return AutoKeyJob.id.in_(unpaid)
    week_from, week_to = week_bounds_utc(now, tz)
    if key == "this_week":
        return and_(
            AutoKeyJob.status.notin_(LOST_STATUSES),
            AutoKeyJob.scheduled_at >= naive_utc(week_from),
            AutoKeyJob.scheduled_at < naive_utc(week_to),
        )
    if key == "completed_this_week":
        return and_(
            AutoKeyJob.work_completed_at >= naive_utc(week_from), AutoKeyJob.work_completed_at < naive_utc(week_to)
        )
    if key == "invoiced_this_week":
        raised = (
            select(AutoKeyInvoice.auto_key_job_id)
            .where(AutoKeyInvoice.tenant_id == tenant_id)
            .where(AutoKeyInvoice.status.notin_(_EXCLUDED_INVOICE_STATUSES))
            .where(AutoKeyInvoice.created_at >= naive_utc(week_from), AutoKeyInvoice.created_at < naive_utc(week_to))
        )
        return AutoKeyJob.id.in_(raised)
    if key == "collected_this_week":
        paid = (
            select(AutoKeyInvoice.auto_key_job_id)
            .where(AutoKeyInvoice.tenant_id == tenant_id)
            .where(AutoKeyInvoice.status == "paid")
            .where(AutoKeyInvoice.paid_at >= naive_utc(week_from), AutoKeyInvoice.paid_at < naive_utc(week_to))
        )
        return AutoKeyJob.id.in_(paid)
    raise KeyError(key)  # pragma: no cover - guarded above


# ── Pure comparison arithmetic ───────────────────────────────────────────────
def pct_change(current: float, previous: float) -> float | None:
    """Percentage change, or None when there is nothing to compare against."""
    if previous == 0:
        return None
    return round((current - previous) / abs(previous) * 100, 1)


def delta(current: float, baseline: float | None) -> dict[str, Any] | None:
    if baseline is None:
        return None
    return {"abs": current - baseline, "pct": pct_change(current, baseline)}


def tone_for(direction: Direction, change: float | None) -> Tone:
    """Good/bad/neutral for a movement, honouring which way is 'better'."""
    if change is None or change == 0 or direction == "neutral":
        return "neutral"
    better = change > 0 if direction == "higher_is_better" else change < 0
    return "good" if better else "bad"


@dataclass
class WeeklySeries:
    """Daily values keyed by shop-local date, aggregated into ISO weeks."""

    by_day: dict[date, float] = field(default_factory=lambda: defaultdict(float))

    def add(self, day: date, value: float) -> None:
        self.by_day[day] += value

    def week_total(self, start: date, days: int = 7) -> float:
        return sum(self.by_day.get(start + timedelta(days=i), 0.0) for i in range(days))


def compare_metric(
    *,
    key: str,
    label: str,
    unit: Literal["cents", "count"],
    series: WeeklySeries,
    this_week: date,
    days_elapsed: int,
    direction: Direction,
    target: float | None = None,
    definition: str,
) -> dict[str, Any]:
    """This week vs last week / 4-week average / target, with like-for-like pacing.

    ``days_elapsed`` is how many days of this week have happened (1..7). While
    the week is incomplete the primary comparison is against the same number
    of days of the prior periods, and ``partial`` says so; the full prior-week
    figures are still returned for the record.
    """
    days_elapsed = max(1, min(7, days_elapsed))
    partial = days_elapsed < 7
    current = series.week_total(this_week, days_elapsed)
    last_week = this_week - timedelta(days=7)
    previous_full = series.week_total(last_week)
    previous_to_date = series.week_total(last_week, days_elapsed)
    prior_weeks = [this_week - timedelta(days=7 * n) for n in range(1, 5)]
    four_week_full = sum(series.week_total(w) for w in prior_weeks) / 4
    four_week_to_date = sum(series.week_total(w, days_elapsed) for w in prior_weeks) / 4
    target_to_date = None if target is None else target * days_elapsed / 7

    vs_previous = delta(current, previous_to_date)
    vs_four_week = delta(current, four_week_to_date)
    vs_target = delta(current, target_to_date)
    return {
        "key": key,
        "label": label,
        "unit": unit,
        "definition": definition,
        "direction": direction,
        "partial": partial,
        "days_elapsed": days_elapsed,
        "current": current,
        "previous": previous_full,
        "previous_to_date": previous_to_date,
        "four_week_avg": four_week_full,
        "four_week_avg_to_date": four_week_to_date,
        "target": target,
        "target_to_date": target_to_date,
        "vs_previous": vs_previous,
        "vs_previous_tone": tone_for(direction, vs_previous["abs"] if vs_previous else None),
        "vs_four_week": vs_four_week,
        "vs_four_week_tone": tone_for(direction, vs_four_week["abs"] if vs_four_week else None),
        "vs_target": vs_target,
        "vs_target_tone": tone_for(direction, vs_target["abs"] if vs_target else None),
    }


# ── Row-level helpers ────────────────────────────────────────────────────────
def job_summary(job: AutoKeyJob, customer_name: str | None, tech_name: str | None) -> dict[str, Any]:
    return {
        "id": str(job.id),
        "job_number": job.job_number,
        "title": job.title,
        "customer_name": customer_name,
        "status": job.status,
        "canonical_status": canonical_auto_key_status(job.status),
        "category": mobile_status_category(job.status),
        "priority": job.priority,
        "scheduled_at": as_utc(job.scheduled_at).isoformat() if job.scheduled_at else None,
        "assigned_user_id": str(job.assigned_user_id) if job.assigned_user_id else None,
        "assigned_name": tech_name,
        "job_address": job.job_address,
        "cost_cents": job.cost_cents,
        "created_at": as_utc(job.created_at).isoformat() if job.created_at else None,
    }


def invoice_age_bucket(created_at: datetime | None, now: datetime) -> str:
    age_days = (now - as_utc(created_at)).days if created_at else 0
    if age_days <= INVOICE_OVERDUE_DAYS:
        return "current"
    if age_days <= 30:
        return "d8_30"
    return "d31_plus"


def technician_rows(
    *,
    users: Iterable[User],
    active_jobs: list[AutoKeyJob],
    today_jobs: list[AutoKeyJob],
    late_today_ids: set[UUID],
    week_collected_by_user: dict[UUID, int],
    week_completed_by_user: dict[UUID, int],
    now: datetime,
) -> list[dict[str, Any]]:
    """Capacity and load per technician, with schedule-conflict warnings.

    Capacity is ``TECH_DAY_MINUTES`` minus ``ASSUMED_JOB_MINUTES`` per booking
    today — an explicit assumption until estimated durations exist.
    """
    by_tech_today: dict[UUID, list[AutoKeyJob]] = defaultdict(list)
    for job in today_jobs:
        if job.assigned_user_id:
            by_tech_today[job.assigned_user_id].append(job)
    by_tech_active: dict[UUID, list[AutoKeyJob]] = defaultdict(list)
    for job in active_jobs:
        if job.assigned_user_id:
            by_tech_active[job.assigned_user_id].append(job)

    rows: list[dict[str, Any]] = []
    for user in users:
        if not user.is_active:
            continue
        if user.role != "tech" and not by_tech_active.get(user.id):
            continue
        todays = sorted(by_tech_today.get(user.id, []), key=lambda j: as_utc(j.scheduled_at) or now)
        booked_minutes = len(todays) * ASSUMED_JOB_MINUTES
        conflicts: list[dict[str, Any]] = []
        for earlier, later in zip(todays, todays[1:]):
            gap = (as_utc(later.scheduled_at) - as_utc(earlier.scheduled_at)).total_seconds() / 60
            if gap < CONFLICT_WINDOW_MINUTES:
                conflicts.append(
                    {
                        "job_id": str(earlier.id),
                        "job_number": earlier.job_number,
                        "next_job_id": str(later.id),
                        "next_job_number": later.job_number,
                        "gap_minutes": int(gap),
                    }
                )
        in_field = [j for j in by_tech_active.get(user.id, []) if j.status in FIELD_STATUSES]
        upcoming = [j for j in todays if as_utc(j.scheduled_at) >= now and j.status not in FIELD_STATUSES]
        available = max(0, TECH_DAY_MINUTES - booked_minutes)
        rows.append(
            {
                "user_id": str(user.id),
                "name": user.full_name,
                "role": user.role,
                "scheduled_today": len(todays),
                "booked_minutes_today": booked_minutes,
                "capacity_minutes": TECH_DAY_MINUTES,
                "available_minutes": available,
                "utilisation_pct": round(min(booked_minutes, TECH_DAY_MINUTES) / TECH_DAY_MINUTES * 100, 1),
                "active_jobs": len(by_tech_active.get(user.id, [])),
                "in_field_now": bool(in_field),
                "current_job_number": in_field[0].job_number if in_field else None,
                "late_today": sum(1 for j in todays if j.id in late_today_ids),
                "conflicts": conflicts,
                "next_job": (
                    {
                        "id": str(upcoming[0].id),
                        "job_number": upcoming[0].job_number,
                        "scheduled_at": as_utc(upcoming[0].scheduled_at).isoformat(),
                        "job_address": upcoming[0].job_address,
                    }
                    if upcoming
                    else None
                ),
                "collected_week_cents": week_collected_by_user.get(user.id, 0),
                "completed_week": week_completed_by_user.get(user.id, 0),
            }
        )
    rows.sort(key=lambda r: (-r["scheduled_today"], r["name"].lower()))
    return rows


def build_daily_series(
    *,
    jobs: list[AutoKeyJob],
    invoices: list[AutoKeyInvoice],
    invoice_by_job: dict[UUID, AutoKeyInvoice],
    tz: ZoneInfo,
) -> dict[str, WeeklySeries]:
    """Daily money/count series in shop-local days, from raw rows."""
    def local_day(dt: datetime | None) -> date | None:
        u = as_utc(dt)
        return u.astimezone(tz).date() if u else None

    series = {k: WeeklySeries() for k in ("booked", "completed", "invoiced", "collected", "jobs_created", "jobs_completed")}
    for job in jobs:
        if (created := local_day(job.created_at)) is not None:
            series["jobs_created"].add(created, 1)
        if job.scheduled_at and job.status not in LOST_STATUSES:
            series["booked"].add(local_day(job.scheduled_at), max(0, job.cost_cents or 0))
        if job.work_completed_at:
            done = local_day(job.work_completed_at)
            series["jobs_completed"].add(done, 1)
            inv = invoice_by_job.get(job.id)
            value = inv.total_cents if inv and inv.status not in _EXCLUDED_INVOICE_STATUSES else max(0, job.cost_cents or 0)
            series["completed"].add(done, value)
    for inv in invoices:
        if inv.status in _EXCLUDED_INVOICE_STATUSES:
            continue
        series["invoiced"].add(local_day(inv.created_at), inv.total_cents)
        if inv.status == "paid" and inv.paid_at:
            series["collected"].add(local_day(inv.paid_at), inv.total_cents)
    return series


METRIC_DEFINITIONS: dict[str, tuple[str, Literal["cents", "count"], Direction, str]] = {
    "booked": ("Booked", "cents", "higher_is_better", "Sell value (job price) of jobs scheduled in the period, whatever stage they reached; failed / no-go jobs are excluded."),
    "completed": ("Completed", "cents", "higher_is_better", "Value of jobs whose work was completed in the period (invoice total, else job price)."),
    "invoiced": ("Invoiced", "cents", "higher_is_better", "Invoices raised in the period, excluding void/refunded."),
    "collected": ("Cash collected", "cents", "higher_is_better", "Invoices paid in the period, by paid date."),
    "jobs_created": ("Jobs created", "count", "neutral", "Jobs created in the period (leads and bookings)."),
    "jobs_completed": ("Jobs completed", "count", "higher_is_better", "Jobs whose work was completed in the period."),
}
