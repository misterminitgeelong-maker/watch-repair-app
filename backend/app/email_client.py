"""
Transactional email via Twilio SendGrid (Mail Send API).

Configure in Twilio Console → Email → API Keys, then set SENDGRID_API_KEY.
SMS remains on TWILIO_*; email uses SendGrid under the same Twilio account.

When enable_email_notifications is False or no API key is set, messages are logged only (dry-run).
"""
from __future__ import annotations

import base64
import html as _html
import logging
from typing import Sequence

import httpx

from .config import settings
from .email_templates import ShopInfo, render_transactional_email

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
    body_html = render_transactional_email(
        title=f"Quote · Job #{job_number}",
        preheader=f"Your watch repair quote is ${total:.2f}",
        greeting=f"Hi {customer_name},",
        intro_html=(
            f"Here is your quote for <strong>watch repair job #{_html.escape(job_number)}</strong>. "
            "Tap below to approve or decline."
        ),
        shop=ShopInfo(name=shop_name),
        cta_label="Review quote",
        cta_url=approval_url,
        line_items=line_items or [],
        total_cents=total_cents,
        currency="AUD",
    )
    return _send_email(
        to_email=to_email.strip(),
        subject=subject,
        body_plain=body_plain,
        body_html=body_html,
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
    shop_logo_url: str | None = None,
    shop_brand_color: str | None = None,
    pdf_bytes: bytes | None = None,
    pay_url: str | None = None,
) -> tuple[bool, str | None]:
    """Send email when a watch repair invoice is sent to the customer."""
    if not (to_email or "").strip():
        return False, None
    sym = _currency_symbol(currency)
    total = total_cents / 100
    items_block = _format_line_items(line_items or [])
    if items_block:
        items_block = f"\n\nLine items:\n{items_block}\n"
    pay_url = (pay_url or "").strip() or None
    closing = (
        f"Pay online: {pay_url}\n\n" if pay_url
        else f"Contact {shop_name} to arrange payment or collection.\n\n"
    )
    subject = f"Invoice {invoice_number} – Job #{job_number}"
    body_plain = (
        f"Hi {customer_name},\n\n"
        f"Please find your invoice {invoice_number} for watch repair job #{job_number}.\n"
        f"Amount due: {sym}{total:.2f}.{items_block}\n"
        f"{closing}"
        f"Thanks,\n{shop_name}"
    )
    intro_html = (
        f"Please find your invoice for <strong>watch repair job #{_html.escape(job_number)}</strong> below. "
        + (
            "Use the button below to view and pay online."
            if pay_url
            else f"Contact {_html.escape(shop_name)} to arrange payment or collection."
        )
    )
    body_html = render_transactional_email(
        title=f"Invoice {invoice_number}",
        preheader=f"Invoice {invoice_number} · {sym}{total:.2f}",
        greeting=f"Hi {customer_name},",
        intro_html=intro_html,
        shop=ShopInfo(name=shop_name, logo_url=shop_logo_url, brand_color=shop_brand_color),
        cta_label="View & pay online" if pay_url else None,
        cta_url=pay_url,
        line_items=line_items or [],
        total_cents=total_cents,
        currency=currency,
        note_html="A PDF copy of your invoice is attached for your records." if pdf_bytes else None,
    )
    return _send_email(
        to_email=to_email.strip(),
        subject=subject,
        body_plain=body_plain,
        body_html=body_html,
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
    subtotal_cents: int | None = None,
    tax_cents: int | None = None,
    shop_address: str | None = None,
    shop_phone: str | None = None,
    shop_email: str | None = None,
    shop_abn: str | None = None,
    shop_logo_url: str | None = None,
    shop_brand_color: str | None = None,
    pdf_bytes: bytes | None = None,
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
    body_html = render_transactional_email(
        title=f"Quote · Job #{job_number}",
        preheader=f"Your quote from {shop} is {sym}{total:.2f}",
        greeting=f"Hi {customer_name},",
        intro_html=(
            f"Here is your quote for <strong>job #{_html.escape(job_number)}</strong>. "
            "Review the details below and tap the button to approve online."
        ),
        shop=ShopInfo(
            name=shop_name,
            address=shop_address,
            phone=shop_phone,
            email=shop_email,
            abn=shop_abn,
            logo_url=shop_logo_url,
            brand_color=shop_brand_color,
        ),
        cta_label="Review & accept quote",
        cta_url=portal_url,
        line_items=line_items or [],
        subtotal_cents=subtotal_cents,
        tax_cents=tax_cents,
        total_cents=total_cents,
        currency=currency,
        note_html="Have a question? Just reply to this email and it will reach us directly.",
    )
    return _send_email(
        to_email=to_email.strip(),
        subject=subject,
        body_plain=body_plain,
        body_html=body_html,
        shop_name=shop_name,
        reply_to=shop_email,
        event="mobile_quote_sent",
        pdf_bytes=pdf_bytes,
        pdf_filename=f"Quote-{job_number}.pdf",
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
    subtotal_cents: int | None = None,
    tax_cents: int | None = None,
    shop_address: str | None = None,
    shop_phone: str | None = None,
    shop_email: str | None = None,
    shop_abn: str | None = None,
    shop_logo_url: str | None = None,
    shop_brand_color: str | None = None,
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
    body_html = render_transactional_email(
        title=f"Invoice {invoice_number}",
        preheader=f"Invoice {invoice_number} from {shop} · {sym}{total:.2f}",
        greeting=f"Hi {customer_name},",
        intro_html=(
            f"Your <strong>job #{_html.escape(job_number)}</strong> is complete — thank you. "
            "Your invoice is below. You can view it and pay securely online."
        ),
        shop=ShopInfo(
            name=shop_name,
            address=shop_address,
            phone=shop_phone,
            email=shop_email,
            abn=shop_abn,
            logo_url=shop_logo_url,
            brand_color=shop_brand_color,
        ),
        cta_label="View & pay invoice",
        cta_url=view_url,
        line_items=line_items or [],
        subtotal_cents=subtotal_cents,
        tax_cents=tax_cents,
        total_cents=total_cents,
        currency=currency,
        note_html="A PDF copy of your invoice is attached for your records.",
    )
    return _send_email(
        to_email=to_email.strip(),
        subject=subject,
        body_plain=body_plain,
        body_html=body_html,
        shop_name=shop_name,
        reply_to=shop_email,
        event="mobile_invoice_sent",
        pdf_bytes=pdf_bytes,
        pdf_filename=f"Invoice-{invoice_number}.pdf",
    )


def send_portal_bookmark_email(
    *,
    to_email: str,
    portal_url: str,
    expires_days: int = 30,
    shop_name: str = "Mainspring",
) -> tuple[bool, str | None]:
    """Send a bookmark link for the cross-shop customer repair portal."""
    if not (to_email or "").strip():
        return False, None
    subject = "Your repair tracking link"
    body_plain = (
        f"Hi,\n\n"
        f"Save this link to track your repairs any time (valid for {expires_days} days):\n"
        f"{portal_url}\n\n"
        f"Thanks,\n{shop_name}"
    )
    body_html = render_transactional_email(
        title="Track your repairs",
        preheader=f"Bookmark this link — valid for {expires_days} days",
        greeting="Hi,",
        intro_html=(
            "Use the button below to see all your active repairs. "
            f"This link stays valid for <strong>{expires_days} days</strong>."
        ),
        shop=ShopInfo(name=shop_name),
        cta_label="Open my repairs",
        cta_url=portal_url,
    )
    return _send_email(
        to_email=to_email.strip(),
        subject=subject,
        body_plain=body_plain,
        body_html=body_html,
        shop_name=shop_name,
        event="portal_bookmark",
    )


def send_portal_status_email(
    *,
    to_email: str,
    shop_name: str,
    job_label: str,
    old_status: str,
    new_status: str,
    status_url: str,
) -> tuple[bool, str | None]:
    """Email when a portal customer opted into status change notifications."""
    if not (to_email or "").strip():
        return False, None
    new_label = new_status.replace("_", " ")
    subject = f"Job update — {job_label}"
    body_plain = (
        f"Hi,\n\n"
        f"{shop_name} updated your repair ({job_label}). "
        f"New status: {new_label}.\n\n"
        f"View details: {status_url}\n\n"
        f"Thanks,\n{shop_name}"
    )
    body_html = render_transactional_email(
        title=f"Status update · {job_label}",
        preheader=f"New status: {new_label}",
        greeting="Hi,",
        intro_html=f"<strong>{_html.escape(shop_name)}</strong> updated your job. New status: <strong>{_html.escape(new_label)}</strong>.",
        shop=ShopInfo(name=shop_name),
        cta_label="View job",
        cta_url=status_url,
    )
    return _send_email(
        to_email=to_email.strip(),
        subject=subject,
        body_plain=body_plain,
        body_html=body_html,
        shop_name=shop_name,
        event="portal_status",
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
    body_html = render_transactional_email(
        title=f"Ready for collection · Job #{job_number}",
        preheader="Your watch is ready for collection",
        greeting=f"Hi {customer_name},",
        intro_html=(
            f"Good news — your watch (<strong>job #{_html.escape(job_number)}</strong>) is ready for collection."
        ),
        shop=ShopInfo(name=shop_name),
        cta_label="Check job status",
        cta_url=status_url,
    )
    return _send_email(
        to_email=to_email.strip(),
        subject=subject,
        body_plain=body_plain,
        body_html=body_html,
        shop_name=shop_name,
        event="job_ready",
    )


_SALES_REPORT_CATEGORY_LABELS = {"watch": "Watch Repair", "shoe": "Shoe Repair", "mobile": "Mobile Services"}


def send_sales_report_email(
    *,
    to_email: str,
    shop_name: str,
    period_label: str,
    period_start: str,
    period_end: str,
    category_summary: dict[str, dict],
    csv_bytes: bytes,
    csv_filename: str,
) -> tuple[bool, str | None]:
    """Send a scheduled weekly/monthly sales-by-category report with the sales CSV attached."""
    if not (to_email or "").strip():
        return False, None
    total_revenue_cents = sum(int(cat.get("revenue_cents", 0)) for cat in category_summary.values())
    active_categories = {
        key: cat for key, cat in category_summary.items() if cat.get("jobs") or cat.get("revenue_cents")
    }
    line_items = [
        {
            "description": _SALES_REPORT_CATEGORY_LABELS.get(key, key),
            "quantity": cat.get("jobs", 0),
            "total_price_cents": cat.get("revenue_cents", 0),
        }
        for key, cat in active_categories.items()
    ]
    lines_plain = "\n".join(
        f"  • {_SALES_REPORT_CATEGORY_LABELS.get(key, key)}: {cat.get('jobs', 0)} jobs, "
        f"${cat.get('revenue_cents', 0) / 100:.2f} revenue"
        for key, cat in active_categories.items()
    ) or "  No sales recorded for this period."
    subject = f"{period_label} sales report – {period_start} to {period_end}"
    body_plain = (
        f"Hi,\n\n"
        f"Your {period_label.lower()} sales report for {period_start} to {period_end}:\n\n"
        f"{lines_plain}\n\n"
        f"Total revenue: ${total_revenue_cents / 100:.2f}\n\n"
        f"Full transaction-level detail is attached as a CSV.\n\n"
        f"— {shop_name}"
    )
    body_html = render_transactional_email(
        title=f"{period_label} sales report",
        preheader=f"{period_start} to {period_end} · ${total_revenue_cents / 100:.2f} revenue",
        greeting="Hi,",
        intro_html=(
            f"Here's your <strong>{_html.escape(period_label.lower())} sales report</strong> for "
            f"{_html.escape(period_start)} to {_html.escape(period_end)}."
        ),
        shop=ShopInfo(name=shop_name),
        line_items=line_items,
        total_cents=total_revenue_cents,
        currency="AUD",
        note_html="Full transaction-level detail is attached as a CSV.",
    )
    return _send_email(
        to_email=to_email.strip(),
        subject=subject,
        body_plain=body_plain,
        body_html=body_html,
        shop_name=shop_name,
        event="sales_report",
        attachment_bytes=csv_bytes,
        attachment_filename=csv_filename,
        attachment_mime_type="text/csv",
    )


def _send_email(
    *,
    to_email: str,
    subject: str,
    body_plain: str,
    shop_name: str,
    event: str,
    body_html: str | None = None,
    reply_to: str | None = None,
    pdf_bytes: bytes | None = None,
    pdf_filename: str = "invoice.pdf",
    attachment_bytes: bytes | None = None,
    attachment_filename: str = "attachment",
    attachment_mime_type: str = "text/csv",
) -> tuple[bool, str | None]:
    from_addr = _from_email()
    if not _enabled():
        logger.info("email (disabled) %s to %s: %s", event, to_email, subject)
        return False, None
    key = _api_key()
    if not key:
        logger.info("email (dry-run, no SENDGRID_API_KEY) %s to %s: %s", event, to_email, subject)
        return False, None
    # text/plain must precede text/html per RFC / SendGrid ordering rules.
    content: list[dict] = [{"type": "text/plain", "value": body_plain}]
    if body_html:
        content.append({"type": "text/html", "value": body_html})
    payload: dict = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": from_addr, "name": _from_name(shop_name)},
        "subject": subject,
        "content": content,
        # Category for SendGrid analytics/deliverability segmentation.
        "categories": [event],
    }
    # Replies should reach the shop, not the unattended noreply sender.
    reply = (reply_to or "").strip()
    if reply and "@" in reply and reply.lower() != from_addr.lower():
        payload["reply_to"] = {"email": reply, "name": _from_name(shop_name)}
    # List-Unsubscribe improves inbox placement and is expected by Gmail/Yahoo.
    unsub_target = reply if (reply and "@" in reply) else from_addr
    payload["headers"] = {
        "List-Unsubscribe": f"<mailto:{unsub_target}?subject=unsubscribe>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    }
    attachments: list[dict] = []
    if pdf_bytes:
        attachments.append(
            {
                "content": base64.b64encode(pdf_bytes).decode(),
                "type": "application/pdf",
                "filename": pdf_filename,
                "disposition": "attachment",
            }
        )
    if attachment_bytes:
        attachments.append(
            {
                "content": base64.b64encode(attachment_bytes).decode(),
                "type": attachment_mime_type,
                "filename": attachment_filename,
                "disposition": "attachment",
            }
        )
    if attachments:
        payload["attachments"] = attachments
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
