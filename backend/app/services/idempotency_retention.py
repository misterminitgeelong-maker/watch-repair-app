"""Retention for the two tables batch 3 added, both of which grow without bound.

``mutationidempotencykey`` stores up to 64 KB of response body for every mutation
carrying an Idempotency-Key. ``emaillog.payload_json`` stores the rendered body of
every email sent — for quote and invoice mail that is customer names, job detail
and amounts. Neither had any cleanup, so both grew forever and the second changed
what customer data the system retains without that being a stated decision.

Both are kept only for a purpose with a natural shelf life:

* an idempotency key matters until the client has stopped replaying that mutation;
  the offline queue gives up after 5 attempts, so days, not months.
* an email payload matters until redelivery has succeeded or exhausted its
  attempts; after that it is inert customer data sitting in a log table.

This trims both to a configured window. It does not delete the log rows — the
audit trail of *what was sent to whom and when* is the point of EmailLog — only
the stored body once it can no longer be used to resend.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from ..config import settings
from ..idempotency import IN_PROGRESS_ABANDONED_AFTER, STATE_IN_PROGRESS
from ..models import EmailLog, MutationIdempotencyKey
from ..notification_retry import redelivery_max_attempts

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def purge_expired_idempotency_keys(session: Session) -> int:
    """Drop completed keys past the retention window, and abandoned reservations.

    A reservation whose request never completed (process killed mid-request) would
    otherwise answer every replay of that key with 409 forever.
    """
    now = _utcnow()
    completed_cutoff = now - timedelta(days=settings.idempotency_key_retention_days)
    abandoned_cutoff = now - IN_PROGRESS_ABANDONED_AFTER

    removed = 0
    for row in session.exec(select(MutationIdempotencyKey)).all():
        created = _as_utc(row.created_at)
        if created is None:
            continue
        if row.state == STATE_IN_PROGRESS:
            if created < abandoned_cutoff:
                session.delete(row)
                removed += 1
            continue
        if created < completed_cutoff:
            session.delete(row)
            removed += 1
    if removed:
        session.commit()
    return removed


def purge_stale_email_payloads(session: Session) -> int:
    """Clear stored email bodies that can no longer be redelivered.

    Keeps the payload while the row is still a redelivery candidate: failed and
    under the attempt cap. Everything else past the window has its body cleared
    and keeps its audit fields.
    """
    cutoff = _utcnow() - timedelta(days=settings.email_payload_retention_days)
    cap = redelivery_max_attempts()

    cleared = 0
    rows = session.exec(
        select(EmailLog).where(EmailLog.payload_json.is_not(None))  # type: ignore[union-attr]
    ).all()
    for row in rows:
        created = _as_utc(row.created_at)
        if created is None or created >= cutoff:
            continue
        still_redeliverable = row.status == "failed" and row.attempt_count < cap
        if still_redeliverable:
            continue
        row.payload_json = None
        session.add(row)
        cleared += 1
    if cleared:
        session.commit()
    return cleared


def run_retention(session: Session) -> dict[str, int]:
    summary = {
        "idempotency_keys_removed": purge_expired_idempotency_keys(session),
        "email_payloads_cleared": purge_stale_email_payloads(session),
    }
    if summary["idempotency_keys_removed"] or summary["email_payloads_cleared"]:
        logger.info("Retention sweep: %s", summary)
    return summary
