"""
SMS notification service using Twilio.

If Twilio credentials are not configured (empty strings) the module
operates in dry-run mode: messages are logged to stdout but not sent.
This keeps the app fully functional in development without a Twilio account.
"""
import logging
from uuid import UUID

from sqlmodel import Session

from .config import settings
from .models import SmsLog

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal send helper
# ---------------------------------------------------------------------------

def _send_sms(to: str, body: str) -> str | None:
    """Send an SMS and return the provider SID, or None on failure/dry-run."""
    if not (settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_from_number):
        logger.info("[SMS DRY-RUN] To=%s | %s", to, body)
        return None

    try:
        from twilio.rest import Client  # type: ignore[import]
        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        message = client.messages.create(
            body=body,
            from_=settings.twilio_from_number,
            to=to,
        )
        logger.info("[SMS SENT] sid=%s to=%s", message.sid, to)
        return message.sid
    except Exception as exc:  # noqa: BLE001
        logger.error("[SMS ERROR] to=%s error=%s", to, exc)
        return None


def _persist(
    session: Session,
    *,
    tenant_id: UUID,
    repair_job_id: UUID | None,
    to_phone: str,
    body: str,
    event: str,
    provider_sid: str | None,
    status: str,
) -> None:
    log = SmsLog(
        tenant_id=tenant_id,
        repair_job_id=repair_job_id,
        to_phone=to_phone,
        body=body,
        event=event,
        provider_sid=provider_sid,
        status=status,
    )
    session.add(log)
    # Caller is responsible for committing the session.


# ---------------------------------------------------------------------------
# Public notification functions — each maps to a business event
# ---------------------------------------------------------------------------

def notify_quote_sent(
    session: Session,
    *,
    tenant_id: UUID,
    repair_job_id: UUID,
    customer_name: str,
    to_phone: str,
    total_cents: int,
    approval_token: str,
    shop_name: str = "your watch repair shop",
) -> None:
    """Send the quote approval SMS to the customer."""
    total = total_cents / 100
    currency_symbol = "$"
    approval_url = f"{settings.public_base_url}/approve/{approval_token}"
    body = (
        f"Hi {customer_name}, your watch repair quote is {currency_symbol}{total:.2f}. "
        f"Reply YES to approve or NO to decline, or tap the link to view details: {approval_url}"
    )
    sid = _send_sms(to_phone, body)
    _persist(
        session,
        tenant_id=tenant_id,
        repair_job_id=repair_job_id,
        to_phone=to_phone,
        body=body,
        event="quote_sent",
        provider_sid=sid,
        status="sent" if sid else "dry_run",
    )


def notify_job_status_changed(
    session: Session,
    *,
    tenant_id: UUID,
    repair_job_id: UUID,
    customer_name: str,
    to_phone: str,
    job_number: str,
    status_token: str,
    new_status: str,
    shop_name: str = "your watch repair shop",
) -> None:
    """Send a status-update SMS to the customer on milestone transitions."""
    message_map: dict[str, str] = {
        "awaiting_go_ahead": (
            f"Hi {customer_name}, we've received your watch (job #{job_number}). "
            f"We'll be in touch once we've assessed it."
        ),
        "go_ahead": (
            f"Hi {customer_name}, your repair for job #{job_number} has been approved. "
            f"We'll get started and keep you updated."
        ),
        "working_on": (
            f"Hi {customer_name}, great news — we've started work on your watch (job #{job_number}). "
            f"We'll let you know when it's done."
        ),
        "completed": (
            f"Hi {customer_name}, your watch (job #{job_number}) is ready for collection! "
            f"Please contact us to arrange pick-up."
        ),
        "awaiting_collection": (
            f"Hi {customer_name}, your watch (job #{job_number}) is ready and waiting for collection! "
            f"Please contact us to arrange pick-up."
        ),
        "collected": (
            f"Thank you {customer_name}! Your watch (job #{job_number}) has been collected. "
            f"We hope you enjoy it — don't hesitate to reach out if you need anything."
        ),
    }

    body = message_map.get(new_status)
    if not body:
        # No notification for diagnosis, qc, cancelled, etc.
        return

    body = f"{body} Track live status: {settings.public_base_url}/status/{status_token}"

    sid = _send_sms(to_phone, body)
    _persist(
        session,
        tenant_id=tenant_id,
        repair_job_id=repair_job_id,
        to_phone=to_phone,
        body=body,
        event=f"status_{new_status}",
        provider_sid=sid,
        status="sent" if sid else "dry_run",
    )


def notify_auto_key_day_before_reminder(
    session: Session,
    *,
    tenant_id: UUID,
    to_phone: str,
    job_summaries: list[str],
) -> None:
    """Remind tech of tomorrow's scheduled Auto Key jobs."""
    if not job_summaries:
        return
    lines = "Tomorrow's jobs: " + "; ".join(job_summaries[:5])
    if len(job_summaries) > 5:
        lines += f" (+{len(job_summaries) - 5} more)"
    sid = _send_sms(to_phone, lines)
    _persist(
        session,
        tenant_id=tenant_id,
        repair_job_id=None,
        to_phone=to_phone,
        body=lines,
        event="auto_key_day_before_reminder",
        provider_sid=sid,
        status="sent" if sid else "dry_run",
    )


def notify_auto_key_customer_scheduled(
    session: Session,
    *,
    tenant_id: UUID,
    to_phone: str,
    customer_name: str,
    job_number: str,
    scheduled_at: str | None,
    job_address: str | None,
) -> None:
    """Notify customer when their mobile Auto Key job is scheduled."""
    if not scheduled_at:
        return
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
        when = f"{dt.strftime('%a %d %b')} around {dt.strftime('%H:%M')}"
    except (ValueError, TypeError):
        when = scheduled_at[:16] if scheduled_at else ""
    body = f"Hi {customer_name}, your auto key technician is scheduled for {when}."
    if job_address:
        body += f" Address: {job_address[:50]}{'…' if len(job_address) > 50 else ''}"
    sid = _send_sms(to_phone, body)
    _persist(
        session,
        tenant_id=tenant_id,
        repair_job_id=None,
        to_phone=to_phone,
        body=body,
        event="auto_key_customer_scheduled",
        provider_sid=sid,
        status="sent" if sid else "dry_run",
    )


def notify_auto_key_customer_day_before(
    session: Session,
    *,
    tenant_id: UUID,
    to_phone: str,
    customer_name: str,
    job_number: str,
    scheduled_at: str | None,
    job_address: str | None,
) -> None:
    """Notify customer of tomorrow's scheduled mobile job."""
    if not scheduled_at:
        return
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
        when = f"{dt.strftime('%a %d %b')} around {dt.strftime('%H:%M')}"
    except (ValueError, TypeError):
        when = scheduled_at[:16] if scheduled_at else "tomorrow"
    body = f"Hi {customer_name}, your technician is scheduled for {when}."
    if job_address:
        body += f" Address: {job_address[:50]}{'…' if len(job_address) > 50 else ''}"
    body += " We'll SMS you with your arrival window on the day."
    sid = _send_sms(to_phone, body)
    _persist(
        session,
        tenant_id=tenant_id,
        repair_job_id=None,
        to_phone=to_phone,
        body=body,
        event="auto_key_customer_day_before",
        provider_sid=sid,
        status="sent" if sid else "dry_run",
    )


def notify_auto_key_arrival_window(
    session: Session,
    *,
    tenant_id: UUID,
    to_phone: str,
    customer_name: str,
    job_number: str,
    time_window: str,
) -> None:
    """Notify customer: tech on the way, arriving in time window (e.g. 9–11am)."""
    body = f"Hi {customer_name}, your technician is on the way and will arrive between {time_window}."
    sid = _send_sms(to_phone, body)
    _persist(
        session,
        tenant_id=tenant_id,
        repair_job_id=None,
        to_phone=to_phone,
        body=body,
        event="auto_key_arrival_window",
        provider_sid=sid,
        status="sent" if sid else "dry_run",
    )


def notify_auto_key_schedule_changed(
    session: Session,
    *,
    tenant_id: UUID,
    to_phone: str,
    job_number: str,
    scheduled_at: str | None,
    job_address: str | None,
    job_type: str | None,
) -> None:
    """Notify assigned tech when an auto key job's schedule changes."""
    parts = [f"Auto key job #{job_number} schedule updated:"]
    if scheduled_at:
        from datetime import datetime
        try:
            dt = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
            parts.append(f" {dt.strftime('%a %d %b')} at {dt.strftime('%H:%M')}")
        except (ValueError, TypeError):
            parts.append(f" {scheduled_at[:16]}")
    if job_type:
        parts.append(f" Type: {job_type}")
    if job_address:
        parts.append(f" Address: {job_address[:60]}{'…' if len(job_address) > 60 else ''}")
    body = "".join(parts).strip()
    if len(body) <= 10:
        return
    sid = _send_sms(to_phone, body)
    _persist(
        session,
        tenant_id=tenant_id,
        repair_job_id=None,
        to_phone=to_phone,
        body=body,
        event="auto_key_schedule_changed",
        provider_sid=sid,
        status="sent" if sid else "dry_run",
    )
