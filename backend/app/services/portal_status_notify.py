"""Notify portal customers when job status changes (email/SMS per session prefs)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlmodel import Session, select

from ..config import settings
from ..email_client import send_portal_status_email
from ..models import AutoKeyJob, Customer, PortalSession, RepairJob, Shoe, ShoeRepairJob, Tenant, Watch
from .. import sms

logger = logging.getLogger(__name__)


def notify_portal_status_change(
    session: Session,
    *,
    tenant_id: UUID,
    customer_email: str | None,
    job_number: str,
    job_title: str,
    old_status: str,
    new_status: str,
    status_url: str,
    shop_name: str,
) -> None:
    email = (customer_email or "").strip().lower()
    if not email:
        return

    now = datetime.now(timezone.utc)
    portals = session.exec(select(PortalSession).where(PortalSession.email.ilike(email))).all()  # type: ignore[attr-defined]
    active = [
        p for p in portals
        if (p.expires_at.replace(tzinfo=timezone.utc) if p.expires_at.tzinfo is None else p.expires_at) > now
    ]
    if not active:
        return

    notify_email = any(p.status_notify_email for p in active)
    notify_sms = any(p.status_notify_sms for p in active)
    if not notify_email and not notify_sms:
        return

    label = f"{job_number}: {job_title}"
    summary = f"Status updated to {new_status.replace('_', ' ')}"

    if notify_email:
        try:
            send_portal_status_email(
                to_email=email,
                shop_name=shop_name,
                job_label=label,
                old_status=old_status,
                new_status=new_status,
                status_url=status_url,
            )
        except Exception:
            logger.exception("portal status email failed email=%s job=%s", email, job_number)

    if notify_sms:
        customer = session.exec(
            select(Customer)
            .where(Customer.tenant_id == tenant_id)
            .where(Customer.email.ilike(email))  # type: ignore[attr-defined]
        ).first()
        if customer and customer.phone:
            body = f"{shop_name}: {summary}. Track: {status_url}"
            sid = sms._send_sms(customer.phone, body)  # noqa: SLF001
            sms._persist(  # noqa: SLF001
                session,
                tenant_id=tenant_id,
                repair_job_id=None,
                to_phone=customer.phone,
                body=body,
                event="portal_status",
                provider_sid=sid,
                status="sent" if sid else "dry_run",
            )


def notify_repair_job_status(session: Session, job: RepairJob, old_status: str, shop_name: str) -> None:
    watch = session.get(Watch, job.watch_id) if job.watch_id else None
    customer = session.get(Customer, watch.customer_id) if watch else None
    status_url = f"{settings.public_base_url.rstrip('/')}/status/{job.status_token}"
    notify_portal_status_change(
        session,
        tenant_id=job.tenant_id,
        customer_email=customer.email if customer else None,
        job_number=job.job_number,
        job_title=job.title,
        old_status=old_status,
        new_status=job.status,
        status_url=status_url,
        shop_name=shop_name,
    )


def notify_shoe_job_status(session: Session, job: ShoeRepairJob, old_status: str, shop_name: str) -> None:
    shoe = session.get(Shoe, job.shoe_id)
    customer = session.get(Customer, shoe.customer_id) if shoe else None
    status_url = f"{settings.public_base_url.rstrip('/')}/shoe-status/{job.status_token}"
    notify_portal_status_change(
        session,
        tenant_id=job.tenant_id,
        customer_email=customer.email if customer else None,
        job_number=job.job_number,
        job_title=job.title,
        old_status=old_status,
        new_status=job.status,
        status_url=status_url,
        shop_name=shop_name,
    )


def notify_auto_key_job_status(session: Session, job: AutoKeyJob, old_status: str, shop_name: str) -> None:
    customer = session.get(Customer, job.customer_id) if job.customer_id else None
    status_url = f"{settings.public_base_url.rstrip('/')}/customer-portal/job/auto_key/{job.status_token}"
    notify_portal_status_change(
        session,
        tenant_id=job.tenant_id,
        customer_email=customer.email if customer else None,
        job_number=job.job_number,
        job_title=job.title,
        old_status=old_status,
        new_status=job.status,
        status_url=status_url,
        shop_name=shop_name,
    )


def shop_name_for(session: Session, tenant_id: UUID) -> str:
    tenant = session.get(Tenant, tenant_id)
    return (tenant.name if tenant else None) or "Your repair shop"
