"""
Optional email notifications (quote sent, job ready).
When enable_email_notifications is True, uses SendGrid or Postmark if API key is set;
otherwise logs only (dry-run).
"""
import logging
from .config import settings

logger = logging.getLogger(__name__)


def _enabled() -> bool:
    return getattr(settings, "enable_email_notifications", False)


def send_quote_sent_email(
    *,
    to_email: str,
    customer_name: str,
    total_cents: int,
    approval_token: str,
    job_number: str,
) -> None:
    """Send email when a quote is sent to the customer."""
    if not _enabled() or not (to_email or "").strip():
        return
    approval_url = f"{settings.public_base_url}/approve/{approval_token}"
    total = total_cents / 100
    subject = f"Your watch repair quote – Job #{job_number}"
    body_plain = (
        f"Hi {customer_name},\n\n"
        f"Your watch repair quote for job #{job_number} is ${total:.2f}. "
        f"Reply YES to approve or NO to decline, or open this link to view details:\n{approval_url}\n\n"
        "Thanks,\nYour watch repair shop"
    )
    if getattr(settings, "sendgrid_api_key", "").strip():
        _send_via_sendgrid(to_email=to_email.strip(), subject=subject, body_plain=body_plain)
    elif getattr(settings, "postmark_api_key", "").strip():
        _send_via_postmark(to_email=to_email.strip(), subject=subject, body_plain=body_plain)
    else:
        logger.info("email (dry-run) quote_sent to %s: %s", to_email, subject)


def send_job_ready_email(
    *,
    to_email: str,
    customer_name: str,
    job_number: str,
    status_token: str,
) -> None:
    """Send email when a job is ready for collection (completed / awaiting_collection)."""
    if not _enabled() or not (to_email or "").strip():
        return
    status_url = f"{settings.public_base_url}/status/{status_token}"
    subject = f"Your watch is ready for collection – Job #{job_number}"
    body_plain = (
        f"Hi {customer_name},\n\n"
        f"Your watch (job #{job_number}) is ready for collection. "
        f"Check status: {status_url}\n\n"
        "Thanks,\nYour watch repair shop"
    )
    if getattr(settings, "sendgrid_api_key", "").strip():
        _send_via_sendgrid(to_email=to_email.strip(), subject=subject, body_plain=body_plain)
    elif getattr(settings, "postmark_api_key", "").strip():
        _send_via_postmark(to_email=to_email.strip(), subject=subject, body_plain=body_plain)
    else:
        logger.info("email (dry-run) job_ready to %s: %s", to_email, subject)


def _send_via_sendgrid(to_email: str, subject: str, body_plain: str) -> None:
    """Send a single email via SendGrid API (minimal implementation)."""
    key = (getattr(settings, "sendgrid_api_key", "") or "").strip()
    if not key:
        return
    try:
        import urllib.request
        import json
        req = urllib.request.Request(
            "https://api.sendgrid.com/v3/mail/send",
            data=json.dumps({
                "personalizations": [{"to": [{"email": to_email}]}],
                "from": {"email": "noreply@mainspring.au", "name": "Watch Repair"},
                "subject": subject,
                "content": [{"type": "text/plain", "value": body_plain}],
            }).encode("utf-8"),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if 200 <= resp.status < 300:
                logger.info("SendGrid sent quote_sent/job_ready to %s", to_email)
            else:
                logger.warning("SendGrid returned %s for %s", resp.status, to_email)
    except Exception as e:
        logger.exception("SendGrid send failed for %s: %s", to_email, e)


def _send_via_postmark(to_email: str, subject: str, body_plain: str) -> None:
    """Send a single email via Postmark API (minimal implementation)."""
    key = (getattr(settings, "postmark_api_key", "") or "").strip()
    if not key:
        return
    try:
        import urllib.request
        import json
        req = urllib.request.Request(
            "https://api.postmarkapp.com/email",
            data=json.dumps({
                "From": "noreply@mainspring.au",
                "To": to_email,
                "Subject": subject,
                "TextBody": body_plain,
            }).encode("utf-8"),
            headers={"X-Postmark-Server-Token": key, "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                logger.info("Postmark sent quote_sent/job_ready to %s", to_email)
            else:
                logger.warning("Postmark returned %s for %s", resp.status, to_email)
    except Exception as e:
        logger.exception("Postmark send failed for %s: %s", to_email, e)
