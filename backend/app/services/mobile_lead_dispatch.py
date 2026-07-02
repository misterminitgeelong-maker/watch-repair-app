"""Uber-style mobile lead dispatch: offer → timeout → next operator → HQ."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlmodel import Session, func, select

from ..dependencies import PLAN_FEATURES, AuthContext, enforce_plan_limit, normalize_plan_code
from ..minit_mobile_routing import (
    candidate_operator_ids_json,
    normalize_suburb_name,
    parse_candidate_operator_ids,
    rank_mobile_operator_candidates,
    suburb_in_operator_territory,
)
from ..minit_provision import _is_operator_plan
from ..models import (
    AutoKeyJob,
    AutoKeyQuote,
    Customer,
    CustomerAccountMembership,
    MobileLeadDispatch,
    ParentAccount,
    ParentAccountEventLog,
    ParentAccountMembership,
    Tenant,
    TenantEventLog,
)
from .. import sms as sms_service

logger = logging.getLogger(__name__)

DISPATCH_STATUS_OFFERING = "offering"
DISPATCH_STATUS_QUOTED = "quoted"
DISPATCH_STATUS_ESCALATED_HQ = "escalated_hq"
DISPATCH_STATUS_FAILED = "failed"


def _digits_phone(p: str | None) -> str | None:
    if not p:
        return None
    d = "".join(c for c in p if c.isdigit())
    return d or None


def _tenant_linked_to_parent(session: Session, parent_id: UUID, tenant_id: UUID) -> bool:
    row = session.exec(
        select(ParentAccountMembership)
        .where(ParentAccountMembership.parent_account_id == parent_id)
        .where(ParentAccountMembership.tenant_id == tenant_id)
    ).first()
    return row is not None


def _tenant_accepts_mobile_leads(tenant: Tenant, *, is_escalation: bool = False) -> bool:
    plan_code = normalize_plan_code(tenant.plan_code)
    if "auto_key" in PLAN_FEATURES.get(plan_code, set()):
        return True
    return is_escalation


def _next_auto_key_job_number(session: Session, tenant_id: UUID) -> str:
    count = session.exec(select(func.count()).select_from(AutoKeyJob).where(AutoKeyJob.tenant_id == tenant_id)).one()
    return f"AK-{int(count) + 1:05d}"


def lead_payload_from_body(body: Any) -> dict[str, Any]:
    """Serialize ingest body to JSON-safe dict."""
    if hasattr(body, "model_dump"):
        return body.model_dump()
    return dict(body)


def _find_or_create_customer(session: Session, tenant_id: UUID, payload: dict[str, Any]) -> Customer:
    phone_digits = _digits_phone(payload.get("phone"))
    if phone_digits:
        customers = session.exec(select(Customer).where(Customer.tenant_id == tenant_id)).all()
        for c in customers:
            if c.phone and _digits_phone(c.phone) == phone_digits:
                return c
    email = payload.get("email")
    if email:
        em = str(email).strip().lower()
        existing = session.exec(
            select(Customer).where(Customer.tenant_id == tenant_id).where(Customer.email == em)
        ).first()
        if existing:
            return existing

    suburb = str(payload.get("suburb") or "").strip()
    state_code = str(payload.get("state_code") or "").strip().upper()
    street = payload.get("street_address")
    addr_line = ", ".join(
        p
        for p in [
            str(street).strip() if street else None,
            f"{suburb} {state_code}" if suburb else None,
        ]
        if p
    )
    c = Customer(
        tenant_id=tenant_id,
        full_name=str(payload.get("customer_name") or "Website lead").strip()[:300],
        phone=str(payload.get("phone")).strip()[:80] if payload.get("phone") else None,
        email=str(email).strip().lower()[:320] if email else None,
        address=addr_line[:2000] if addr_line else None,
        notes="Created from website mobile key lead",
    )
    session.add(c)
    session.flush()
    return c


def _build_job_from_payload(
    session: Session,
    *,
    tenant_id: UUID,
    payload: dict[str, Any],
    suburb: str,
    state_code: str,
) -> AutoKeyJob:
    customer = _find_or_create_customer(session, tenant_id, payload)
    inferred = session.exec(
        select(CustomerAccountMembership)
        .where(CustomerAccountMembership.tenant_id == tenant_id)
        .where(CustomerAccountMembership.customer_id == customer.id)
        .order_by(CustomerAccountMembership.created_at)
    ).first()
    customer_account_id = inferred.customer_account_id if inferred else None

    st = state_code.strip().upper()
    street = payload.get("street_address")
    job_address_parts = [
        str(street).strip() if street else None,
        f"{suburb.strip()} {st}",
    ]
    job_address = ", ".join(p for p in job_address_parts if p)[:2000] or None

    desc_parts: list[str] = ["Submitted via website lead feed."]
    key_result = payload.get("key_service_result")
    if key_result:
        desc_parts.append(f"Key checker / site result: {str(key_result).strip()}")
    website_notes = payload.get("website_notes")
    if website_notes:
        desc_parts.append(str(website_notes).strip())
    description = "\n\n".join(desc_parts)[:8000]

    customer_name = str(payload.get("customer_name") or "Customer").strip()
    vehicle_bits = [payload.get("vehicle_make"), payload.get("vehicle_model"), payload.get("registration_plate")]
    title_vehicle = " · ".join(str(x).strip() for x in vehicle_bits if x and str(x).strip())
    title = f"Web lead — {customer_name}" + (f" ({title_vehicle})" if title_vehicle else "")

    return AutoKeyJob(
        tenant_id=tenant_id,
        customer_id=customer.id,
        customer_account_id=customer_account_id,
        job_number=_next_auto_key_job_number(session, tenant_id),
        title=title[:500],
        description=description or None,
        vehicle_make=str(payload.get("vehicle_make")).strip()[:120] if payload.get("vehicle_make") else None,
        vehicle_model=str(payload.get("vehicle_model")).strip()[:120] if payload.get("vehicle_model") else None,
        registration_plate=str(payload.get("registration_plate")).strip()[:32] if payload.get("registration_plate") else None,
        job_address=job_address,
        job_type="Diagnostic",
        status="awaiting_quote",
        priority="normal",
        key_quantity=1,
        programming_status="pending",
        deposit_cents=0,
        cost_cents=0,
    )


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


def _log_inbox_quote_needed(
    session: Session,
    *,
    tenant_id: UUID,
    job: AutoKeyJob,
    customer_name: str,
    suburb: str,
    state_code: str,
    summary_suffix: str = "",
) -> None:
    suffix = f" {summary_suffix}".rstrip()
    session.add(
        TenantEventLog(
            tenant_id=tenant_id,
            actor_user_id=None,
            actor_email="website-lead@ingest",
            entity_type="auto_key_job",
            entity_id=job.id,
            event_type="mobile_lead_quote_needed",
            event_summary=(
                f"New website lead #{job.job_number} — quote required "
                f"({customer_name}, {suburb} {state_code}){suffix}"
            ),
        )
    )


def _close_unquoted_job(session: Session, job: AutoKeyJob, *, reason: str) -> None:
    if job.status != "awaiting_quote":
        return
    job.status = "failed_job"
    note = f"[Lead escalated] {reason}"
    job.tech_notes = f"{job.tech_notes}\n{note}".strip() if job.tech_notes else note
    session.add(job)


def dispatch_is_quoted(session: Session, dispatch: MobileLeadDispatch) -> bool:
    if dispatch.status != DISPATCH_STATUS_OFFERING:
        return dispatch.status == DISPATCH_STATUS_QUOTED
    if not dispatch.auto_key_job_id:
        return False
    job = session.get(AutoKeyJob, dispatch.auto_key_job_id)
    if not job:
        return False
    if job.status != "awaiting_quote":
        return True
    quote = session.exec(
        select(AutoKeyQuote).where(AutoKeyQuote.auto_key_job_id == job.id)
    ).first()
    if quote and quote.status in {"sent", "approved", "declined"}:
        return True
    return False


def complete_dispatch_if_quoted(session: Session, job_id: UUID) -> bool:
    dispatch = session.exec(
        select(MobileLeadDispatch)
        .where(MobileLeadDispatch.auto_key_job_id == job_id)
        .where(MobileLeadDispatch.status == DISPATCH_STATUS_OFFERING)
    ).first()
    if not dispatch:
        return False
    dispatch.status = DISPATCH_STATUS_QUOTED
    dispatch.offer_expires_at = None
    dispatch.updated_at = datetime.now(timezone.utc)
    session.add(dispatch)
    session.add(
        ParentAccountEventLog(
            parent_account_id=dispatch.parent_account_id,
            tenant_id=dispatch.current_operator_tenant_id,
            actor_email="website-lead@dispatch",
            event_type="mobile_lead_dispatch_quoted",
            event_summary=f"Website lead quoted on job {job_id}",
        )
    )
    return True


def _create_job_for_dispatch(
    session: Session,
    dispatch: MobileLeadDispatch,
    tenant_id: UUID,
    *,
    is_escalation: bool = False,
) -> AutoKeyJob:
    parent = session.get(ParentAccount, dispatch.parent_account_id)
    if not parent:
        raise ValueError("Parent account missing for dispatch")

    tenant = session.get(Tenant, tenant_id)
    if not tenant:
        raise ValueError("Target tenant not found")
    if not _tenant_linked_to_parent(session, parent.id, tenant_id):
        raise ValueError("Target tenant not linked to parent")
    if not _tenant_accepts_mobile_leads(tenant, is_escalation=is_escalation):
        raise ValueError("Target tenant plan does not include mobile services")

    plan_code = normalize_plan_code(tenant.plan_code)
    if "auto_key" in PLAN_FEATURES.get(plan_code, set()):
        ak_count = int(
            session.exec(select(func.count()).select_from(AutoKeyJob).where(AutoKeyJob.tenant_id == tenant_id)).one()
        )
        ingest_ctx = AuthContext(tenant_id=tenant_id, user_id=uuid4(), role="owner", plan_code=plan_code)
        enforce_plan_limit(ingest_ctx, "auto_key_job", ak_count)

    payload = json.loads(dispatch.payload_json)
    job = _build_job_from_payload(
        session,
        tenant_id=tenant_id,
        payload=payload,
        suburb=dispatch.suburb,
        state_code=dispatch.state_code,
    )
    session.add(job)
    session.flush()

    customer_name = str(payload.get("customer_name") or "Customer").strip()
    _log_inbox_quote_needed(
        session,
        tenant_id=tenant_id,
        job=job,
        customer_name=customer_name,
        suburb=dispatch.suburb,
        state_code=dispatch.state_code,
    )
    return job


def _notify_operator_offer(session: Session, dispatch: MobileLeadDispatch, job: AutoKeyJob, tenant: Tenant) -> None:
    phone = sms_service.operator_dispatch_phone(tenant)
    if not phone:
        logger.info("mobile_lead_dispatch.no_dispatch_phone tenant=%s dispatch=%s", tenant.id, dispatch.id)
        return
    payload = json.loads(dispatch.payload_json)
    sms_service.notify_mobile_lead_offer(
        session,
        tenant_id=tenant.id,
        auto_key_job_id=job.id,
        to_phone=phone,
        customer_name=str(payload.get("customer_name") or "Customer"),
        customer_phone=payload.get("phone"),
        suburb=dispatch.suburb,
        state_code=dispatch.state_code,
        vehicle_make=payload.get("vehicle_make"),
        vehicle_model=payload.get("vehicle_model"),
        registration_plate=payload.get("registration_plate"),
        job_number=job.job_number,
        timeout_minutes=dispatch.offer_timeout_minutes,
    )


def offer_dispatch_to_current_operator(session: Session, dispatch: MobileLeadDispatch) -> AutoKeyJob | None:
    """Create job on current operator and send SMS offer."""
    operator_ids = parse_candidate_operator_ids(dispatch.candidate_operator_ids_json)
    if dispatch.current_offer_index >= len(operator_ids):
        return None

    operator_id = operator_ids[dispatch.current_offer_index]
    tenant = session.get(Tenant, operator_id)
    if not tenant:
        return None

    job = _create_job_for_dispatch(session, dispatch, operator_id)
    dispatch.current_operator_tenant_id = operator_id
    dispatch.auto_key_job_id = job.id
    dispatch.offer_expires_at = datetime.now(timezone.utc) + timedelta(minutes=dispatch.offer_timeout_minutes)
    dispatch.updated_at = datetime.now(timezone.utc)
    session.add(dispatch)
    session.flush()

    _notify_operator_offer(session, dispatch, job, tenant)
    session.add(
        ParentAccountEventLog(
            parent_account_id=dispatch.parent_account_id,
            tenant_id=operator_id,
            actor_email="website-lead@dispatch",
            event_type="mobile_lead_dispatch_offered",
            event_summary=(
                f"Website lead offered to {tenant.name} ({dispatch.suburb} {dispatch.state_code}) "
                f"— {dispatch.offer_timeout_minutes} min to quote"
            ),
        )
    )
    return job


def escalate_dispatch_to_hq(
    session: Session,
    dispatch: MobileLeadDispatch,
    *,
    reason: str = "operator_timeout",
) -> AutoKeyJob | None:
    parent = session.get(ParentAccount, dispatch.parent_account_id)
    if not parent:
        dispatch.status = DISPATCH_STATUS_FAILED
        session.add(dispatch)
        return None

    hq_tid = _escalation_tenant_id(session, parent)
    if not hq_tid:
        dispatch.status = DISPATCH_STATUS_FAILED
        dispatch.updated_at = datetime.now(timezone.utc)
        session.add(dispatch)
        return None

    if dispatch.auto_key_job_id:
        old_job = session.get(AutoKeyJob, dispatch.auto_key_job_id)
        if old_job:
            _close_unquoted_job(session, old_job, reason="No operator quoted in time; escalated to HQ.")

    job = _create_job_for_dispatch(session, dispatch, hq_tid, is_escalation=True)
    dispatch.status = DISPATCH_STATUS_ESCALATED_HQ
    dispatch.current_operator_tenant_id = hq_tid
    dispatch.auto_key_job_id = job.id
    dispatch.offer_expires_at = None
    dispatch.updated_at = datetime.now(timezone.utc)
    session.add(dispatch)

    payload = json.loads(dispatch.payload_json)
    customer_name = str(payload.get("customer_name") or "Customer").strip()
    if reason == "outside_operator_territory":
        summary = (
            f"Website lead outside operator map — HQ manual dispatch "
            f"({customer_name}, {dispatch.suburb} {dispatch.state_code})"
        )
        inbox_suffix = "— outside operator map, HQ manual dispatch"
    elif reason == "testing_hq_mode":
        summary = (
            f"Website lead (HQ testing mode) — manual dispatch "
            f"({customer_name}, {dispatch.suburb} {dispatch.state_code})"
        )
        inbox_suffix = "— HQ testing mode, manual dispatch"
    else:
        summary = (
            f"Website lead escalated to HQ for manual quoting "
            f"({customer_name}, {dispatch.suburb} {dispatch.state_code})"
        )
        inbox_suffix = "— HQ manual quote"
    session.add(
        ParentAccountEventLog(
            parent_account_id=dispatch.parent_account_id,
            tenant_id=hq_tid,
            actor_email="website-lead@dispatch",
            event_type="mobile_lead_dispatch_escalated_hq",
            event_summary=summary,
        )
    )
    _log_inbox_quote_needed(
        session,
        tenant_id=hq_tid,
        job=job,
        customer_name=customer_name,
        suburb=dispatch.suburb,
        state_code=dispatch.state_code,
        summary_suffix=inbox_suffix,
    )
    return job


def advance_expired_dispatch(session: Session, dispatch: MobileLeadDispatch) -> str:
    """Move an expired offer to the next operator or HQ. Returns action taken."""
    if dispatch.status != DISPATCH_STATUS_OFFERING:
        return "skipped"

    if dispatch_is_quoted(session, dispatch):
        dispatch.status = DISPATCH_STATUS_QUOTED
        dispatch.offer_expires_at = None
        dispatch.updated_at = datetime.now(timezone.utc)
        session.add(dispatch)
        return "quoted"

    if dispatch.auto_key_job_id:
        old_job = session.get(AutoKeyJob, dispatch.auto_key_job_id)
        if old_job:
            _close_unquoted_job(session, old_job, reason="Operator did not quote within the time limit.")

    operator_ids = parse_candidate_operator_ids(dispatch.candidate_operator_ids_json)
    next_index = dispatch.current_offer_index + 1
    max_offers = min(dispatch.max_operator_offers, len(operator_ids))

    if next_index < max_offers:
        dispatch.current_offer_index = next_index
        dispatch.auto_key_job_id = None
        dispatch.current_operator_tenant_id = None
        dispatch.updated_at = datetime.now(timezone.utc)
        session.add(dispatch)
        session.flush()
        offer_dispatch_to_current_operator(session, dispatch)
        return "next_operator"

    escalate_dispatch_to_hq(session, dispatch)
    return "escalated_hq"


def start_mobile_lead_dispatch(
    session: Session,
    *,
    parent: ParentAccount,
    payload: dict[str, Any],
    suburb: str,
    state_code: str,
) -> MobileLeadDispatch:
    """Create dispatch record and offer to the first operator."""
    st = state_code.strip().upper()
    sub_norm = normalize_suburb_name(suburb)
    timeout = max(int(parent.mobile_lead_offer_timeout_minutes or 30), 5)
    max_offers = max(int(parent.mobile_lead_max_operator_offers or 3), 1)

    force_hq = bool(parent.mobile_lead_force_hq_dispatch)
    in_territory = False if force_hq else suburb_in_operator_territory(
        session,
        parent_id=parent.id,
        suburb=suburb,
        state_code=st,
    )
    candidates: list[UUID] = []
    if in_territory:
        candidates = rank_mobile_operator_candidates(
            session,
            parent_id=parent.id,
            suburb=suburb,
            state_code=st,
            max_candidates=max_offers,
        )

    dispatch = MobileLeadDispatch(
        parent_account_id=parent.id,
        status=DISPATCH_STATUS_OFFERING,
        suburb=suburb.strip(),
        state_code=st,
        suburb_normalized=sub_norm,
        payload_json=json.dumps(payload),
        candidate_operator_ids_json=candidate_operator_ids_json(candidates),
        current_offer_index=0,
        offer_timeout_minutes=timeout,
        max_operator_offers=max_offers,
    )
    session.add(dispatch)
    session.flush()

    if candidates:
        offer_dispatch_to_current_operator(session, dispatch)
    else:
        reason = "testing_hq_mode" if force_hq else (
            "outside_operator_territory" if not in_territory else "operator_timeout"
        )
        escalate_dispatch_to_hq(session, dispatch, reason=reason)

    return dispatch


def process_due_mobile_lead_dispatches(session: Session) -> dict[str, int]:
    """Check offering dispatches past their deadline and escalate as needed."""
    now = datetime.now(timezone.utc)
    rows = session.exec(
        select(MobileLeadDispatch)
        .where(MobileLeadDispatch.status == DISPATCH_STATUS_OFFERING)
        .where(MobileLeadDispatch.offer_expires_at.is_not(None))  # type: ignore[union-attr]
        .where(MobileLeadDispatch.offer_expires_at <= now)
    ).all()

    summary = {"checked": len(rows), "quoted": 0, "next_operator": 0, "escalated_hq": 0, "skipped": 0}
    for dispatch in rows:
        action = advance_expired_dispatch(session, dispatch)
        summary[action] = summary.get(action, 0) + 1
    if summary["checked"]:
        session.commit()
    return summary
