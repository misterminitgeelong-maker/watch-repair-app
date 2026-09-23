"""
Transactional email via Twilio SendGrid (Mail Send API).

Configure in Twilio Console → Email → API Keys, then set SENDGRID_API_KEY.
SMS remains on TWILIO_*; email uses SendGrid under the same Twilio account.

When enable_email_notifications is False or no API key is set, messages are logged only (dry-run).
"""
from __future__ import annotations

import base64
import html as _html
import json
import logging
import time
from typing import Sequence
from uuid import UUID

import httpx
from sqlmodel import Session

from .config import settings
from .database import engine
from .email_templates import ShopInfo, render_transactional_email
from .models import EmailLog
from .money import format_cents
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



def email_skip_reason(to_email: str | None) -> str | None:
    """Why email was not attempted; None means send may proceed."""
    if not (to_email or "").strip():
        return "no_email"
    if not _enabled():
        return "email_disabled"
    if not _api_key():
        return "sendgrid_not_configured"
    return None


def _format_line_items(line_items: Sequence[dict], currency: str | None = None) -> str:
    lines: list[str] = []
    for li in line_items:
        desc = (li.get("description") or "Item").strip()
        qty = li.get("quantity", 1)
        total_cents = int(li.get("total_price_cents") or 0)
        lines.append(f"  • {desc} — qty {qty} — {format_cents(total_cents, currency)}")
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
    session: Session | None = None,
    tenant_id: UUID | None = None,
) -> tuple[bool, str | None]:
    """Send email when a watch repair quote is sent to the customer."""
    if not (to_email or "").strip():
        return False, None
    approval_url = f"{settings.public_base_url.rstrip('/')}/approve/{approval_token}"
    items_block = _format_line_items(line_items or [])
    if items_block:
        items_block = f"\n\nLine items:\n{items_block}\n"
    subject = f"Your watch repair quote – Job #{job_number}"
    body_plain = (
        f"Hi {customer_name},\n\n"
        f"Your watch repair quote for job #{job_number} is {format_cents(total_cents)}.{items_block}\n"
        f"Reply YES to approve or NO to decline, or open this link to view details:\n{approval_url}\n\n"
        f"Thanks,\n{shop_name}"
    )
    body_html = render_transactional_email(
        title=f"Quote · Job #{job_number}",
        preheader=f"Your watch repair quote is {format_cents(total_cents)}",
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
        session=session,
        tenant_id=tenant_id,
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
    session: Session | None = None,
    tenant_id: UUID | None = None,
) -> tuple[bool, str | None]:
    """Send email when a watch repair invoice is sent to the customer."""
    if not (to_email or "").strip():
        return False, None
    items_block = _format_line_items(line_items or [], currency)
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
        f"Amount due: {format_cents(total_cents, currency)}.{items_block}\n"
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
        preheader=f"Invoice {invoice_number} · {format_cents(total_cents, currency)}",
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
        session=session,
        tenant_id=tenant_id,
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
    session: Session | None = None,
    tenant_id: UUID | None = None,
) -> tuple[bool, str | None]:
    """Send email when a Mobile Services (auto key) quote is sent."""
    if not (to_email or "").strip():
        return False, None
    portal_url = f"{settings.public_base_url.rstrip('/')}/mobile-quote/{quote_approval_token}"
    items_block = _format_line_items(line_items or [], currency)
    if items_block:
        items_block = f"\n\nLine items:\n{items_block}\n"
    shop = shop_name.strip() or "us"
    subject = f"Your quote from {shop} – Job #{job_number}"
    body_plain = (
        f"Hi {customer_name},\n\n"
        f"Your quote from {shop} for job #{job_number} is {format_cents(total_cents, currency)}.{items_block}\n"
        f"Please review and accept here:\n{portal_url}\n\n"
        f"Reply to this email if you have any questions.\n\n"
        f"Thanks,\n{shop_name}"
    )
    body_html = render_transactional_email(
        title=f"Quote · Job #{job_number}",
        preheader=f"Your quote from {shop} is {format_cents(total_cents, currency)}",
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
        session=session,
        tenant_id=tenant_id,
    )


def send_shop_mobile_booking_email(
    *,
    to_email: str,
    shop_name: str,
    customer_name: str,
    customer_phone: str | None,
    job_address: str,
    accept_url: str,
    timeout_minutes: int,
    session: Session | None = None,
    tenant_id: UUID | None = None,
) -> tuple[bool, str | None]:
    """Email the assigned operator when a shop sends a live mobile booking request."""
    if not (to_email or "").strip():
        return False, None
    cust_line = customer_name.strip()
    if customer_phone and customer_phone.strip():
        cust_line += f" · {customer_phone.strip()}"
    shop = shop_name.strip() or "A shop"

    subject = f"Live booking from {shop} — accept within {timeout_minutes} min"
    body_plain = (
        f"{shop} sent a live mobile booking request.\n\n"
        f"Customer: {cust_line}\n"
        f"Address: {job_address.strip()}\n\n"
        f"Accept within {timeout_minutes} minutes or it opens to the shared Dispatch Pool "
        f"for any nearby operator to claim.\n\n"
        f"Accept & quote: {accept_url}\n"
    )
    intro_html = (
        f"<strong>{_html.escape(shop)}</strong> sent a live mobile booking request. "
        f"You have <strong>{timeout_minutes} minutes</strong> to accept before it opens to the shared "
        f"Dispatch Pool for any nearby operator to claim.<br><br>"
        f"<strong>Customer:</strong> {_html.escape(cust_line)}<br>"
        f"<strong>Address:</strong> {_html.escape(job_address.strip())}"
    )
    body_html = render_transactional_email(
        title="Live shop booking request",
        preheader=f"Accept within {timeout_minutes} min — {shop}",
        greeting="Live booking request",
        intro_html=intro_html,
        shop=ShopInfo(name="Mobile Services"),
        cta_label="Accept & quote",
        cta_url=accept_url,
    )
    return _send_email(
        to_email=to_email.strip(),
        subject=subject,
        body_plain=body_plain,
        body_html=body_html,
        shop_name="Mobile Services",
        event="shop_mobile_booking_pending",
        session=session,
        tenant_id=tenant_id,
    )


def send_pool_jobs_waiting_email(
    *,
    to_email: str,
    job_count: int,
    pool_url: str,
    session: Session | None = None,
    tenant_id: UUID | None = None,
) -> tuple[bool, str | None]:
    """One digest email per operator when jobs have sat unclaimed in the Dispatch Pool nearby."""
    if not (to_email or "").strip():
        return False, None
    plural = "job" if job_count == 1 else "jobs"
    subject = f"{job_count} {plural} waiting in the Dispatch Pool near you"
    body_plain = (
        f"{job_count} {plural} have been sitting unclaimed in the Dispatch Pool near you — "
        f"first operator to claim gets it.\n\n"
        f"Open the pool: {pool_url}\n"
    )
    body_html = render_transactional_email(
        title="Dispatch Pool",
        preheader=f"{job_count} {plural} waiting near you",
        greeting=f"{job_count} {plural} waiting near you",
        intro_html=(
            f"<strong>{job_count}</strong> {plural} have been sitting unclaimed in the Dispatch Pool "
            "near you — first operator to claim gets it."
        ),
        shop=ShopInfo(name="Mobile Services"),
        cta_label="Open the pool",
        cta_url=pool_url,
    )
    return _send_email(
        to_email=to_email.strip(),
        subject=subject,
        body_plain=body_plain,
        body_html=body_html,
        shop_name="Mobile Services",
        event="pool_jobs_waiting",
        session=session,
        tenant_id=tenant_id,
    )


def send_website_lead_alert_email(
    *,
    to_email: str,
    customer_name: str,
    customer_phone: str | None,
    suburb: str,
    state_code: str,
    vehicle_make: str | None,
    vehicle_model: str | None,
    registration_plate: str | None,
    inbox_url: str,
    session: Session | None = None,
    tenant_id: UUID | None = None,
) -> tuple[bool, str | None]:
    """Email the operator when a website enquiry lands in their Lead Inbox — an FYI, not a live offer."""
    if not (to_email or "").strip():
        return False, None
    cust_line = customer_name.strip()
    if customer_phone and customer_phone.strip():
        cust_line += f" · {customer_phone.strip()}"
    veh = " ".join(x for x in (vehicle_make or "", vehicle_model or "") if x and str(x).strip()).strip()
    if registration_plate and registration_plate.strip():
        veh = f"{veh} {registration_plate.strip()}".strip() if veh else registration_plate.strip()
    location = f"{suburb.strip()} {state_code.strip().upper()}"

    subject = f"New lead in your Lead Inbox ({location})"
    body_plain = (
        f"A new website enquiry has been added to your Lead Inbox.\n\n"
        f"Customer: {cust_line}\n"
        f"Location: {location}\n"
        + (f"Vehicle: {veh}\n" if veh else "")
        + f"\nWork it whenever suits — this one has no countdown.\n\n"
        f"Open Lead Inbox: {inbox_url}\n"
    )
    detail_lines = [f"<strong>Customer:</strong> {_html.escape(cust_line)}", f"<strong>Location:</strong> {_html.escape(location)}"]
    if veh:
        detail_lines.append(f"<strong>Vehicle:</strong> {_html.escape(veh)}")
    intro_html = (
        "A new website enquiry has been added to your Lead Inbox. No countdown on this one — "
        "work it whenever suits.<br><br>" + "<br>".join(detail_lines)
    )
    body_html = render_transactional_email(
        title="New lead in your Lead Inbox",
        preheader=f"{location} — no countdown, work it whenever suits",
        greeting="New lead in your Lead Inbox",
        intro_html=intro_html,
        shop=ShopInfo(name="Mobile Services"),
        cta_label="Open Lead Inbox",
        cta_url=inbox_url,
    )
    return _send_email(
        to_email=to_email.strip(),
        subject=subject,
        body_plain=body_plain,
        body_html=body_html,
        shop_name="Mobile Services",
        event="website_lead_alert",
        session=session,
        tenant_id=tenant_id,
    )


def send_shop_owner_invite_email(
    *,
    to_email: str,
    owner_full_name: str,
    tenant_name: str,
    shop_number: str | None,
    invite_url: str,
    expiry_days: int,
    session: Session | None = None,
    tenant_id: UUID | None = None,
) -> tuple[bool, str | None]:
    """Email a franchisee their one-time link to set up their own shop login."""
    if not (to_email or "").strip():
        return False, None
    shop_label = tenant_name.strip()
    if shop_number:
        shop_label += f" (#{shop_number})"

    subject = f"Set up your {shop_label} login"
    body_plain = (
        f"Hi {owner_full_name.strip() or 'there'},\n\n"
        f"Set up your own login for {shop_label} — this replaces the shared HQ login "
        f"you may have been using, with your own email and password.\n\n"
        f"Set up your login: {invite_url}\n\n"
        f"This link is one-time use and expires in {expiry_days} days. "
        f"If you weren't expecting this, contact Mister Minit HQ.\n"
    )
    intro_html = (
        f"Set up your own login for <strong>{_html.escape(shop_label)}</strong> — this replaces the "
        f"shared HQ login you may have been using, with your own email and password."
    )
    body_html = render_transactional_email(
        title=f"Set up your {shop_label} login",
        preheader=f"One-time link, expires in {expiry_days} days",
        greeting=f"Hi {owner_full_name.strip() or 'there'},",
        intro_html=intro_html,
        shop=ShopInfo(name="Mister Minit HQ"),
        cta_label="Set up your login",
        cta_url=invite_url,
    )
    return _send_email(
        to_email=to_email.strip(),
        subject=subject,
        body_plain=body_plain,
        body_html=body_html,
        shop_name="Mister Minit HQ",
        event="shop_owner_invite",
        session=session,
        tenant_id=tenant_id,
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
    session: Session | None = None,
    tenant_id: UUID | None = None,
) -> tuple[bool, str | None]:
    """Send email when a Mobile Services (auto key) invoice is sent."""
    if not (to_email or "").strip():
        return False, None
    view_url = f"{settings.public_base_url.rstrip('/')}/mobile-invoice/{customer_view_token}"
    items_block = _format_line_items(line_items or [], currency)
    if items_block:
        items_block = f"\n\nLine items:\n{items_block}\n"
    shop = shop_name.strip() or "us"
    subject = f"Invoice {invoice_number} from {shop} – Job #{job_number}"
    body_plain = (
        f"Hi {customer_name},\n\n"
        f"Your job #{job_number} with {shop} is complete. "
        f"Invoice {invoice_number} total: {format_cents(total_cents, currency)}.{items_block}\n"
        f"View your invoice and pay online (if available):\n{view_url}\n\n"
        f"Thank you for your business.\n\n"
        f"{shop_name}"
    )
    body_html = render_transactional_email(
        title=f"Invoice {invoice_number}",
        preheader=f"Invoice {invoice_number} from {shop} · {format_cents(total_cents, currency)}",
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
        session=session,
        tenant_id=tenant_id,
    )


def send_portal_bookmark_email(
    *,
    to_email: str,
    portal_url: str,
    expires_days: int = 30,
    shop_name: str = "Mainspring",
    session: Session | None = None,
    tenant_id: UUID | None = None,
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
        session=session,
        tenant_id=tenant_id,
    )


def send_portal_status_email(
    *,
    to_email: str,
    shop_name: str,
    job_label: str,
    old_status: str,
    new_status: str,
    status_url: str,
    session: Session | None = None,
    tenant_id: UUID | None = None,
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
        session=session,
        tenant_id=tenant_id,
    )


def send_job_ready_email(
    *,
    to_email: str,
    customer_name: str,
    job_number: str,
    status_token: str,
    shop_name: str = "Your repair shop",
    session: Session | None = None,
    tenant_id: UUID | None = None,
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
        session=session,
        tenant_id=tenant_id,
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
    session: Session | None = None,
    tenant_id: UUID | None = None,
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
        f"{format_cents(cat.get('revenue_cents', 0))} revenue"
        for key, cat in active_categories.items()
    ) or "  No sales recorded for this period."
    subject = f"{period_label} sales report – {period_start} to {period_end}"
    body_plain = (
        f"Hi,\n\n"
        f"Your {period_label.lower()} sales report for {period_start} to {period_end}:\n\n"
        f"{lines_plain}\n\n"
        f"Total revenue: {format_cents(total_revenue_cents)}\n\n"
        f"Full transaction-level detail is attached as a CSV.\n\n"
        f"— {shop_name}"
    )
    body_html = render_transactional_email(
        title=f"{period_label} sales report",
        preheader=f"{period_start} to {period_end} · {format_cents(total_revenue_cents)} revenue",
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
        session=session,
        tenant_id=tenant_id,
    )


def send_mobile_weekly_report_email(
    *,
    to_email: str,
    period_start: str,
    period_end: str,
    rows: list[dict],
    csv_bytes: bytes,
    csv_filename: str,
    session: Session | None = None,
    tenant_id: UUID | None = None,
) -> tuple[bool, str | None]:
    """Send the weekly Mobile Services network scorecard — one row per operator."""
    if not (to_email or "").strip():
        return False, None
    total_sales_cents = sum(int(r.get("sales_cents", 0)) for r in rows)
    total_jobs = sum(int(r.get("jobs_count", 0)) for r in rows)
    needs_attention = [r for r in rows if int(r.get("enquiries_not_actioned", 0)) > 0]

    line_items = [
        {
            "description": r.get("operator_name", "Operator"),
            "quantity": r.get("jobs_count", 0),
            "total_price_cents": r.get("sales_cents", 0),
        }
        for r in rows
    ]
    lines_plain = "\n".join(
        f"  • {r.get('operator_name', 'Operator')}: {r.get('jobs_count', 0)} jobs, "
        f"{format_cents(r.get('sales_cents', 0))} sales"
        + (f" — {r.get('enquiries_not_actioned')} enquiries not actioned" if r.get("enquiries_not_actioned") else "")
        for r in rows
    ) or "  No mobile operators to report on."
    attention_plain = (
        "\n\nNeeds attention (unactioned email enquiries): "
        + ", ".join(f"{r.get('operator_name')} ({r.get('enquiries_not_actioned')})" for r in needs_attention)
        if needs_attention
        else ""
    )
    subject = f"Mobile Services weekly report – {period_start} to {period_end}"
    body_plain = (
        f"Hi,\n\n"
        f"Mobile Services network report for {period_start} to {period_end}:\n\n"
        f"{lines_plain}\n\n"
        f"Total: {total_jobs} jobs, {format_cents(total_sales_cents)} sales across the network."
        f"{attention_plain}\n\n"
        f"Full detail is attached as a CSV.\n\n"
        f"— Mainspring"
    )
    note = "Full detail is attached as a CSV."
    if needs_attention:
        note += " " + ", ".join(
            f"{_html.escape(str(r.get('operator_name')))} has {r.get('enquiries_not_actioned')} enquiries not yet actioned"
            for r in needs_attention
        ) + "."
    body_html = render_transactional_email(
        title="Mobile Services weekly report",
        preheader=f"{period_start} to {period_end} · {total_jobs} jobs · {format_cents(total_sales_cents)}",
        greeting="Hi,",
        intro_html=(
            f"Here's the <strong>Mobile Services network report</strong> for "
            f"{_html.escape(period_start)} to {_html.escape(period_end)}."
        ),
        shop=ShopInfo(name="Mobile Services Network"),
        line_items=line_items,
        total_cents=total_sales_cents,
        currency="AUD",
        note_html=note,
    )
    return _send_email(
        to_email=to_email.strip(),
        subject=subject,
        body_plain=body_plain,
        body_html=body_html,
        shop_name="Mobile Services Network",
        event="mobile_weekly_report",
        attachment_bytes=csv_bytes,
        attachment_filename=csv_filename,
        attachment_mime_type="text/csv",
        session=session,
        tenant_id=tenant_id,
    )


def _payload_json(*, subject: str, body_plain: str, body_html: str | None, shop_name: str, reply_to: str | None) -> str:
    return json.dumps(
        {
            "subject": subject,
            "body_plain": body_plain,
            "body_html": body_html,
            "shop_name": shop_name,
            "reply_to": reply_to,
        }
    )


def _is_sqlite() -> bool:
    return engine.dialect.name == "sqlite"


def _begin_email_log(session: Session | None, **kwargs):
    row = EmailLog(**kwargs)
    if session is None or not _is_sqlite():
        with Session(engine) as log_session:
            log_session.add(row)
            log_session.commit()
            log_session.refresh(row)
            return row.id
    session.add(row)
    session.flush()
    return row.id


def _finish_email_log(session: Session | None, log_id, **fields) -> None:
    from datetime import datetime, timezone

    if session is not None and _is_sqlite():
        row = session.get(EmailLog, log_id)
        if row is None:
            return
        for key, value in fields.items():
            setattr(row, key, value)
        if "last_attempt_at" not in fields:
            row.last_attempt_at = datetime.now(timezone.utc)
        session.add(row)
        return
    with Session(engine) as log_session:
        row = log_session.get(EmailLog, log_id)
        if row is None:
            return
        for key, value in fields.items():
            setattr(row, key, value)
        if "last_attempt_at" not in fields:
            row.last_attempt_at = datetime.now(timezone.utc)
        log_session.add(row)
        log_session.commit()


def send_email_from_payload(
    *,
    to_email: str,
    event: str,
    payload: dict,
    session: Session | None = None,
    tenant_id: UUID | None = None,
    existing_log_id=None,
) -> tuple[bool, str | None]:
    """Redeliver a previously recorded email from its stored payload (no attachments)."""
    return _send_email(
        to_email=to_email,
        subject=str(payload.get("subject") or event),
        body_plain=str(payload.get("body_plain") or ""),
        body_html=payload.get("body_html"),
        shop_name=str(payload.get("shop_name") or "Mainspring"),
        event=event,
        reply_to=payload.get("reply_to"),
        session=session,
        tenant_id=tenant_id,
        existing_log_id=existing_log_id,
    )


def send_vswt_management_report_email(
    *,
    to_email: str,
    shop_name: str,
    week: int,
    sales: float | None,
    sales_delta_pct: float | None,
    customers: float | None,
    jobs: float | None,
    sales_rank: int | None,
    region_size: int,
    alerts: list[dict],
    csv_bytes: bytes,
    csv_filename: str,
) -> tuple[bool, str | None]:
    """Send the Regional Reports comparison cockpit as a weekly management email."""
    if not (to_email or "").strip():
        return False, None
    sales_text = f"${sales:,.2f}" if sales is not None else "Unavailable"
    movement = (
        f" ({sales_delta_pct * 100:+.1f}% vs previous week)"
        if sales_delta_pct is not None
        else ""
    )
    rank_text = f"#{sales_rank} of {region_size}" if sales_rank is not None else "Unavailable"
    alert_lines = "\n".join(f"  • {a.get('title')}: {a.get('message')}" for a in alerts[:5]) or "  No material exceptions."
    body_plain = (
        f"Hi,\n\nRegional performance report for {shop_name}, week {week}.\n\n"
        f"Sales: {sales_text}{movement}\nCustomers: {customers if customers is not None else 'Unavailable'}\n"
        f"Jobs: {jobs if jobs is not None else 'Unavailable'}\nRegional sales rank: {rank_text}\n\n"
        f"Performance signals:\n{alert_lines}\n\nThe full comparison table is attached as a CSV.\n\n— Mainspring"
    )
    note_html = "<br>".join(
        f"<strong>{_html.escape(str(a.get('title', 'Signal')))}</strong>: {_html.escape(str(a.get('message', '')))}"
        for a in alerts[:5]
    ) or "No material exceptions were detected."
    line_items = [
        {
            "description": f"Week {week} sales",
            "quantity": 1,
            "total_price_cents": round((sales or 0) * 100),
        }
    ]
    body_html = render_transactional_email(
        title="Weekly regional performance report",
        preheader=f"Week {week} · {sales_text} sales · rank {rank_text}",
        greeting="Hi,",
        intro_html=(
            f"Here's the regional performance summary for <strong>{_html.escape(shop_name)}</strong>. "
            f"Customers: <strong>{customers if customers is not None else '—'}</strong>. "
            f"Jobs: <strong>{jobs if jobs is not None else '—'}</strong>. "
            f"Sales rank: <strong>{_html.escape(rank_text)}</strong>."
        ),
        shop=ShopInfo(name=shop_name),
        line_items=line_items,
        total_cents=round((sales or 0) * 100),
        currency="AUD",
        note_html=note_html + "<br><br>Full KPI comparison detail is attached as a CSV.",
    )
    return _send_email(
        to_email=to_email.strip(),
        subject=f"Regional performance report – Week {week}",
        body_plain=body_plain,
        body_html=body_html,
        shop_name=shop_name,
        event="vswt_weekly_report",
        attachment_bytes=csv_bytes,
        attachment_filename=csv_filename,
        attachment_mime_type="text/csv",
    )


def send_region_manager_report_email(
    *,
    to_email: str,
    manager_name: str | None,
    region_name: str,
    week: int,
    sales: float | None,
    sales_delta_pct: float | None,
    customers: float | None,
    region_rank: int | None,
    region_count: int,
    shops_reported: int,
    shop_count: int,
    narrative: str,
    movers_up: list[dict],
    movers_down: list[dict],
    alerts: list[dict],
    attainment: dict,
    csv_bytes: bytes,
    csv_filename: str,
) -> tuple[bool, str | None]:
    """The regional manager's Monday email: the region's week, who moved, what needs a call."""
    if not (to_email or "").strip():
        return False, None
    sales_text = f"${sales:,.0f}" if sales is not None else "Unavailable"
    movement = f" ({sales_delta_pct * 100:+.1f}% vs previous week)" if sales_delta_pct is not None else ""
    rank_text = f"#{region_rank} of {region_count} regions" if region_rank is not None else "Unranked"
    greeting = f"Hi {manager_name.split()[0]}," if (manager_name or "").strip() else "Hi,"

    def _mover_line(r: dict) -> str:
        pct = f"{r['delta_pct'] * 100:+.1f}%" if r.get("delta_pct") is not None else "—"
        delta = f" (${r['delta']:+,.0f})" if r.get("delta") is not None else ""
        return f"{r['shop_name']} (#{r['shop_number']}): {pct}{delta}"

    up_lines = "\n".join(f"  ↑ {_mover_line(r)}" for r in movers_up[:5]) or "  none"
    down_lines = "\n".join(f"  ↓ {_mover_line(r)}" for r in movers_down[:5]) or "  none"
    alert_lines = "\n".join(f"  • {a.get('title')}: {a.get('message')}" for a in alerts[:6]) or "  No material exceptions."
    attain_text = (
        f"{attainment.get('shops_met', 0)} of {attainment.get('shops_with_target', 0)} shops with a sales target met it"
        if attainment.get("shops_with_target")
        else "No sales targets set for this region yet"
    )
    body_plain = (
        f"{greeting}\n\n{region_name} — week {week}.\n\n{narrative}\n\n"
        f"Sales: {sales_text}{movement}\nCustomers: {f'{customers:,.0f}' if customers is not None else 'Unavailable'}\n"
        f"Rank: {rank_text}\nShops reported: {shops_reported} of {shop_count}\nTargets: {attain_text}\n\n"
        f"Moved up most:\n{up_lines}\n\nMoved down most:\n{down_lines}\n\n"
        f"Needs a call:\n{alert_lines}\n\nEvery shop's week is attached as a CSV.\n\n— Mainspring"
    )

    def _mover_html(r: dict, arrow: str) -> str:
        pct = f"{r['delta_pct'] * 100:+.1f}%" if r.get("delta_pct") is not None else "—"
        delta = f" (${r['delta']:+,.0f})" if r.get("delta") is not None else ""
        return f"{arrow} <strong>{_html.escape(str(r['shop_name']))}</strong> {_html.escape(pct)}{_html.escape(delta)}"

    note_html = (
        f"<p>{_html.escape(narrative)}</p>"
        f"<p><strong>Moved up most</strong><br>{'<br>'.join(_mover_html(r, '↑') for r in movers_up[:5]) or 'none'}</p>"
        f"<p><strong>Moved down most</strong><br>{'<br>'.join(_mover_html(r, '↓') for r in movers_down[:5]) or 'none'}</p>"
        f"<p><strong>Needs a call</strong><br>"
        + ("<br>".join(
            f"<strong>{_html.escape(str(a.get('title', 'Signal')))}</strong>: {_html.escape(str(a.get('message', '')))}"
            for a in alerts[:6]
        ) or "No material exceptions.")
        + f"</p><p>{_html.escape(attain_text)}.</p>"
    )
    body_html = render_transactional_email(
        title=f"{region_name}: week {week}",
        preheader=f"{sales_text} sales{movement} · {rank_text}",
        greeting=greeting,
        intro_html=(
            f"Here is <strong>{_html.escape(region_name)}</strong>'s week. "
            f"Sales <strong>{_html.escape(sales_text)}</strong>{_html.escape(movement)}. "
            f"Rank <strong>{_html.escape(rank_text)}</strong>. "
            f"{shops_reported} of {shop_count} shops reported."
        ),
        shop=ShopInfo(name=region_name),
        line_items=[{"description": f"Week {week} region sales", "quantity": 1, "total_price_cents": round((sales or 0) * 100)}],
        total_cents=round((sales or 0) * 100),
        currency="AUD",
        note_html=note_html + "<br>Every shop's week is attached as a CSV.",
    )
    return _send_email(
        to_email=to_email.strip(),
        subject=f"{region_name} — week {week} regional report",
        body_plain=body_plain,
        body_html=body_html,
        shop_name=region_name,
        event="region_manager_weekly_report",
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
    session: Session | None = None,
    tenant_id: UUID | None = None,
    existing_log_id=None,
) -> tuple[bool, str | None]:
    """Send via SendGrid. When `session` + `tenant_id` are given (or an existing log
    id), the attempt is persisted to EmailLog *before* the provider call so a later
    commit failure leaves a spurious row rather than a silent send.
    """
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    log_id = existing_log_id
    payload_blob = _payload_json(
        subject=subject,
        body_plain=body_plain,
        body_html=body_html,
        shop_name=shop_name,
        reply_to=reply_to,
    )
    if log_id is None and session is not None and tenant_id is not None:
        log_id = _begin_email_log(
            session,
            tenant_id=tenant_id,
            to_email=to_email,
            event=event,
            status="failed",
            error=None,
            attempt_count=0,
            last_attempt_at=now,
            payload_json=payload_blob,
        )

    def _finish(ok: bool, status: str, error: str | None, attempts: int, *, permanent: bool = False) -> tuple[bool, str | None]:
        if log_id is not None:
            _finish_email_log(
                session,
                log_id,
                status=status,
                error=(error or None) and str(error)[:500],
                attempt_count=pin_attempts_if_permanent(attempts, permanent=permanent),
                last_attempt_at=datetime.now(timezone.utc),
                payload_json=payload_blob,
            )
        return ok, error

    from_addr = _from_email()
    if not _enabled():
        logger.info("email (disabled) %s to %s: %s", event, to_email, subject)
        return _finish(False, "dry_run", None, 0)
    key = _api_key()
    if not key:
        logger.info("email (dry-run, no SENDGRID_API_KEY) %s to %s: %s", event, to_email, subject)
        return _finish(False, "dry_run", None, 0)
    # text/plain must precede text/html per RFC / SendGrid ordering rules.
    content: list[dict] = [{"type": "text/plain", "value": body_plain}]
    if body_html:
        content.append({"type": "text/html", "value": body_html})
    payload: dict = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": from_addr, "name": _from_name(shop_name)},
        "subject": subject,
        "content": content,
        "categories": [event],
        # Click tracking rewrites every link through the SendGrid link-branding
        # domain (urlNNNN.<domain>), which has no TLS cert → browsers show
        # NET::ERR_CERT_COMMON_NAME_INVALID. These are transactional emails
        # carrying invite/reset/approval tokens, so links must go out untouched.
        "tracking_settings": {
            "click_tracking": {"enable": False, "enable_text": False},
        },
    }
    reply = (reply_to or "").strip()
    if reply and "@" in reply and reply.lower() != from_addr.lower():
        payload["reply_to"] = {"email": reply, "name": _from_name(shop_name)}
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

    max_attempts = inline_retry_attempts()
    last_error: str | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    json=payload,
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                )
            if 200 <= resp.status_code < 300:
                logger.info("Twilio SendGrid sent %s to %s from %s", event, to_email, from_addr)
                return _finish(True, "sent", None, attempt)
            detail = (resp.text or "").strip()[:400]
            err = f"SendGrid HTTP {resp.status_code} (from={from_addr})"
            if detail:
                err = f"{err}: {detail}"
            last_error = err
            if 400 <= resp.status_code < 500:
                logger.warning("Twilio SendGrid %s failed for %s: %s", event, to_email, err)
                return _finish(False, "failed", err, attempt, permanent=True)
            if attempt < max_attempts and is_retryable_http_status(resp.status_code):
                time.sleep(backoff_seconds(attempt - 1))
                continue
            logger.warning("Twilio SendGrid %s failed for %s: %s", event, to_email, err)
            return _finish(False, "failed", err, attempt)
        except Exception as e:
            last_error = str(e)[:400]
            retryable = is_timeout_exc(e) or is_transport_exc(e)
            status = http_status_from_exc(e)
            if status is not None and 400 <= status < 500:
                logger.warning("Twilio SendGrid %s failed for %s: %s", event, to_email, e)
                return _finish(False, "failed", last_error, attempt, permanent=True)
            if retryable and attempt < max_attempts:
                time.sleep(backoff_seconds(attempt - 1))
                continue
            logger.exception("Twilio SendGrid %s failed for %s: %s", event, to_email, e)
            return _finish(False, "failed", last_error, attempt)
    return _finish(False, "failed", last_error, max_attempts)
