"""Unified per-job message threads.

A ticket's thread shows the whole SMS conversation with that customer, not just
rows linked to the job id. Inbound replies are routed to the customer's most
recent open job (which may be a different ticket), and several automated mobile
services SMS are persisted without a job link — so the thread merges:

1. JobMessage / SmsLog rows linked to the job id, and
2. tenant-scoped rows whose phone matches the customer's number.
"""
from datetime import datetime, timezone
from uuid import UUID

from sqlmodel import Session, select

from ..models import JobMessage, JobThreadMessage, SmsLog
from ..phone_utils import phones_match

# Cap on the phone-matched scan; well beyond a single shop's recent SMS volume.
_PHONE_SCAN_LIMIT = 1000


def _as_utc(dt: datetime) -> datetime:
    """Normalise to timezone-aware UTC. In production Postgres, jobmessage.created_at
    is timestamptz (aware) while smslog.created_at is timestamp (naive UTC) — mixing
    them in a sort raises TypeError, which 500'd the whole thread."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def build_job_thread(
    session: Session,
    *,
    tenant_id: UUID,
    customer_phone: str | None,
    repair_job_id: UUID | None = None,
    shoe_repair_job_id: UUID | None = None,
    auto_key_job_id: UUID | None = None,
) -> list[JobThreadMessage]:
    """Return the merged message thread for a job, oldest first."""
    manual: dict[UUID, JobMessage] = {}
    automated: dict[UUID, SmsLog] = {}

    job_filters = []
    if repair_job_id:
        job_filters.append((JobMessage.repair_job_id, SmsLog.repair_job_id, repair_job_id))
    if shoe_repair_job_id:
        job_filters.append((JobMessage.shoe_repair_job_id, SmsLog.shoe_repair_job_id, shoe_repair_job_id))
    if auto_key_job_id:
        job_filters.append((JobMessage.auto_key_job_id, SmsLog.auto_key_job_id, auto_key_job_id))

    for msg_col, log_col, job_id in job_filters:
        for row in session.exec(
            select(JobMessage).where(msg_col == job_id).where(JobMessage.tenant_id == tenant_id)
        ).all():
            manual[row.id] = row
        for row in session.exec(
            select(SmsLog).where(log_col == job_id).where(SmsLog.tenant_id == tenant_id)
        ).all():
            automated[row.id] = row

    if customer_phone and (customer_phone or "").strip():
        candidates = session.exec(
            select(JobMessage)
            .where(JobMessage.tenant_id == tenant_id)
            .order_by(JobMessage.created_at.desc())
            .limit(_PHONE_SCAN_LIMIT)
        ).all()
        for row in candidates:
            if row.id in manual:
                continue
            if phones_match(row.to_phone, customer_phone) or phones_match(row.from_phone, customer_phone):
                manual[row.id] = row

        log_candidates = session.exec(
            select(SmsLog)
            .where(SmsLog.tenant_id == tenant_id)
            .order_by(SmsLog.created_at.desc())
            .limit(_PHONE_SCAN_LIMIT)
        ).all()
        for row in log_candidates:
            if row.id in automated:
                continue
            if phones_match(row.to_phone, customer_phone):
                automated[row.id] = row

    thread: list[JobThreadMessage] = []
    for m in manual.values():
        thread.append(JobThreadMessage(
            id=m.id,
            direction=m.direction,
            body=m.body,
            from_phone=m.from_phone,
            to_phone=m.to_phone,
            created_at=_as_utc(m.created_at),
        ))
    for s in automated.values():
        thread.append(JobThreadMessage(
            id=s.id,
            direction="system",
            body=s.body,
            to_phone=s.to_phone,
            event=s.event,
            status=s.status,
            created_at=_as_utc(s.created_at),
        ))

    thread.sort(key=lambda m: m.created_at)
    return thread
