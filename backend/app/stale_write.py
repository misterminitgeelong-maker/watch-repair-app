"""Reject offline-queue replays that would overwrite a newer server write."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request


EXPECTED_HEADER = "X-Expected-Updated-At"
QUEUED_HEADER = "X-Queued-At"
_SLACK = timedelta(seconds=2)


def _parse_ts(raw: str | None) -> datetime | None:
    if not raw or not raw.strip():
        return None
    text = raw.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def reject_stale_write(entity_updated_at: datetime | None, request: Request) -> None:
    """409 if the client held (or queued at) a timestamp older than the entity.

    Prefers ``X-Expected-Updated-At`` (the ``updated_at`` the client last saw).
    Falls back to ``X-Queued-At`` so an offline mutation queued at 9am cannot
    overwrite edits that landed at 10am.
    """
    client_ts = _parse_ts(request.headers.get(EXPECTED_HEADER)) or _parse_ts(request.headers.get(QUEUED_HEADER))
    actual = _as_utc(entity_updated_at)
    if client_ts is None or actual is None:
        return
    if actual > client_ts + _SLACK:
        raise HTTPException(
            status_code=409,
            detail="stale_write",
        )
