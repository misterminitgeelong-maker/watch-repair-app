"""Reminder SMS for quotes that haven't been given a go-ahead.

Watch repair quote links expire after QUOTE_APPROVAL_TOKEN_TTL_HOURS, so the
reminder also refreshes the token expiry — the link in the reminder text works
for another full window. Mobile services (auto key) quote links don't expire,
so those just get the nudge. One reminder per quote, QUOTE_REMINDER_DAYS after
it was sent, only while the job is still waiting on the customer.
"""
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlmodel import Session, select

from .. import sms
from ..config import settings
from ..models import (
    AutoKeyJob,
    AutoKeyQuote,
    Customer,
    Quote,
    Tenant,
    Watch,
)
from ..tenant_helpers import get_tenant_repair_job

logger = logging.getLogger(__name__)


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _shop_name(session: Session, cache: dict[UUID, str], tenant_id: UUID) -> str:
    if tenant_id not in cache:
        tenant = session.get(Tenant, tenant_id)
        cache[tenant_id] = (tenant.name if tenant else None) or "your repair shop"
    return cache[tenant_id]


def send_due_quote_reminders(session: Session, tenant_id: UUID | None = None) -> dict[str, int]:
    """Send reminder SMS for all due, undecided quotes. Caller-agnostic: used by
    the in-app scheduler (all tenants) and the manual endpoint (one tenant)."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max(settings.quote_reminder_days, 1))
    shop_names: dict[UUID, str] = {}
    summary = {"watch_sent": 0, "mobile_sent": 0, "skipped": 0}

    # ── Watch repair quotes ──────────────────────────────────────────────────
    query = (
        select(Quote)
        .where(Quote.status.in_(("sent", "expired")))
        .where(Quote.reminder_sent_at.is_(None))
        .where(Quote.sent_at.isnot(None))
    )
    if tenant_id:
        query = query.where(Quote.tenant_id == tenant_id)
    for quote in session.exec(query).all():
        sent_at = _as_utc(quote.sent_at)
        if not sent_at or sent_at > cutoff:
            continue

        job = get_tenant_repair_job(session, quote.repair_job_id, quote.tenant_id)
        if not job or job.status != "awaiting_go_ahead":
            # Decided some other way (or cancelled) — never remind.
            quote.reminder_sent_at = now
            session.add(quote)
            summary["skipped"] += 1
            continue

        watch = session.get(Watch, job.watch_id)
        customer = session.get(Customer, watch.customer_id) if watch else None
        if not customer or not (customer.phone or "").strip():
            quote.reminder_sent_at = now
            session.add(quote)
            summary["skipped"] += 1
            continue

        # Refresh the approval link so the reminder doesn't point at a dead page.
        quote.approval_token_expires_at = now + timedelta(hours=max(settings.quote_approval_token_ttl_hours, 1))
        if quote.status == "expired":
            quote.status = "sent"
        quote.reminder_sent_at = now
        session.add(quote)

        sms.notify_quote_reminder(
            session,
            tenant_id=quote.tenant_id,
            repair_job_id=job.id,
            customer_name=customer.full_name,
            to_phone=customer.phone.strip(),
            total_cents=quote.total_cents,
            approval_token=quote.approval_token,
            job_number=job.job_number,
            shop_name=_shop_name(session, shop_names, quote.tenant_id),
        )
        summary["watch_sent"] += 1

    # ── Mobile services (auto key) quotes ────────────────────────────────────
    ak_query = (
        select(AutoKeyQuote)
        .where(AutoKeyQuote.status == "sent")
        .where(AutoKeyQuote.reminder_sent_at.is_(None))
        .where(AutoKeyQuote.sent_at.isnot(None))
    )
    if tenant_id:
        ak_query = ak_query.where(AutoKeyQuote.tenant_id == tenant_id)
    for quote in session.exec(ak_query).all():
        sent_at = _as_utc(quote.sent_at)
        if not sent_at or sent_at > cutoff:
            continue

        job = session.get(AutoKeyJob, quote.auto_key_job_id)
        if not job or job.tenant_id != quote.tenant_id or job.status != "quote_sent":
            quote.reminder_sent_at = now
            session.add(quote)
            summary["skipped"] += 1
            continue

        customer = session.get(Customer, job.customer_id)
        if not customer or not (customer.phone or "").strip():
            quote.reminder_sent_at = now
            session.add(quote)
            summary["skipped"] += 1
            continue

        quote.reminder_sent_at = now
        session.add(quote)

        first_name = ((customer.full_name or "").strip().split() or ["there"])[0]
        sms.notify_auto_key_quote_reminder(
            session,
            tenant_id=quote.tenant_id,
            auto_key_job_id=job.id,
            to_phone=customer.phone.strip(),
            customer_name=first_name,
            shop_name=_shop_name(session, shop_names, quote.tenant_id),
            job_number=job.job_number,
            total_cents=quote.total_cents,
            currency=quote.currency or "AUD",
            quote_approval_token=quote.quote_approval_token,
        )
        summary["mobile_sent"] += 1

    session.commit()
    return summary
