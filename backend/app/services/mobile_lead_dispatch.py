"""Website lead routing: an async enquiry (not a live lead) → one operator's Lead Inbox.

No timer, no cascade, no auto-created job — see routes/shop_mobile_bookings.py for the
live, timed "book mobile now" flow this is deliberately simpler than.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlmodel import Session, func, select

from ..config import settings
from ..minit_mobile_routing import rank_mobile_operator_candidates, suburb_in_operator_territory
from ..minit_provision import _is_operator_plan
from ..models import AutoKeyJob, ParentAccount, ParentAccountEventLog, ProspectLead, Tenant
from .. import email_client
from .. import sms as sms_service

logger = logging.getLogger(__name__)


def lead_payload_from_body(body: Any) -> dict[str, Any]:
    """Serialize ingest body to JSON-safe dict."""
    if hasattr(body, "model_dump"):
        return body.model_dump()
    return dict(body)


def _next_auto_key_job_number(session: Session, tenant_id: UUID) -> str:
    """Shared by routes/inbound_email.py when HQ manually turns a captured email into a job."""
    count = session.exec(select(func.count()).select_from(AutoKeyJob).where(AutoKeyJob.tenant_id == tenant_id)).one()
    return f"AK-{int(count) + 1:05d}"


def _escalation_tenant_id(session: Session, parent: ParentAccount) -> UUID | None:
    if parent.mobile_lead_escalation_tenant_id:
        return parent.mobile_lead_escalation_tenant_id
    fallback = parent.mobile_lead_default_tenant_id
    if not fallback:
        return None
    tenant = session.get(Tenant, fallback)
    if tenant and not _is_operator_plan(tenant.plan_code):
        return fallback
    return None


def route_website_lead_to_prospect(
    session: Session,
    *,
    parent: ParentAccount,
    payload: dict[str, Any],
    suburb: str,
    state_code: str,
) -> ProspectLead:
    """Website enquiry (an email, not a live lead): route to one operator's Lead Inbox and
    send a one-time SMS + email alert. No timer, no cascade, no job — unlike a live shop
    booking, the operator works it from Lead Inbox at their own pace.
    """
    st = state_code.strip().upper()
    force_hq = bool(parent.mobile_lead_force_hq_dispatch)
    in_territory = False if force_hq else suburb_in_operator_territory(
        session,
        parent_id=parent.id,
        suburb=suburb,
        state_code=st,
    )
    tenant_id: UUID | None = None
    if in_territory:
        candidates = rank_mobile_operator_candidates(
            session, parent_id=parent.id, suburb=suburb, state_code=st, max_candidates=1,
        )
        tenant_id = candidates[0] if candidates else None
    if not tenant_id:
        tenant_id = _escalation_tenant_id(session, parent)
    if not tenant_id:
        raise ValueError("no_operator_or_escalation_configured")

    customer_name = str(payload.get("customer_name") or "Website lead").strip()[:300]
    vehicle_bits = [payload.get("vehicle_make"), payload.get("vehicle_model"), payload.get("registration_plate")]
    veh = " ".join(str(x).strip() for x in vehicle_bits if x and str(x).strip())
    notes_parts = ["Submitted via website lead feed."]
    if veh:
        notes_parts.append(f"Vehicle: {veh}")
    if payload.get("key_service_result"):
        notes_parts.append(f"Key checker result: {str(payload['key_service_result']).strip()}")
    if payload.get("website_notes"):
        notes_parts.append(str(payload["website_notes"]).strip())

    lead = ProspectLead(
        tenant_id=tenant_id,
        name=customer_name,
        phone=str(payload.get("phone")).strip()[:80] if payload.get("phone") else None,
        contact_email=str(payload.get("email")).strip().lower()[:320] if payload.get("email") else None,
        suburb_name=suburb.strip()[:200],
        state_code=st[:8],
        notes="\n\n".join(notes_parts)[:4000],
        status="new",
        source="website_lead",
    )
    session.add(lead)
    session.flush()

    tenant = session.get(Tenant, tenant_id)
    if tenant:
        inbox_url = f"{settings.public_base_url.rstrip('/')}/auto-key/prospects/inbox"
        phone = sms_service.operator_dispatch_phone(tenant)
        if phone:
            sms_service.notify_website_lead_alert(
                session,
                tenant_id=tenant_id,
                to_phone=phone,
                customer_name=customer_name,
                customer_phone=payload.get("phone"),
                suburb=suburb,
                state_code=st,
                vehicle_make=payload.get("vehicle_make"),
                vehicle_model=payload.get("vehicle_model"),
                registration_plate=payload.get("registration_plate"),
                inbox_url=inbox_url,
            )
        email = sms_service.operator_dispatch_email(session, tenant)
        if email:
            ok, err = email_client.send_website_lead_alert_email(
                to_email=email,
                customer_name=customer_name,
                customer_phone=payload.get("phone"),
                suburb=suburb,
                state_code=st,
                vehicle_make=payload.get("vehicle_make"),
                vehicle_model=payload.get("vehicle_model"),
                registration_plate=payload.get("registration_plate"),
                inbox_url=inbox_url,
            )
            if not ok and err:
                logger.info("mobile_lead_dispatch.website_lead_email_failed tenant=%s err=%s", tenant_id, err)

    session.add(
        ParentAccountEventLog(
            parent_account_id=parent.id,
            tenant_id=tenant_id,
            actor_email="website-lead@ingest",
            event_type="website_lead_routed",
            event_summary=f"Website lead routed to Lead Inbox ({customer_name}, {suburb.strip()} {st})",
        )
    )
    return lead
