"""Day-before text for mobile services (auto key) jobs.

The "appointment confirmed" text promises customers a message the day before.
This sweep sends it, in each shop's own timezone, once per job.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlmodel import Session, select

from .. import sms
from ..auto_key_status import AUTO_KEY_FINAL_STATUSES
from ..models import AutoKeyJob, Customer, SmsLog

logger = logging.getLogger(__name__)

#: Local hour (shop time) from which the sweep sends tomorrow's reminders.
SEND_FROM_LOCAL_HOUR = 16


def _already_sent(session: Session, tenant_id: UUID, job_id: UUID) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=30)
    rows = session.exec(
        select(SmsLog)
        .where(SmsLog.tenant_id == tenant_id)
        .where(SmsLog.auto_key_job_id == job_id)
        .where(SmsLog.event == "auto_key_customer_day_before")
        .where(SmsLog.created_at >= cutoff)
    ).all()
    return any(r.status in ("sent", "dry_run", "suppressed") for r in rows)


def send_day_before_reminders(
    session: Session, tenant_id: UUID | None = None, *, ignore_hour: bool = False
) -> dict[str, int]:
    """Text every customer whose mobile job is tomorrow (shop time). Safe to run often:
    each job is only texted once. ``ignore_hour`` is for the manual button."""
    now = datetime.now(timezone.utc)
    window_start = now.replace(tzinfo=None)
    window_end = (now + timedelta(days=2)).replace(tzinfo=None)
    query = (
        select(AutoKeyJob)
        .where(AutoKeyJob.scheduled_at.is_not(None))
        .where(AutoKeyJob.scheduled_at >= window_start)
        .where(AutoKeyJob.scheduled_at < window_end)
        .where(AutoKeyJob.status.notin_(AUTO_KEY_FINAL_STATUSES))
    )
    if tenant_id:
        query = query.where(AutoKeyJob.tenant_id == tenant_id)
    summary = {"sent": 0, "skipped": 0}
    zones: dict[UUID, ZoneInfo] = {}
    for job in session.exec(query).all():
        zone = zones.get(job.tenant_id)
        if zone is None:
            zone = zones[job.tenant_id] = ZoneInfo(sms._shop_tz(session, job.tenant_id))  # noqa: SLF001
        local_now = now.astimezone(zone)
        local_job = job.scheduled_at.replace(tzinfo=timezone.utc).astimezone(zone)
        if local_job.date() != local_now.date() + timedelta(days=1):
            continue
        if not ignore_hour and local_now.hour < SEND_FROM_LOCAL_HOUR:
            continue
        customer = session.get(Customer, job.customer_id)
        if not customer or not (customer.phone or "").strip() or _already_sent(session, job.tenant_id, job.id):
            summary["skipped"] += 1
            continue
        first_name = ((customer.full_name or "").strip().split() or ["there"])[0]
        sms.notify_auto_key_customer_day_before(
            session,
            tenant_id=job.tenant_id,
            to_phone=customer.phone.strip(),
            customer_name=first_name,
            job_number=job.job_number,
            scheduled_at=job.scheduled_at.isoformat(),
            job_address=job.job_address,
            auto_key_job_id=job.id,
        )
        summary["sent"] += 1
    session.commit()
    return summary
