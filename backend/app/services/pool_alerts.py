"""Dispatch Pool alerts: notify nearby operators once a job has sat unclaimed a while.

Deliberately NOT a push per job — that would spam an operator with a text every time
something lands nearby. Instead: a job unclaimed past the grace period is folded into
one digest alert (one SMS + one email) per nearby operator per sweep, and the job is
never re-alerted after that — operators can still find it any time by opening the pool.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlmodel import Session, col, select

from .. import email_client
from .. import sms as sms_service
from ..config import settings
from ..dependencies import normalize_plan_code
from ..dispatch_utils import operator_ring_for_job
from ..models import IntakeJob, Tenant
from ..routes.shop_mobile_bookings import BOOKABLE_OPERATOR_PLAN_CODES

logger = logging.getLogger(__name__)

#: Only alert operators within this many rings of the job; farther operators can still
#: browse and claim it from the pool, they just don't get pinged for it.
MAX_ALERT_RING = 2


def _eligible_operators(session: Session) -> list[Tenant]:
    rows = session.exec(
        select(Tenant)
        .where(col(Tenant.base_lat).is_not(None))
        .where(col(Tenant.base_lng).is_not(None))
        .where(Tenant.is_active == True)  # noqa: E712
    ).all()
    return [t for t in rows if normalize_plan_code(t.plan_code) in BOOKABLE_OPERATOR_PLAN_CODES]


def process_stale_pool_jobs(session: Session) -> dict[str, int]:
    """Fold newly-stale unclaimed pool jobs into one digest alert per nearby operator."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.pool_alert_after_minutes)
    stale_jobs = session.exec(
        select(IntakeJob)
        .where(IntakeJob.status == "unclaimed")
        .where(col(IntakeJob.alerted_at).is_(None))
        .where(col(IntakeJob.created_at) <= cutoff)
    ).all()
    summary = {"stale_jobs": len(stale_jobs), "operators_alerted": 0}
    if not stale_jobs:
        return summary

    operators = _eligible_operators(session)
    op_by_id = {op.id: op for op in operators}
    jobs_by_operator: dict[UUID, list[IntakeJob]] = {}
    for job in stale_jobs:
        for op in operators:
            ring = operator_ring_for_job(op.base_lat, op.base_lng, job.job_lat, job.job_lng, op.ring_radius_km or 10)
            if ring is not None and ring <= MAX_ALERT_RING:
                jobs_by_operator.setdefault(op.id, []).append(job)

    pool_url = f"{settings.public_base_url.rstrip('/')}/auto-key/pool"
    for tenant_id, jobs in jobs_by_operator.items():
        tenant = op_by_id[tenant_id]
        notified = False

        phone = sms_service.operator_dispatch_phone(tenant)
        if phone:
            sms_service.notify_pool_jobs_waiting(
                session, tenant_id=tenant_id, to_phone=phone, job_count=len(jobs), pool_url=pool_url,
            )
            notified = True

        email = sms_service.operator_dispatch_email(session, tenant)
        if email:
            ok, err = email_client.send_pool_jobs_waiting_email(
                to_email=email, job_count=len(jobs), pool_url=pool_url, session=session, tenant_id=tenant_id,
            )
            if not ok and err:
                logger.info("pool_alerts.email_failed tenant=%s err=%s", tenant_id, err)
            notified = True

        if notified:
            summary["operators_alerted"] += 1

    now = datetime.now(timezone.utc)
    for job in stale_jobs:
        job.alerted_at = now
        session.add(job)
    session.commit()
    return summary
