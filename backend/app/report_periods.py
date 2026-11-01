"""Civil calendar period bounds for reporting exports (Monday-first weeks)."""
from datetime import date, datetime, timedelta, timezone, tzinfo
from typing import Literal

PeriodType = Literal["day", "week", "month", "quarter"]
VALID_PERIODS: frozenset[str] = frozenset({"day", "week", "month", "quarter"})


def parse_reference_date(value: str | None, tz: tzinfo = timezone.utc) -> date:
    """The civil date to report on; with no value, today in ``tz`` (the shop's zone)."""
    if not value:
        return datetime.now(timezone.utc).astimezone(tz).date()
    return datetime.strptime(value, "%Y-%m-%d").date()


def local_day_start_utc(day: date, tz: tzinfo = timezone.utc) -> datetime:
    """The UTC instant a civil ``day`` begins in ``tz``."""
    return datetime(day.year, day.month, day.day, tzinfo=tz).astimezone(timezone.utc)


def local_day_end_utc(day: date, tz: tzinfo = timezone.utc) -> datetime:
    """The last UTC microsecond of a civil ``day`` in ``tz`` (inclusive upper bound)."""
    return local_day_start_utc(day + timedelta(days=1), tz) - timedelta(microseconds=1)


def resolve_period_bounds(
    period: PeriodType, reference: date, tz: tzinfo = timezone.utc
) -> tuple[datetime, datetime, str, str]:
    """UTC [start, end] inclusive for the period containing ``reference`` (civil Y-M-D labels).

    The civil days are read in ``tz`` (the shop's zone), so a Melbourne "today" runs from
    Melbourne midnight, not 11am.
    """
    if period == "day":
        start_ymd = end_ymd = reference.isoformat()
    elif period == "week":
        monday = reference - timedelta(days=reference.weekday())
        sunday = monday + timedelta(days=6)
        start_ymd = monday.isoformat()
        end_ymd = sunday.isoformat()
    elif period == "month":
        start_ymd = reference.replace(day=1).isoformat()
        if reference.month == 12:
            next_month = reference.replace(year=reference.year + 1, month=1, day=1)
        else:
            next_month = reference.replace(month=reference.month + 1, day=1)
        end_ymd = (next_month - timedelta(days=1)).isoformat()
    elif period == "quarter":
        q_index = (reference.month - 1) // 3
        start_month = q_index * 3 + 1
        end_month = start_month + 2
        start_ymd = date(reference.year, start_month, 1).isoformat()
        if end_month == 12:
            next_month = date(reference.year + 1, 1, 1)
        else:
            next_month = date(reference.year, end_month + 1, 1)
        end_ymd = (next_month - timedelta(days=1)).isoformat()
    else:
        raise ValueError(f"Unsupported period: {period}")

    start_dt = local_day_start_utc(date.fromisoformat(start_ymd), tz)
    end_dt = local_day_end_utc(date.fromisoformat(end_ymd), tz)
    return start_dt, end_dt, start_ymd, end_ymd
