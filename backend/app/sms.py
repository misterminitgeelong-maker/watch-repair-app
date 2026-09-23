"""
SMS notification service using Twilio.

If Twilio credentials are not configured (empty strings) the module
operates in dry-run mode: messages are logged to stdout but not sent.
This keeps the app fully functional in development without a Twilio account.
"""
import logging
import time
from datetime import datetime, timezone
from uuid import UUID

from sqlmodel import Session, select

from .money import format_cents
from .config import settings
from .database import engine
from .datetime_utils import format_in_timezone
from .models import JobMessage, SmsLog, Tenant, User
from .notification_retry import (
    backoff_seconds,
    http_status_from_exc,
    inline_retry_attempts,
    is_retryable_http_status,
    is_timeout_exc,
    is_transport_exc,
    pin_attempts_if_permanent,
)

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

_twilio_client = None
_twilio_client_creds: tuple[str, str] | None = None


def reset_twilio_client() -> None:
    """Drop the cached Twilio client (tests that swap credentials)."""
    global _twilio_client, _twilio_client_creds
    _twilio_client = None
    _twilio_client_creds = None


def _get_twilio_client():
    """Module-level lazy singleton — one TLS handshake, reused across sends."""
    global _twilio_client, _twilio_client_creds
    creds = (settings.twilio_account_sid, settings.twilio_auth_token)
    if _twilio_client is None or _twilio_client_creds != creds:
        from twilio.rest import Client  # type: ignore[import]

        _twilio_client = Client(creds[0], creds[1])
        _twilio_client_creds = creds
    return _twilio_client


def _send_sms(to: str, body: str) -> tuple[str | None, str, str | None, int]:
    """Send an SMS with bounded retry on timeouts and 5xx. Never retries a 4xx.

    Returns (provider SID or None, status, error, attempt_count) where status is
    one of "sent" | "dry_run" | "failed".
    """
    if not (settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_from_number):
        logger.info("[SMS DRY-RUN] To=%s | %s", to, body)
        return None, "dry_run", None, 0

    max_attempts = inline_retry_attempts()
    last_error: str | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            client = _get_twilio_client()
            message = client.messages.create(
                body=body,
                from_=settings.twilio_from_number,
                to=to,
            )
            logger.info("[SMS SENT] sid=%s to=%s", message.sid, to)
            return message.sid, "sent", None, attempt
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)[:400]
            status = http_status_from_exc(exc)
            if status is not None and 400 <= status < 500:
                logger.error("[SMS ERROR] to=%s error=%s", to, exc)
                return None, "failed", last_error, pin_attempts_if_permanent(attempt, permanent=True)
            retryable = is_retryable_http_status(status) or is_timeout_exc(exc) or is_transport_exc(exc)
            if retryable and attempt < max_attempts:
                time.sleep(backoff_seconds(attempt - 1))
                continue
            logger.error("[SMS ERROR] to=%s error=%s", to, exc)
            return None, "failed", last_error, attempt
    return None, "failed", last_error, max_attempts


def _is_sqlite() -> bool:
    return engine.dialect.name == "sqlite"


def _begin_sms_log(session: Session, **kwargs) -> UUID:
    row = SmsLog(**kwargs)
    if _is_sqlite():
        session.add(row)
        session.flush()
        return row.id
    with Session(engine) as log_session:
        log_session.add(row)
        log_session.commit()
        log_session.refresh(row)
        return row.id


def _finish_sms_log(session: Session, log_id: UUID, **fields) -> None:
    if _is_sqlite():
        row = session.get(SmsLog, log_id)
        if row is None:
            return
        for key, value in fields.items():
            setattr(row, key, value)
        session.add(row)
        return
    with Session(engine) as log_session:
        row = log_session.get(SmsLog, log_id)
        if row is None:
            return
        for key, value in fields.items():
            setattr(row, key, value)
        log_session.add(row)
        log_session.commit()


def _logged_send(
    session: Session,
    *,
    tenant_id: UUID,
    repair_job_id: UUID | None,
    to_phone: str,
    body: str,
    event: str,
    shoe_repair_job_id: UUID | None = None,
    auto_key_job_id: UUID | None = None,
    existing_log_id: UUID | None = None,
) -> tuple[str | None, str]:
    """Persist the attempt, then send. Failure mode is a spurious row, not a silent send."""
    now = datetime.now(timezone.utc)
    log_id = existing_log_id
    if log_id is None:
        log_id = _begin_sms_log(
            session,
            tenant_id=tenant_id,
            repair_job_id=repair_job_id,
            shoe_repair_job_id=shoe_repair_job_id,
            auto_key_job_id=auto_key_job_id,
            to_phone=to_phone,
            body=body,
            event=event,
            provider_sid=None,
            status="failed",
            attempt_count=0,
            last_attempt_at=now,
        )
    sid, status, _error, attempts = _send_sms(to_phone, body)
    _finish_sms_log(
        session,
        log_id,
        provider_sid=sid,
        status=status,
        attempt_count=attempts,
        last_attempt_at=datetime.now(timezone.utc),
    )
    return sid, status


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
    """Back-compat wrapper: log-then-send is now `_logged_send`. Kept for callers
    that still pass a completed (sid, status) pair (e.g. portal status).
    """
    if provider_sid is not None or status in {"sent", "dry_run", "failed"}:
        # Already sent — record only, without a second provider call.
        _begin_sms_log(
            session,
            tenant_id=tenant_id,
            repair_job_id=repair_job_id,
            shoe_repair_job_id=shoe_repair_job_id,
            auto_key_job_id=auto_key_job_id,
            to_phone=to_phone,
            body=body,
            event=event,
            provider_sid=provider_sid,
            status=status,
            attempt_count=1 if status != "dry_run" else 0,
            last_attempt_at=datetime.now(timezone.utc),
        )
        return
    _logged_send(
        session,
        tenant_id=tenant_id,
        repair_job_id=repair_job_id,
        to_phone=to_phone,
        body=body,
        event=event,
        shoe_repair_job_id=shoe_repair_job_id,
        auto_key_job_id=auto_key_job_id,
    )


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
    sid, sms_status, _, _ = _send_sms(to_phone, body)
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
    sid, sms_status = _logged_send(
        session,
        tenant_id=tenant_id,
        repair_job_id=repair_job_id,
        to_phone=to_phone,
        body=body,
        event="job_live",
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
    sid, sms_status = _logged_send(
        session,
        tenant_id=tenant_id,
        repair_job_id=repair_job_id,
        to_phone=to_phone,
        body=body,
        event="work_started",
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
                parts.append(f"{desc} ({format_cents(item_total)})")
            work_summary = " This includes: " + ", ".join(parts) + "."

    body = (
        f"Hi {customer_name}, your repair quote from {shop} is {format_cents(total_cents)}.{work_summary} "
        f"Reply YES to approve or NO to decline, or tap here to view: {approval_url}"
    )
    sid, sms_status = _logged_send(
        session,
        tenant_id=tenant_id,
        repair_job_id=repair_job_id,
        to_phone=to_phone,
        body=body,
        event="quote_sent",
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
    approval_url = f"{settings.public_base_url}/approve/{approval_token}"
    shop = shop_name.strip() or "us"
    body = (
        f"Hi {customer_name}, just a friendly reminder from {shop} — your repair quote of {format_cents(total_cents)} "
        f"for job #{job_number} is still waiting for your go-ahead. "
        f"Reply YES to approve or NO to decline, or tap here to view: {approval_url}"
    )
    sid, sms_status = _logged_send(
        session,
        tenant_id=tenant_id,
        repair_job_id=repair_job_id,
        to_phone=to_phone,
        body=body,
        event="quote_reminder",
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
    portal_url = f"{settings.public_base_url}/mobile-quote/{quote_approval_token}"
    shop = shop_name.strip() or "us"
    body = (
        f"Hi {customer_name}, just a friendly reminder from {shop} — your quote of {format_cents(total_cents, currency)} "
        f"for job #{job_number} is still waiting for your decision. "
        f"Review and accept here: {portal_url} — Reply to this message if you have any questions."
    )
    if len(body) > 1500:
        body = body[:1490] + "…"
    sid, sms_status = _logged_send(
        session,
        tenant_id=tenant_id,
        repair_job_id=None,
        auto_key_job_id=auto_key_job_id,
        to_phone=to_phone,
        body=body,
        event="auto_key_quote_reminder",
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

    sid, sms_status = _logged_send(
        session,
        tenant_id=tenant_id,
        repair_job_id=repair_job_id,
        to_phone=to_phone,
        body=body,
        event=f"status_{new_status}",
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
    sid, sms_status = _logged_send(
        session,
        tenant_id=tenant_id,
        repair_job_id=None,
        to_phone=to_phone,
        body=lines,
        event="auto_key_day_before_reminder",
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
    sid, sms_status = _logged_send(
        session,
        tenant_id=tenant_id,
        repair_job_id=None,
        to_phone=to_phone,
        body=body,
        event="auto_key_customer_scheduled",
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
    sid, sms_status = _logged_send(
        session,
        tenant_id=tenant_id,
        repair_job_id=None,
        to_phone=to_phone,
        body=body,
        event="auto_key_customer_day_before",
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
    sid, sms_status = _logged_send(
        session,
        tenant_id=tenant_id,
        repair_job_id=None,
        to_phone=to_phone,
        body=body,
        event="auto_key_en_route",
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
    sid, sms_status = _logged_send(
        session,
        tenant_id=tenant_id,
        repair_job_id=None,
        to_phone=to_phone,
        body=body,
        event="auto_key_arrival_window",
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
) -> bool:
    """SMS after job completed with link to customer invoice page. Returns True if provider accepted the message."""
    if not mobile_services_customer_sms_enabled(session, tenant_id):
        return False
    shop = shop_name.strip() or "us"
    body = (
        f"Hi {customer_name}, your job #{job_number} with {shop} is now complete. "
        f"Your invoice total is {format_cents(total_cents, currency)}. You can view your invoice here: {view_url} — "
        f"Thank you for your business."
    )
    if len(body) > 1500:
        body = body[:1490] + "…"
    sid, sms_status = _logged_send(
        session,
        tenant_id=tenant_id,
        repair_job_id=None,
        to_phone=to_phone,
        body=body,
        event="auto_key_invoice_ready",
    )
    return sid is not None


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
    portal_url = f"{settings.public_base_url}/mobile-quote/{quote_approval_token}"
    shop = shop_name.strip() or "us"
    body = (
        f"Hi {customer_name}, your quote from {shop} for job #{job_number} is {format_cents(total_cents, currency)}. "
        f"Please review and accept here: {portal_url} — Reply to this message if you have any questions."
    )
    if len(body) > 1500:
        body = body[:1490] + "…"
    sid, sms_status = _logged_send(
        session,
        tenant_id=tenant_id,
        repair_job_id=None,
        auto_key_job_id=auto_key_job_id,
        to_phone=to_phone,
        body=body,
        event="auto_key_quote_sent",
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
        f"We've created your job (#{job_number}) — please follow the link to fill in your vehicle details, "
        f"preferred appointment time, and a photo of the key: {intake_url}"
    )
    if len(body) > 1500:
        body = body[:1490] + "…"
    sid, sms_status = _logged_send(
        session,
        tenant_id=tenant_id,
        repair_job_id=None,
        to_phone=to_phone,
        body=body,
        event="auto_key_customer_intake",
    )


def operator_dispatch_phone(tenant: Tenant | None) -> str | None:
    """Phone number for operator dispatch SMS (shop booking alerts)."""
    if not tenant:
        return None
    raw = getattr(tenant, "mobile_dispatch_phone", None)
    if not raw or not str(raw).strip():
        return None
    return str(raw).strip()


def operator_dispatch_email(session: Session, tenant: Tenant | None) -> str | None:
    """Best email for operator dispatch alerts: shop email, else the tenant owner's login email."""
    if not tenant:
        return None
    shop_email = (getattr(tenant, "shop_email", None) or "").strip()
    if shop_email:
        return shop_email
    owner = session.exec(
        select(User)
        .where(User.tenant_id == tenant.id)
        .where(User.role == "owner")
        .where(User.is_active == True)  # noqa: E712
        .order_by(User.created_at)
    ).first()
    return owner.email.strip() if owner and owner.email else None


def notify_website_lead_alert(
    session: Session,
    *,
    tenant_id: UUID,
    to_phone: str,
    customer_name: str,
    customer_phone: str | None,
    suburb: str,
    state_code: str,
    vehicle_make: str | None,
    vehicle_model: str | None,
    registration_plate: str | None,
    inbox_url: str,
) -> bool:
    """SMS operator when a website enquiry (email, not a live lead) is routed to their Lead Inbox.

    No timer, no cascade — this is a one-time FYI, unlike a live shop booking offer.
    """
    lines = ["New lead in your Lead Inbox."]
    cust_line = customer_name.strip()
    if customer_phone and customer_phone.strip():
        cust_line += f" · {customer_phone.strip()}"
    lines.append(f"Customer: {cust_line}")
    lines.append(f"Location: {suburb.strip()} {state_code.strip().upper()}")

    veh = " ".join(x for x in (vehicle_make or "", vehicle_model or "") if x and str(x).strip()).strip()
    if registration_plate and registration_plate.strip():
        veh = f"{veh} {registration_plate.strip()}".strip() if veh else registration_plate.strip()
    if veh:
        lines.append(f"Vehicle: {veh}")

    lines.append(f"Lead Inbox: {inbox_url}")

    body = "\n".join(lines)
    if len(body) > 1500:
        body = body[:1490] + "…"

    sid, sms_status = _logged_send(
        session,
        tenant_id=tenant_id,
        repair_job_id=None,
        to_phone=to_phone,
        body=body,
        event="website_lead_alert",
    )
    return sid is not None


def notify_mobile_lead_offer(
    session: Session,
    *,
    tenant_id: UUID,
    auto_key_job_id: UUID,
    to_phone: str,
    customer_name: str,
    customer_phone: str | None,
    suburb: str,
    state_code: str,
    vehicle_make: str | None,
    vehicle_model: str | None,
    registration_plate: str | None,
    job_number: str,
    timeout_minutes: int = 30,
    accept_url: str | None = None,
) -> bool:
    """SMS operator when a website lead is assigned for quoting."""
    lines = [f"New website lead — quote within {timeout_minutes} min."]
    cust_line = customer_name.strip()
    if customer_phone and customer_phone.strip():
        cust_line += f" · {customer_phone.strip()}"
    lines.append(f"Customer: {cust_line}")
    lines.append(f"Location: {suburb.strip()} {state_code.strip().upper()}")

    veh = " ".join(x for x in (vehicle_make or "", vehicle_model or "") if x and str(x).strip()).strip()
    if registration_plate and registration_plate.strip():
        veh = f"{veh} {registration_plate.strip()}".strip() if veh else registration_plate.strip()
    if veh:
        lines.append(f"Vehicle: {veh}")

    lines.append(f"Job #{job_number}")
    link = (accept_url or "").strip() or f"{settings.public_base_url.rstrip('/')}/auto-key"
    lines.append(f"Accept & quote: {link}")

    body = "\n".join(lines)
    if len(body) > 1500:
        body = body[:1490] + "…"

    sid, sms_status = _logged_send(
        session,
        tenant_id=tenant_id,
        repair_job_id=None,
        auto_key_job_id=auto_key_job_id,
        to_phone=to_phone,
        body=body,
        event="mobile_lead_offer",
    )
    return sid is not None


def notify_shop_owner_invite(
    session: Session,
    *,
    tenant_id: UUID,
    to_phone: str,
    tenant_name: str,
    shop_number: str | None,
    invite_url: str,
    expiry_days: int,
) -> bool:
    """Text a franchisee their one-time link to set up their own shop login."""
    shop_label = tenant_name.strip()
    if shop_number:
        shop_label += f" (#{shop_number})"
    body = (
        f"Mister Minit: set up your own login for {shop_label} "
        f"(replaces the shared HQ login) — {invite_url} "
        f"— link expires in {expiry_days} days."
    )
    sid, sms_status = _logged_send(
        session,
        tenant_id=tenant_id,
        repair_job_id=None,
        to_phone=to_phone,
        body=body,
        event="shop_owner_invite",
    )
    return sid is not None


def send_portal_login_code(session: Session, *, tenant_id: UUID, to_phone: str, shop_name: str, code: str) -> str:
    """Text a customer the code that opens the mobile-key portal. Returns the send status."""
    body = f"{shop_name.strip() or 'Your shop'}: your sign-in code is {code}. It expires in 10 minutes."
    _sid, sms_status = _logged_send(
        session,
        tenant_id=tenant_id,
        repair_job_id=None,
        to_phone=to_phone,
        body=body,
        event="portal_login_code",
    )
    return sms_status


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
    accept_url: str | None = None,
    timeout_minutes: int | None = None,
) -> bool:
    """SMS operator when a shop submits a pending mobile booking request."""
    from datetime import datetime

    shop = shop_name.strip() or "A shop"
    visit = "At shop" if visit_location_type == "at_shop" else "Customer site"
    urgency = f" — accept within {timeout_minutes} min or it opens to the Dispatch Pool." if timeout_minutes else " — review in app."
    lines = [f"New shop booking from {shop}{urgency}"]
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

    link = (accept_url or "").strip() or f"{settings.public_base_url.rstrip('/')}/auto-key"
    lines.append(f"Accept: {link}")

    body = "\n".join(lines)
    if len(body) > 1500:
        body = body[:1490] + "…"

    sid, sms_status = _logged_send(
        session,
        tenant_id=tenant_id,
        repair_job_id=None,
        to_phone=to_phone,
        body=body,
        event="shop_mobile_booking_pending",
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
    sid, sms_status = _logged_send(
        session,
        tenant_id=tenant_id,
        repair_job_id=None,
        to_phone=to_phone,
        body=body,
        event="shop_mobile_booking_accepted",
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
    sid, sms_status = _logged_send(
        session,
        tenant_id=tenant_id,
        repair_job_id=None,
        to_phone=to_phone,
        body=body,
        event="shop_mobile_booking_declined",
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
    sid, sms_status = _logged_send(
        session,
        tenant_id=tenant_id,
        repair_job_id=None,
        to_phone=to_phone,
        body=body,
        event="shop_mobile_booking_expired",
    )
    return sid is not None


def notify_shop_mobile_booking_moved_to_pool(
    session: Session,
    *,
    tenant_id: UUID,
    to_phone: str,
    shop_name: str,
    customer_name: str,
    operator_name: str,
) -> bool:
    """SMS the requesting shop when the assigned operator missed the offer window and it opened to the Dispatch Pool."""
    body = (
        f"{shop_name}: {operator_name.strip()} didn't respond in time for {customer_name.strip()}'s booking, "
        f"so it's now open in the Dispatch Pool for any nearby operator to claim."
    )
    sid, sms_status = _logged_send(
        session,
        tenant_id=tenant_id,
        repair_job_id=None,
        to_phone=to_phone,
        body=body,
        event="shop_mobile_booking_moved_to_pool",
    )
    return sid is not None


def notify_pool_jobs_waiting(
    session: Session,
    *,
    tenant_id: UUID,
    to_phone: str,
    job_count: int,
    pool_url: str,
) -> bool:
    """One digest SMS per operator when jobs have sat unclaimed in the Dispatch Pool nearby —
    never one text per job, and never repeated for the same job."""
    plural = "job" if job_count == 1 else "jobs"
    body = (
        f"{job_count} {plural} waiting in the Dispatch Pool near you — first to claim gets it.\n"
        f"Open pool: {pool_url}"
    )
    sid, sms_status = _logged_send(
        session,
        tenant_id=tenant_id,
        repair_job_id=None,
        to_phone=to_phone,
        body=body,
        event="pool_jobs_waiting",
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
    body = (
        f"Hi {customer_name}, your booking with {shop} is confirmed — "
        f"job #{job_number}{veh_bit} on {when}. "
        f"Quoted total: {format_cents(quote_total_cents, currency)}. Please confirm your booking here: {confirm_url}"
    )
    if len(body) > 1500:
        body = body[:1490] + "…"
    sid, sms_status = _logged_send(
        session,
        tenant_id=tenant_id,
        repair_job_id=None,
        to_phone=to_phone,
        body=body,
        event="auto_key_booking_request",
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
    sid, sms_status = _logged_send(
        session,
        tenant_id=tenant_id,
        repair_job_id=None,
        shoe_repair_job_id=shoe_repair_job_id,
        to_phone=to_phone,
        body=body,
        event="job_live",
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
    approval_url = f"{settings.public_base_url}/shoe-approve/{approval_token}"
    body = (
        f"Hi {customer_name}, your shoe repair quote from {shop_name} is {format_cents(total_cents)}. "
        f"Reply YES to approve or NO to decline, or tap here to view: {approval_url}"
    )
    sid, sms_status = _logged_send(
        session,
        tenant_id=tenant_id,
        repair_job_id=None,
        shoe_repair_job_id=shoe_repair_job_id,
        to_phone=to_phone,
        body=body,
        event="quote_sent",
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

    sid, sms_status = _logged_send(
        session,
        tenant_id=tenant_id,
        repair_job_id=None,
        shoe_repair_job_id=shoe_repair_job_id,
        to_phone=to_phone,
        body=body,
        event=f"status_{new_status}",
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
    sid, sms_status = _logged_send(
        session,
        tenant_id=tenant_id,
        repair_job_id=None,
        to_phone=to_phone,
        body=body,
        event="auto_key_schedule_changed",
    )
