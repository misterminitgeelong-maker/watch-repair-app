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
    new_status: str,
    shop_name: str = "your watch repair shop",
) -> None:
    """Send a status-update SMS to the customer on milestone transitions."""
    message_map: dict[str, str] = {
        "intake": (
            f"Hi {customer_name}, we've received your watch (job #{job_number}). "
            f"We'll be in touch once we've assessed it."
        ),
        "awaiting_approval": (
            f"Hi {customer_name}, your repair quote for job #{job_number} is ready. "
            f"We'll send you a separate link shortly."
        ),
        "in_repair": (
            f"Hi {customer_name}, great news — we've started work on your watch (job #{job_number}). "
            f"We'll let you know when it's done."
        ),
        "ready": (
            f"Hi {customer_name}, your watch (job #{job_number}) is ready for collection! "
            f"Please contact us to arrange pick-up."
        ),
        "delivered": (
            f"Thank you {customer_name}! Your watch (job #{job_number}) has been collected. "
            f"We hope you enjoy it — don't hesitate to reach out if you need anything."
        ),
    }

    body = message_map.get(new_status)
    if not body:
        # No notification for diagnosis, qc, cancelled, etc.
        return

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
