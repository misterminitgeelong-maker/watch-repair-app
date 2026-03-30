"""Helpers for storing auto-key scheduled_at as UTC (SQLite naive) and emitting correct JSON / SMS copy."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def naive_utc_from_any(dt: datetime | None) -> datetime | None:
    """Persist to DB: aware datetimes → UTC with tz stripped; naive kept as-is (legacy UTC)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def as_utc_for_json(dt: datetime | None) -> datetime | None:
    """API JSON: naive datetimes are treated as UTC and serialized with an offset."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def isoformat_z_utc(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    u = as_utc_for_json(dt)
    assert u is not None
    s = u.isoformat()
    return s.replace("+00:00", "Z")


def local_calendar_day_bounds_utc(tz_name: str, date_from: str | None, date_to: str | None) -> tuple[datetime | None, datetime | None]:
    """
    Interpret YYYY-MM-DD as calendar days in the given zone, return inclusive UTC bounds
    for filtering naive UTC scheduled_at in the database.
    """
    tz = ZoneInfo(tz_name)
    lower: datetime | None = None
    upper: datetime | None = None
    if date_from:
        y, m, d = map(int, date_from.split("-"))
        lower = datetime(y, m, d, 0, 0, 0, tzinfo=tz).astimezone(timezone.utc).replace(tzinfo=None)
    if date_to:
        y, m, d = map(int, date_to.split("-"))
        upper = datetime(y, m, d, 23, 59, 59, 999999, tzinfo=tz).astimezone(timezone.utc).replace(tzinfo=None)
    return lower, upper


def format_in_timezone(dt: datetime | None, tz_name: str, fmt: str = "%a %d %b, %H:%M") -> str:
    """SMS / display: show wall time in shop timezone."""
    if dt is None:
        return ""
    u = as_utc_for_json(dt)
    assert u is not None
    return u.astimezone(ZoneInfo(tz_name)).strftime(fmt)
