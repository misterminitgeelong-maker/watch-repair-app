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
from .datetime_utils import format_in_timezone
from .models import SmsLog, Tenant

logger = logging.getLogger(__name__)


def mobile_services_customer_sms_enabled(session: Session, tenant_id: UUID) -> bool:
    """When False, skip customer-facing SMS for mobile services (auto key); tech SMS may still send."""
    tenant = session.get(Tenant, tenant_id)
    if not tenant:
        return True
    return bool(getattr(tenant, "mobile_services_customer_sms_enabled", True))


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
    shoe_repair_job_id: UUID | None = None,
    auto_key_job_id: UUID | None = None,
) -> None:
    log = SmsLog(
        tenant_id=tenant_id,
        repair_job_id=repair_job_id,
        shoe_repair_job_id=shoe_repair_job_id,
        auto_key_job_id=auto_key_job_id,
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

def notify_job_live(
    session: Session,
    *,
    tenant_id: UUID,
    repair_job_id: UUID,
    customer_name: str,
    to_phone: str,
    status_token: str,
    job_number: str,
) -> None:
    """Send 'your job is live' SMS with link to track status."""
    status_url = f"{settings.public_base_url}/status/{status_token}"
    body = (
        f"Hi {customer_name}, your watch repair job #{job_number} is now live! "
        f"Track it here: {status_url}"
    )
    sid = _send_sms(to_phone, body)
    _persist(
        session,
        tenant_id=tenant_id,
        repair_job_id=repair_job_id,
        to_phone=to_phone,
        body=body,
        event="job_live",
        provider_sid=sid,
        status="sent" if sid else "dry_run",
    )


def notify_work_started(
    session: Session,
    *,
    tenant_id: UUID,
    repair_job_id: UUID,
    customer_name: str,
    to_phone: str,
    job_number: str,
) -> None:
    """Notify customer that work has started on their watch."""
    body = (
        f"Hi {customer_name}, we have started work on your watch (job #{job_number}). "
        f"You will hear from us in the coming days when your watch is ready for collection."
    )
    sid = _send_sms(to_phone, body)
    _persist(
        session,
        tenant_id=tenant_id,
        repair_job_id=repair_job_id,
        to_phone=to_phone,
        body=body,
        event="work_started",
        provider_sid=sid,
        status="sent" if sid else "dry_run",
    )


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
    if not mobile_services_customer_sms_enabled(session, tenant_id):
        return
    if not scheduled_at:
        return
    try:
        from datetime import datetime

        dt = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
        when = format_in_timezone(dt, settings.schedule_calendar_timezone, "%a %d %b around %H:%M")
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
    if not mobile_services_customer_sms_enabled(session, tenant_id):
        return
    if not scheduled_at:
        return
    try:
        from datetime import datetime

        dt = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
        when = format_in_timezone(dt, settings.schedule_calendar_timezone, "%a %d %b around %H:%M")
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


def notify_auto_key_en_route(
    session: Session,
    *,
    tenant_id: UUID,
    to_phone: str,
    customer_name: str,
    shop_name: str,
    job_number: str,
    job_address: str | None = None,
    scheduled_at=None,
) -> None:
    """SMS when job status moves to en_route — technician is driving to the customer."""
    if not mobile_services_customer_sms_enabled(session, tenant_id):
        return
    from datetime import datetime

    body = f"Hi {customer_name}, {shop_name} — your technician is on the way for mobile job #{job_number}."
    if scheduled_at:
        try:
            dt = (
                scheduled_at
                if isinstance(scheduled_at, datetime)
                else datetime.fromisoformat(str(scheduled_at).replace("Z", "+00:00"))
            )
            body += f" Planned time: {format_in_timezone(dt, settings.schedule_calendar_timezone)}."
        except (ValueError, TypeError):
            pass
    if job_address and job_address.strip():
        a = job_address.strip()
        body += f" Location: {a[:70]}{'…' if len(a) > 70 else ''}."
    if len(body) > 1500:
        body = body[:1490] + "…"
    sid = _send_sms(to_phone, body)
    _persist(
        session,
        tenant_id=tenant_id,
        repair_job_id=None,
        to_phone=to_phone,
        body=body,
        event="auto_key_en_route",
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
    if not mobile_services_customer_sms_enabled(session, tenant_id):
        return
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


def notify_auto_key_invoice_ready(
    session: Session,
    *,
    tenant_id: UUID,
    to_phone: str,
    customer_name: str,
    shop_name: str,
    job_number: str,
    invoice_number: str,
    total_cents: int,
    currency: str,
    view_url: str,
) -> None:
    """SMS after job completed with link to customer invoice page."""
    if not mobile_services_customer_sms_enabled(session, tenant_id):
        return
    sym = "$" if currency.upper() in ("AUD", "USD", "NZD") else ""
    total = total_cents / 100
    body = (
        f"Hi {customer_name}, {shop_name} — job #{job_number} is complete. "
        f"Invoice {invoice_number}: {sym}{total:.2f} {currency}. Details: {view_url}"
    )
    if len(body) > 1500:
        body = body[:1490] + "…"
    sid = _send_sms(to_phone, body)
    _persist(
        session,
        tenant_id=tenant_id,
        repair_job_id=None,
        to_phone=to_phone,
        body=body,
        event="auto_key_invoice_ready",
        provider_sid=sid,
        status="sent" if sid else "dry_run",
    )


def notify_auto_key_quote_sent(
    session: Session,
    *,
    tenant_id: UUID,
    auto_key_job_id: UUID,
    to_phone: str,
    customer_name: str,
    shop_name: str,
    job_number: str,
    total_cents: int,
    currency: str,
) -> None:
    """SMS when a quote is sent — lets the customer know the price and to reply to confirm."""
    if not mobile_services_customer_sms_enabled(session, tenant_id):
        return
    sym = "$" if currency.upper() in ("AUD", "USD", "NZD") else ""
    total = total_cents / 100
    body = (
        f"Hi {customer_name}, {shop_name} — your quote for mobile job #{job_number} "
        f"is {sym}{total:.2f} {currency}. Reply YES to confirm your booking or call us with any questions."
    )
    if len(body) > 1500:
        body = body[:1490] + "…"
    sid = _send_sms(to_phone, body)
    _persist(
        session,
        tenant_id=tenant_id,
        repair_job_id=None,
        auto_key_job_id=auto_key_job_id,
        to_phone=to_phone,
        body=body,
        event="auto_key_quote_sent",
        provider_sid=sid,
        status="sent" if sid else "dry_run",
    )


def notify_auto_key_customer_intake(
    session: Session,
    *,
    tenant_id: UUID,
    to_phone: str,
    customer_name: str,
    shop_name: str,
    job_number: str,
    intake_url: str,
) -> None:
    """SMS after quick-add: link for customer to complete vehicle / job details."""
    if not mobile_services_customer_sms_enabled(session, tenant_id):
        return
    first = (customer_name or "there").strip().split()[0] if (customer_name or "").strip() else "there"
    body = (
        f"Hi {first}, {shop_name} here — job #{job_number}. "
        f"Please complete your details: {intake_url}"
    )
    if len(body) > 1500:
        body = body[:1490] + "…"
    sid = _send_sms(to_phone, body)
    _persist(
        session,
        tenant_id=tenant_id,
        repair_job_id=None,
        to_phone=to_phone,
        body=body,
        event="auto_key_customer_intake",
        provider_sid=sid,
        status="sent" if sid else "dry_run",
    )


def notify_auto_key_booking_request(
    session: Session,
    *,
    tenant_id: UUID,
    to_phone: str,
    customer_name: str,
    job_number: str,
    title: str,
    vehicle_make: str | None,
    vehicle_model: str | None,
    scheduled_at,
    quote_total_cents: int,
    currency: str,
    shop_name: str,
    confirm_url: str,
) -> None:
    """SMS after job creation: summary, quote total, booking time, link to confirm."""
    if not mobile_services_customer_sms_enabled(session, tenant_id):
        return
    from datetime import datetime

    veh = " ".join(x for x in (vehicle_make or "", vehicle_model or "") if x).strip()
    veh_bit = f" ({veh})" if veh else ""
    try:
        dt = scheduled_at if isinstance(scheduled_at, datetime) else datetime.fromisoformat(str(scheduled_at).replace("Z", "+00:00"))
        when = format_in_timezone(dt, settings.schedule_calendar_timezone, "%a %d %b %H:%M")
    except (ValueError, TypeError):
        when = str(scheduled_at)[:16] if scheduled_at else ""
    sym = "$" if currency.upper() in ("AUD", "USD", "NZD") else ""
    total = quote_total_cents / 100
    body = (
        f"Hi {customer_name}, {shop_name} — job #{job_number}{veh_bit}: {title.strip()}. "
        f"Quoted total {sym}{total:.2f} {currency}. Booked time: {when}. "
        f"Please confirm: {confirm_url}"
    )
    if len(body) > 1500:
        body = body[:1490] + "…"
    sid = _send_sms(to_phone, body)
    _persist(
        session,
        tenant_id=tenant_id,
        repair_job_id=None,
        to_phone=to_phone,
        body=body,
        event="auto_key_booking_request",
        provider_sid=sid,
        status="sent" if sid else "dry_run",
    )


# ---------------------------------------------------------------------------
# Shoe repair notification functions
# ---------------------------------------------------------------------------

def notify_shoe_job_live(
    session: Session,
    *,
    tenant_id: UUID,
    shoe_repair_job_id: UUID,
    customer_name: str,
    to_phone: str,
    status_token: str,
    job_number: str,
) -> None:
    """Send 'your shoe job is live' SMS with link to track status."""
    status_url = f"{settings.public_base_url}/shoe-status/{status_token}"
    body = (
        f"Hi {customer_name}, your shoe repair job #{job_number} is now live! "
        f"Track it here: {status_url}"
    )
    sid = _send_sms(to_phone, body)
    _persist(
        session,
        tenant_id=tenant_id,
        repair_job_id=None,
        shoe_repair_job_id=shoe_repair_job_id,
        to_phone=to_phone,
        body=body,
        event="job_live",
        provider_sid=sid,
        status="sent" if sid else "dry_run",
    )


def notify_shoe_quote_sent(
    session: Session,
    *,
    tenant_id: UUID,
    shoe_repair_job_id: UUID,
    customer_name: str,
    to_phone: str,
    total_cents: int,
    approval_token: str,
    shop_name: str = "your shoe repair shop",
) -> None:
    """Send the shoe quote approval SMS to the customer."""
    total = total_cents / 100
    currency_symbol = "$"
    approval_url = f"{settings.public_base_url}/shoe-approve/{approval_token}"
    body = (
        f"Hi {customer_name}, your shoe repair quote from {shop_name} is {currency_symbol}{total:.2f}. "
        f"Tap to approve or decline: {approval_url}"
    )
    sid = _send_sms(to_phone, body)
    _persist(
        session,
        tenant_id=tenant_id,
        repair_job_id=None,
        shoe_repair_job_id=shoe_repair_job_id,
        to_phone=to_phone,
        body=body,
        event="quote_sent",
        provider_sid=sid,
        status="sent" if sid else "dry_run",
    )


def notify_shoe_job_status_changed(
    session: Session,
    *,
    tenant_id: UUID,
    shoe_repair_job_id: UUID,
    customer_name: str,
    to_phone: str,
    job_number: str,
    status_token: str,
    new_status: str,
) -> None:
    """Send a status-update SMS on milestone shoe job transitions."""
    message_map: dict[str, str] = {
        "go_ahead": (
            f"Hi {customer_name}, your shoe repair job #{job_number} has been approved — we'll get started soon."
        ),
        "working_on": (
            f"Hi {customer_name}, great news — we've started work on your shoes (job #{job_number}). "
            f"We'll let you know when they're ready."
        ),
        "completed": (
            f"Hi {customer_name}, your shoes (job #{job_number}) are ready for collection! "
            f"Please contact us to arrange pick-up."
        ),
        "awaiting_collection": (
            f"Hi {customer_name}, your shoes (job #{job_number}) are ready and waiting for collection! "
            f"Please contact us to arrange pick-up."
        ),
        "collected": (
            f"Thank you {customer_name}! Your shoes (job #{job_number}) have been collected. "
            f"We hope you enjoy them — don't hesitate to reach out if you need anything."
        ),
    }

    body = message_map.get(new_status)
    if not body:
        return

    body = f"{body} Track live status: {settings.public_base_url}/shoe-status/{status_token}"

    sid = _send_sms(to_phone, body)
    _persist(
        session,
        tenant_id=tenant_id,
        repair_job_id=None,
        shoe_repair_job_id=shoe_repair_job_id,
        to_phone=to_phone,
        body=body,
        event=f"status_{new_status}",
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
            parts.append(f" {format_in_timezone(dt, settings.schedule_calendar_timezone, '%a %d %b at %H:%M')}")
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
