"""
Transactional email via Twilio SendGrid (Mail Send API).

Configure in Twilio Console → Email → API Keys, then set SENDGRID_API_KEY.
SMS remains on TWILIO_*; email uses SendGrid under the same Twilio account.

When enable_email_notifications is False or no API key is set, messages are logged only (dry-run).
"""
from __future__ import annotations

import base64
import logging
from typing import Sequence

import httpx

from .config import settings

logger = logging.getLogger(__name__)


def _enabled() -> bool:
    return bool(getattr(settings, "enable_email_notifications", False))


def _api_key() -> str:
    return (getattr(settings, "sendgrid_api_key", "") or "").strip()


def _from_email() -> str:
    return (getattr(settings, "email_from_address", "") or "noreply@em695.mainspring.au").strip()


def _from_name(shop_name: str | None = None) -> str:
    default = (getattr(settings, "email_from_name", "") or "").strip()
    if default:
        return default
    return (shop_name or "").strip() or "Mainspring"


def _currency_symbol(currency: str) -> str:
    cur = (currency or "AUD").upper()
    return "$" if cur in ("AUD", "USD", "NZD", "CAD") else f"{currency} "


def email_skip_reason(to_email: str | None) -> str | None:
    """Why email was not attempted; None means send may proceed."""
    if not (to_email or "").strip():
        return "no_email"
    if not _enabled():
        return "email_disabled"
    if not _api_key():
        return "sendgrid_not_configured"
    return None


def _format_line_items(line_items: Sequence[dict]) -> str:
    lines: list[str] = []
    for li in line_items:
        desc = (li.get("description") or "Item").strip()
        qty = li.get("quantity", 1)
        total_cents = int(li.get("total_price_cents") or 0)
        lines.append(f"  • {desc} — qty {qty} — ${total_cents / 100:.2f}")
    return "\n".join(lines) if lines else ""


def send_quote_sent_email(
    *,
    to_email: str,
    customer_name: str,
    total_cents: int,
    approval_token: str,
    job_number: str,
    shop_name: str = "Your repair shop",
    line_items: Sequence[dict] | None = None,
) -> tuple[bool, str | None]:
    """Send email when a watch repair quote is sent to the customer."""
    if not (to_email or "").strip():
        return False, None
    approval_url = f"{settings.public_base_url.rstrip('/')}/approve/{approval_token}"
    total = total_cents / 100
    items_block = _format_line_items(line_items or [])
    if items_block:
        items_block = f"\n\nLine items:\n{items_block}\n"
    subject = f"Your watch repair quote – Job #{job_number}"
    body_plain = (
        f"Hi {customer_name},\n\n"
        f"Your watch repair quote for job #{job_number} is ${total:.2f}.{items_block}\n"
        f"Reply YES to approve or NO to decline, or open this link to view details:\n{approval_url}\n\n"
        f"Thanks,\n{shop_name}"
    )
    return _send_email(
        to_email=to_email.strip(),
        subject=subject,
        body_plain=body_plain,
        shop_name=shop_name,
        event="quote_sent",
    )


def send_invoice_email(
    *,
    to_email: str,
    customer_name: str,
    invoice_number: str,
    job_number: str,
    total_cents: int,
    currency: str = "AUD",
    shop_name: str = "Your repair shop",
    line_items: Sequence[dict] | None = None,
    pdf_bytes: bytes | None = None,
) -> tuple[bool, str | None]:
    """Send email when a watch repair invoice is sent to the customer."""
    if not (to_email or "").strip():
        return False, None
    sym = _currency_symbol(currency)
    total = total_cents / 100
    items_block = _format_line_items(line_items or [])
    if items_block:
        items_block = f"\n\nLine items:\n{items_block}\n"
    subject = f"Invoice {invoice_number} – Job #{job_number}"
    body_plain = (
        f"Hi {customer_name},\n\n"
        f"Please find your invoice {invoice_number} for watch repair job #{job_number}.\n"
        f"Amount due: {sym}{total:.2f}.{items_block}\n"
        f"Contact {shop_name} to arrange payment or collection.\n\n"
        f"Thanks,\n{shop_name}"
    )
    return _send_email(
        to_email=to_email.strip(),
        subject=subject,
        body_plain=body_plain,
        shop_name=shop_name,
        event="invoice_sent",
        pdf_bytes=pdf_bytes,
        pdf_filename=f"Invoice-{invoice_number}.pdf",
    )


def send_mobile_quote_email(
    *,
    to_email: str,
    customer_name: str,
    total_cents: int,
    currency: str,
    job_number: str,
    shop_name: str,
    quote_approval_token: str,
    line_items: Sequence[dict] | None = None,
) -> tuple[bool, str | None]:
    """Send email when a Mobile Services (auto key) quote is sent."""
    if not (to_email or "").strip():
        return False, None
    sym = _currency_symbol(currency)
    total = total_cents / 100
    portal_url = f"{settings.public_base_url.rstrip('/')}/mobile-quote/{quote_approval_token}"
    items_block = _format_line_items(line_items or [])
    if items_block:
        items_block = f"\n\nLine items:\n{items_block}\n"
    shop = shop_name.strip() or "us"
    subject = f"Your quote from {shop} – Job #{job_number}"
    body_plain = (
        f"Hi {customer_name},\n\n"
        f"Your quote from {shop} for job #{job_number} is {sym}{total:.2f}.{items_block}\n"
        f"Please review and accept here:\n{portal_url}\n\n"
        f"Reply to this email if you have any questions.\n\n"
        f"Thanks,\n{shop_name}"
    )
    return _send_email(
        to_email=to_email.strip(),
        subject=subject,
        body_plain=body_plain,
        shop_name=shop_name,
        event="mobile_quote_sent",
    )


def send_mobile_invoice_email(
    *,
    to_email: str,
    customer_name: str,
    invoice_number: str,
    job_number: str,
    total_cents: int,
    currency: str,
    shop_name: str,
    customer_view_token: str,
    line_items: Sequence[dict] | None = None,
    pdf_bytes: bytes | None = None,
) -> tuple[bool, str | None]:
    """Send email when a Mobile Services (auto key) invoice is sent."""
    if not (to_email or "").strip():
        return False, None
    sym = _currency_symbol(currency)
    total = total_cents / 100
    view_url = f"{settings.public_base_url.rstrip('/')}/mobile-invoice/{customer_view_token}"
    items_block = _format_line_items(line_items or [])
    if items_block:
        items_block = f"\n\nLine items:\n{items_block}\n"
    shop = shop_name.strip() or "us"
    subject = f"Invoice {invoice_number} from {shop} – Job #{job_number}"
    body_plain = (
        f"Hi {customer_name},\n\n"
        f"Your job #{job_number} with {shop} is complete. "
        f"Invoice {invoice_number} total: {sym}{total:.2f}.{items_block}\n"
        f"View your invoice and pay online (if available):\n{view_url}\n\n"
        f"Thank you for your business.\n\n"
        f"{shop_name}"
    )
    return _send_email(
        to_email=to_email.strip(),
        subject=subject,
        body_plain=body_plain,
        shop_name=shop_name,
        event="mobile_invoice_sent",
        pdf_bytes=pdf_bytes,
        pdf_filename=f"Invoice-{invoice_number}.pdf",
    )


def send_job_ready_email(
    *,
    to_email: str,
    customer_name: str,
    job_number: str,
    status_token: str,
    shop_name: str = "Your repair shop",
) -> tuple[bool, str | None]:
    """Send email when a job is ready for collection (completed / awaiting_collection)."""
    if not (to_email or "").strip():
        return False, None
    status_url = f"{settings.public_base_url.rstrip('/')}/status/{status_token}"
    subject = f"Your watch is ready for collection – Job #{job_number}"
    body_plain = (
        f"Hi {customer_name},\n\n"
        f"Your watch (job #{job_number}) is ready for collection. "
        f"Check status: {status_url}\n\n"
        f"Thanks,\n{shop_name}"
    )
    return _send_email(
        to_email=to_email.strip(),
        subject=subject,
        body_plain=body_plain,
        shop_name=shop_name,
        event="job_ready",
    )


def _send_email(
    *,
    to_email: str,
    subject: str,
    body_plain: str,
    shop_name: str,
    event: str,
    pdf_bytes: bytes | None = None,
    pdf_filename: str = "invoice.pdf",
) -> tuple[bool, str | None]:
    from_addr = _from_email()
    if not _enabled():
        logger.info("email (disabled) %s to %s: %s", event, to_email, subject)
        return False, None
    key = _api_key()
    if not key:
        logger.info("email (dry-run, no SENDGRID_API_KEY) %s to %s: %s", event, to_email, subject)
        return False, None
    payload: dict = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": from_addr, "name": _from_name(shop_name)},
        "subject": subject,
        "content": [{"type": "text/plain", "value": body_plain}],
    }
    if pdf_bytes:
        payload["attachments"] = [
            {
                "content": base64.b64encode(pdf_bytes).decode(),
                "type": "application/pdf",
                "filename": pdf_filename,
                "disposition": "attachment",
            }
        ]
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                "https://api.sendgrid.com/v3/mail/send",
                json=payload,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            )
        if 200 <= resp.status_code < 300:
            logger.info("Twilio SendGrid sent %s to %s from %s", event, to_email, from_addr)
            return True, None
        detail = (resp.text or "").strip()[:400]
        err = f"SendGrid HTTP {resp.status_code} (from={from_addr})"
        if detail:
            err = f"{err}: {detail}"
        logger.warning("Twilio SendGrid %s failed for %s: %s", event, to_email, err)
        return False, err
    except Exception as e:
        logger.exception("Twilio SendGrid %s failed for %s: %s", event, to_email, e)
        return False, str(e)[:400]
