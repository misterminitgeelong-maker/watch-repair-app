"""Out-of-band redelivery of failed SMS and email under an attempt cap.

Follows quote_reminders.py: caller-agnostic, idempotent, commits via the
transport's own log updates. The web-process thread in main.py is a thin
wrapper; batch 5 can move this loop with the other sweeps.
"""
from __future__ import annotations

import json
import logging

from sqlmodel import Session, select

from .. import sms
from ..email_client import send_email_from_payload
from ..models import EmailLog, SmsLog
from ..notification_retry import redelivery_max_attempts

logger = logging.getLogger(__name__)


def redeliver_failed_notifications(session: Session) -> dict[str, int]:
    """Resend failed notification rows whose attempt_count is still under the cap.

    4xx failures pin attempt_count to the cap at send time, so they are not
    picked up here. Dry-run rows are never retried.
    """
    cap = redelivery_max_attempts()
    summary = {"email_sent": 0, "sms_sent": 0, "skipped": 0}

    emails = session.exec(select(EmailLog).where(EmailLog.status == "failed")).all()
    for row in emails:
        if row.attempt_count >= cap or not (row.payload_json or "").strip():
            summary["skipped"] += 1
            continue
        try:
            payload = json.loads(row.payload_json)
        except json.JSONDecodeError:
            summary["skipped"] += 1
            continue
        if not isinstance(payload, dict):
            summary["skipped"] += 1
            continue
        ok, _err = send_email_from_payload(
            to_email=row.to_email,
            event=row.event,
            payload=payload,
            session=session,
            tenant_id=row.tenant_id,
            existing_log_id=row.id,
        )
        if ok:
            summary["email_sent"] += 1
        else:
            summary["skipped"] += 1

    texts = session.exec(select(SmsLog).where(SmsLog.status == "failed")).all()
    for row in texts:
        if row.attempt_count >= cap or not (row.body or "").strip() or not (row.to_phone or "").strip():
            summary["skipped"] += 1
            continue
        sid, status = sms._logged_send(  # noqa: SLF001
            session,
            tenant_id=row.tenant_id,
            repair_job_id=row.repair_job_id,
            shoe_repair_job_id=row.shoe_repair_job_id,
            auto_key_job_id=row.auto_key_job_id,
            to_phone=row.to_phone,
            body=row.body,
            event=row.event,
            existing_log_id=row.id,
        )
        if status == "sent":
            summary["sms_sent"] += 1
        else:
            summary["skipped"] += 1

    session.commit()
    session.expire_all()
    return summary
