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
    Shoe,
    ShoeRepairJob,
    ShoeRepairJobItem,
    TenantEventLog,
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
    summary = {"watch_sent": 0, "mobile_sent": 0, "shoe_sent": 0, "skipped": 0}

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
        if not customer or not ((customer.phone or "").strip() or (customer.email or "").strip()):
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

        if (customer.phone or "").strip():
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
        else:
            # Email-only customer: the same quote email again, so they are not left out.
            from ..email_client import send_quote_sent_email

            send_quote_sent_email(
                to_email=customer.email.strip(),
                customer_name=customer.full_name or "there",
                total_cents=quote.total_cents,
                approval_token=quote.approval_token,
                job_number=job.job_number,
                shop_name=_shop_name(session, shop_names, quote.tenant_id),
                session=session,
                tenant_id=quote.tenant_id,
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

    # ── Shoe repair quotes ───────────────────────────────────────────────────
    # Shoe jobs do not store when the quote went out; the link expiry is that moment
    # plus the TTL, so work backwards. One reminder per job, recorded in the inbox log.
    ttl = timedelta(hours=max(settings.quote_approval_token_ttl_hours, 1))
    shoe_query = (
        select(ShoeRepairJob)
        .where(ShoeRepairJob.quote_status == "sent")
        .where(ShoeRepairJob.quote_approval_token_expires_at.isnot(None))
        .where(ShoeRepairJob.status.in_(("awaiting_quote", "awaiting_go_ahead")))
    )
    if tenant_id:
        shoe_query = shoe_query.where(ShoeRepairJob.tenant_id == tenant_id)
    for job in session.exec(shoe_query).all():
        expires = _as_utc(job.quote_approval_token_expires_at)
        sent_at = expires - ttl if expires else None
        if not sent_at or sent_at > cutoff or sent_at < now - timedelta(days=30):
            continue
        already = session.exec(
            select(TenantEventLog.id)
            .where(TenantEventLog.entity_id == job.id)
            .where(TenantEventLog.event_type == "shoe_quote_reminder_sent")
        ).first()
        if already:
            continue
        shoe = session.get(Shoe, job.shoe_id)
        customer = session.get(Customer, shoe.customer_id) if shoe else None
        phone = ((customer.phone if customer else "") or "").strip()
        email = ((customer.email if customer else "") or "").strip()
        if not customer or not (phone or email):
            summary["skipped"] += 1
            continue
        total_cents = int(sum(
            (i.unit_price_cents or 0) * i.quantity
            for i in session.exec(select(ShoeRepairJobItem).where(ShoeRepairJobItem.shoe_repair_job_id == job.id)).all()
        ))
        shop = _shop_name(session, shop_names, job.tenant_id)
        job.quote_approval_token_expires_at = now + ttl
        session.add(job)
        if phone:
            sms.notify_shoe_quote_reminder(
                session,
                tenant_id=job.tenant_id,
                shoe_repair_job_id=job.id,
                customer_name=customer.full_name or "there",
                to_phone=phone,
                total_cents=total_cents,
                approval_token=job.quote_approval_token,
                job_number=job.job_number,
                shop_name=shop,
            )
        if email:
            from ..email_client import send_shoe_quote_email

            send_shoe_quote_email(
                to_email=email,
                customer_name=customer.full_name or "there",
                total_cents=total_cents,
                approval_token=job.quote_approval_token,
                job_number=job.job_number,
                shop_name=shop,
                reminder=True,
                session=session,
                tenant_id=job.tenant_id,
            )
        session.add(TenantEventLog(
            tenant_id=job.tenant_id,
            entity_type="shoe_repair_job",
            entity_id=job.id,
            event_type="shoe_quote_reminder_sent",
            event_summary=f"Reminder sent for shoe quote on job #{job.job_number}",
        ))
        summary["shoe_sent"] += 1

    session.commit()
    return summary
