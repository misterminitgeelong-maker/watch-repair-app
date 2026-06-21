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
from .models import JobMessage, SmsLog, Tenant

logger = logging.getLogger(__name__)


def tracking_sms_skip_reason(sent: bool, has_phone: bool) -> str | None:
    """Why intake tracking SMS was not delivered (for API responses)."""
    if sent:
        return None
    if not has_phone:
        return "no_phone"
    if not (settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_from_number):
        return "sms_not_configured"
    return "send_failed"


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
# Manual two-way messaging
# ---------------------------------------------------------------------------

def send_custom_job_message(
    session: Session,
    *,
    tenant_id: UUID,
    repair_job_id: UUID | None = None,
    shoe_repair_job_id: UUID | None = None,
    auto_key_job_id: UUID | None = None,
    to_phone: str,
    body: str,
) -> JobMessage:
    """Send a free-text SMS to a customer and persist it as an outbound JobMessage."""
    sid = _send_sms(to_phone, body)
    msg = JobMessage(
        tenant_id=tenant_id,
        repair_job_id=repair_job_id,
        shoe_repair_job_id=shoe_repair_job_id,
        auto_key_job_id=auto_key_job_id,
        direction="outbound",
        body=body,
        from_phone=settings.twilio_from_number or None,
        to_phone=to_phone,
        twilio_sid=sid,
    )
    session.add(msg)
    return msg


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
    shop_name: str = "",
) -> bool:
    """Send 'your job is live' SMS with link to track status. Returns True if provider accepted the message."""
    status_url = f"{settings.public_base_url}/status/{status_token}"
    shop = shop_name.strip() or "us"
    body = (
        f"Hi {customer_name}, thanks for bringing your watch in to {shop}. "
        f"Your job (#{job_number}) has been logged and we'll be in touch once we've had a chance to assess it. "
        f"Track your job here: {status_url}"
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
    return sid is not None


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
        f"Hi {customer_name}, great news — we've started work on your watch (job #{job_number}). "
        f"We'll be in touch in the coming days once it's ready for collection."
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
    line_items: list[dict] | None = None,
) -> None:
    """Send the quote approval SMS to the customer."""
    total = total_cents / 100
    currency_symbol = "$"
    approval_url = f"{settings.public_base_url}/approve/{approval_token}"

    shop = shop_name.strip() or "us"
    work_summary = ""
    if line_items:
        filled = [li for li in line_items if li.get("description", "").strip()]
        if filled:
            parts = []
            for li in filled:
                desc = li["description"].strip()
                item_total = li.get("total_price_cents") or (li.get("quantity", 1) * li.get("unit_price_cents", 0))
                parts.append(f"{desc} ({currency_symbol}{item_total / 100:.2f})")
            work_summary = " This includes: " + ", ".join(parts) + "."

    body = (
        f"Hi {customer_name}, your repair quote from {shop} is {currency_symbol}{total:.2f}.{work_summary} "
        f"Reply YES to approve or NO to decline, or tap here to view: {approval_url}"
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


def notify_quote_reminder(
    session: Session,
    *,
    tenant_id: UUID,
    repair_job_id: UUID,
    customer_name: str,
    to_phone: str,
    total_cents: int,
    approval_token: str,
    job_number: str,
    shop_name: str = "your watch repair shop",
) -> None:
    """Remind the customer about a quote they haven't decided on yet."""
    total = total_cents / 100
    approval_url = f"{settings.public_base_url}/approve/{approval_token}"
    shop = shop_name.strip() or "us"
    body = (
        f"Hi {customer_name}, just a friendly reminder from {shop} — your repair quote of ${total:.2f} "
        f"for job #{job_number} is still waiting for your go-ahead. "
        f"Reply YES to approve or NO to decline, or tap here to view: {approval_url}"
    )
    sid = _send_sms(to_phone, body)
    _persist(
        session,
        tenant_id=tenant_id,
        repair_job_id=repair_job_id,
        to_phone=to_phone,
        body=body,
        event="quote_reminder",
        provider_sid=sid,
        status="sent" if sid else "dry_run",
    )


def notify_auto_key_quote_reminder(
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
    quote_approval_token: str,
) -> None:
    """Remind the customer about a mobile services quote they haven't decided on yet."""
    if not mobile_services_customer_sms_enabled(session, tenant_id):
        return
    sym = "$" if currency.upper() in ("AUD", "USD", "NZD") else ""
    total = total_cents / 100
    portal_url = f"{settings.public_base_url}/mobile-quote/{quote_approval_token}"
    shop = shop_name.strip() or "us"
    body = (
        f"Hi {customer_name}, just a friendly reminder from {shop} — your quote of {sym}{total:.2f} "
        f"for job #{job_number} is still waiting for your decision. "
        f"Review and accept here: {portal_url} — Reply to this message if you have any questions."
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
        event="auto_key_quote_reminder",
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
    shop = shop_name.strip() or "us"
    status_url = f"{settings.public_base_url}/status/{status_token}"
    message_map: dict[str, str] = {
        "awaiting_go_ahead": (
            f"Hi {customer_name}, we've received your watch (job #{job_number}) and it's now in our queue. "
            f"We'll be in touch once we've assessed it. Track your job here: {status_url}"
        ),
        "go_ahead": (
            f"Hi {customer_name}, your repair has been approved — we'll get started on job #{job_number} shortly "
            f"and keep you updated along the way. Track your job here: {status_url}"
        ),
        "working_on": (
            f"Hi {customer_name}, we're now working on your watch (job #{job_number}). "
            f"We'll let you know as soon as it's ready. Track your job here: {status_url}"
        ),
        "completed": (
            f"Hi {customer_name}, your watch (job #{job_number}) is ready for collection. "
            f"Please come in or give us a call to arrange pick-up. Track your job here: {status_url}"
        ),
        "awaiting_collection": (
            f"Hi {customer_name}, your watch (job #{job_number}) is ready for collection. "
            f"Please come in or give us a call to arrange pick-up. Track your job here: {status_url}"
        ),
        "collected": (
            f"Hi {customer_name}, thanks for collecting your watch — we hope you're happy with the repair. "
            f"Don't hesitate to get in touch if you need anything. {shop}"
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
    body = (
        f"Hi {customer_name}, your appointment has been confirmed for {when}. "
        f"We'll be in touch the day before to confirm. If you need to reschedule, please reply to this message."
    )
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
    body = f"Hi {customer_name}, just a reminder that your technician is scheduled for tomorrow, {when}."
    if job_address:
        body += f" Address: {job_address[:50]}{'…' if len(job_address) > 50 else ''}"
    body += " We'll send you an arrival window on the day."
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

    body = f"Hi {customer_name}, your technician is now on the way to you."
    if scheduled_at:
        try:
            dt = (
                scheduled_at
                if isinstance(scheduled_at, datetime)
                else datetime.fromisoformat(str(scheduled_at).replace("Z", "+00:00"))
            )
            body += f" Scheduled arrival: {format_in_timezone(dt, settings.schedule_calendar_timezone)}."
        except (ValueError, TypeError):
            pass
    if job_address and job_address.strip():
        a = job_address.strip()
        body += f" {a[:70]}{'…' if len(a) > 70 else ''}."
    body += " Reply to this message if you need to reach us."
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
    body = (
        f"Hi {customer_name}, your technician is on the way and will arrive between {time_window}. "
        f"Please ensure someone is available at the vehicle. Reply to this message if you need to reach us."
    )
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
    shop = shop_name.strip() or "us"
    body = (
        f"Hi {customer_name}, your job #{job_number} with {shop} is now complete. "
        f"Your invoice total is {sym}{total:.2f}. You can view your invoice here: {view_url} — "
        f"Thank you for your business."
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
    quote_approval_token: str,
) -> None:
    """SMS when a quote is sent — lets the customer know the price and links to the approval portal."""
    if not mobile_services_customer_sms_enabled(session, tenant_id):
        return
    sym = "$" if currency.upper() in ("AUD", "USD", "NZD") else ""
    total = total_cents / 100
    portal_url = f"{settings.public_base_url}/mobile-quote/{quote_approval_token}"
    shop = shop_name.strip() or "us"
    body = (
        f"Hi {customer_name}, your quote from {shop} for job #{job_number} is {sym}{total:.2f}. "
        f"Please review and accept here: {portal_url} — Reply to this message if you have any questions."
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
    shop = shop_name.strip() or "us"
    body = (
        f"Hi {first}, thanks for getting in touch with {shop}. "
        f"We've created your job (#{job_number}) — please follow the link to fill in your vehicle details "
        f"and preferred appointment time: {intake_url}"
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


def operator_dispatch_phone(tenant: Tenant | None) -> str | None:
    """Phone number for operator dispatch SMS (shop booking alerts)."""
    if not tenant:
        return None
    raw = getattr(tenant, "mobile_dispatch_phone", None)
    if not raw or not str(raw).strip():
        return None
    return str(raw).strip()


def notify_shop_mobile_booking_request(
    session: Session,
    *,
    tenant_id: UUID,
    to_phone: str,
    shop_name: str,
    customer_name: str,
    customer_phone: str | None,
    vehicle_make: str | None,
    vehicle_model: str | None,
    registration_plate: str | None,
    visit_location_type: str,
    job_address: str,
    preferred_scheduled_at,
    job_type: str | None,
    notes: str | None,
) -> bool:
    """SMS operator when a shop submits a pending mobile booking request."""
    from datetime import datetime

    shop = shop_name.strip() or "A shop"
    visit = "At shop" if visit_location_type == "at_shop" else "Customer site"
    lines = [f"New shop booking from {shop} — review in app."]
    cust_line = customer_name.strip()
    if customer_phone and customer_phone.strip():
        cust_line += f" · {customer_phone.strip()}"
    lines.append(f"Customer: {cust_line}")

    veh = " ".join(x for x in (vehicle_make or "", vehicle_model or "") if x and str(x).strip()).strip()
    if registration_plate and registration_plate.strip():
        veh = f"{veh} {registration_plate.strip()}".strip() if veh else registration_plate.strip()
    if veh:
        lines.append(f"Vehicle: {veh}")

    type_bits = [visit]
    if job_type and job_type.strip():
        type_bits.append(job_type.strip())
    lines.append(f"Visit: {' · '.join(type_bits)}")

    if preferred_scheduled_at:
        try:
            dt = (
                preferred_scheduled_at
                if isinstance(preferred_scheduled_at, datetime)
                else datetime.fromisoformat(str(preferred_scheduled_at).replace("Z", "+00:00"))
            )
            when = format_in_timezone(dt, settings.schedule_calendar_timezone, "%a %d %b around %H:%M")
            lines.append(f"When: {when}")
        except (ValueError, TypeError):
            lines.append(f"When: {str(preferred_scheduled_at)[:32]}")

    addr = (job_address or "").strip()
    if addr:
        short = addr[:90] + ("…" if len(addr) > 90 else "")
        lines.append(f"Where: {short}")

    if notes and notes.strip():
        n = notes.strip()
        lines.append(f"Notes: {n[:120]}{'…' if len(n) > 120 else ''}")

    inbox_url = f"{settings.public_base_url.rstrip('/')}/auto-key"
    lines.append(f"Open: {inbox_url}")

    body = "\n".join(lines)
    if len(body) > 1500:
        body = body[:1490] + "…"

    sid = _send_sms(to_phone, body)
    _persist(
        session,
        tenant_id=tenant_id,
        repair_job_id=None,
        to_phone=to_phone,
        body=body,
        event="shop_mobile_booking_pending",
        provider_sid=sid,
        status="sent" if sid else "dry_run",
    )
    return sid is not None


def notify_shop_mobile_booking_accepted(
    session: Session,
    *,
    tenant_id: UUID,
    to_phone: str,
    shop_name: str,
    customer_name: str,
    operator_name: str,
    job_number: str | None,
) -> bool:
    job_part = f" Job {job_number}." if job_number else ""
    body = (
        f"{shop_name}: booking accepted for {customer_name.strip()} by {operator_name.strip()}."
        f"{job_part} Track status in Mainspring."
    )
    sid = _send_sms(to_phone, body)
    _persist(
        session,
        tenant_id=tenant_id,
        repair_job_id=None,
        to_phone=to_phone,
        body=body,
        event="shop_mobile_booking_accepted",
        provider_sid=sid,
        status="sent" if sid else "dry_run",
    )
    return sid is not None


def notify_shop_mobile_booking_declined(
    session: Session,
    *,
    tenant_id: UUID,
    to_phone: str,
    shop_name: str,
    customer_name: str,
    operator_name: str,
    decline_reason: str | None,
) -> bool:
    reason = (decline_reason or "").strip()
    reason_part = f" Reason: {reason[:120]}." if reason else ""
    body = (
        f"{shop_name}: booking declined for {customer_name.strip()} by {operator_name.strip()}."
        f"{reason_part}"
    )
    sid = _send_sms(to_phone, body)
    _persist(
        session,
        tenant_id=tenant_id,
        repair_job_id=None,
        to_phone=to_phone,
        body=body,
        event="shop_mobile_booking_declined",
        provider_sid=sid,
        status="sent" if sid else "dry_run",
    )
    return sid is not None


def notify_shop_mobile_booking_expired(
    session: Session,
    *,
    tenant_id: UUID,
    to_phone: str,
    shop_name: str,
    customer_name: str,
    operator_name: str,
) -> bool:
    body = (
        f"{shop_name}: booking for {customer_name.strip()} to {operator_name.strip()} "
        f"expired with no response. Submit a new request if still needed."
    )
    sid = _send_sms(to_phone, body)
    _persist(
        session,
        tenant_id=tenant_id,
        repair_job_id=None,
        to_phone=to_phone,
        body=body,
        event="shop_mobile_booking_expired",
        provider_sid=sid,
        status="sent" if sid else "dry_run",
    )
    return sid is not None


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

    shop = shop_name.strip() or "us"
    veh = " ".join(x for x in (vehicle_make or "", vehicle_model or "") if x).strip()
    veh_bit = f" ({veh})" if veh else ""
    try:
        dt = scheduled_at if isinstance(scheduled_at, datetime) else datetime.fromisoformat(str(scheduled_at).replace("Z", "+00:00"))
        when = format_in_timezone(dt, settings.schedule_calendar_timezone, "%a %d %b at %I:%M%p").replace(" 0", " ")
    except (ValueError, TypeError):
        when = str(scheduled_at)[:16] if scheduled_at else ""
    sym = "$" if currency.upper() in ("AUD", "USD", "NZD") else ""
    total = quote_total_cents / 100
    body = (
        f"Hi {customer_name}, your booking with {shop} is confirmed — "
        f"job #{job_number}{veh_bit} on {when}. "
        f"Quoted total: {sym}{total:.2f}. Please confirm your booking here: {confirm_url}"
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
) -> bool:
    """Send 'your shoe job is live' SMS with link to track status. Returns True if provider accepted the message."""
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
    return sid is not None


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
