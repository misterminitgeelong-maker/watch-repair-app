"""Inbound email capture: BCC'd enquiry-form emails → stored lead + HQ inbox alert.

Public endpoint receives POSTs from an inbound-parse provider (SendGrid Inbound
Parse). The provider cannot send custom headers, so the parent account's
existing website-lead shared secret is passed as a ``key`` query parameter.

Capture-and-triage v1: no field parsing — the email is stored whole and
surfaced in the Minit HQ inbox so a person can create the job. Auto-parsing
into AutoKey jobs comes once real form templates have been collected.

Note: no ``from __future__ import annotations`` here — stringified annotations
on the public route's signature crash request handling and /openapi.json under
the deployed fastapi 0.115 + pydantic >= 2.12 combination (unresolvable
``ForwardRef('UUID')`` TypeAdapter).
"""

import re
from email import policy
from email.parser import BytesParser
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlmodel import Session, func, select

from ..database import get_session
from ..dependencies import (
    PLAN_FEATURES,
    AuthContext,
    enforce_plan_limit,
    normalize_plan_code,
    require_feature,
    require_owner,
)
from ..limiter import limiter
from ..minit_email_lead_parser import match_operator_for_lead, parse_powerfulform_body
from ..models import (
    AutoKeyJob,
    Customer,
    InboundEmail,
    InboundEmailDetail,
    InboundEmailJobCreateRequest,
    InboundEmailJobCreateResult,
    InboundEmailListItem,
    InboundEmailParsedRead,
    InboundEmailStatusUpdateRequest,
    ParentAccount,
    Tenant,
    TenantEventLog,
    User,
)
from ..security import verify_password
from ..services.mobile_lead_dispatch import _escalation_tenant_id, _next_auto_key_job_number
from .parent_accounts import _get_parent_account_for_user

public_router = APIRouter(prefix="/v1/public", tags=["inbound-email"])

hq_router = APIRouter(
    prefix="/v1/parent-accounts",
    tags=["inbound-email"],
    dependencies=[Depends(require_feature("multi_site"))],
)

# Guard rails so a single email cannot bloat a row (bodies are for triage reading).
MAX_TEXT_BODY = 100_000
MAX_HTML_BODY = 300_000
MAX_RAW_HEADERS = 20_000

INBOUND_EMAIL_STATUSES = frozenset({"new", "processed", "dismissed"})

_MESSAGE_ID_RE = re.compile(r"^Message-ID:\s*(<[^>]{1,480}>)", re.IGNORECASE | re.MULTILINE)


def _clip(value: str | None, limit: int) -> str | None:
    if not value:
        return None
    return value[:limit]


def _first_str(form, *names: str) -> str | None:
    """Return the first non-empty string form field among ``names``."""
    for name in names:
        value = form.get(name)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _parse_raw_mime(raw: str) -> dict[str, str | None]:
    """Extract headers/bodies from a full MIME message ("POST raw" parse mode)."""
    msg = BytesParser(policy=policy.default).parsebytes(raw.encode("utf-8", errors="replace"))
    text_body: str | None = None
    html_body: str | None = None
    body = msg.get_body(preferencelist=("plain",))
    if body is not None:
        text_body = body.get_content()
    body = msg.get_body(preferencelist=("html",))
    if body is not None:
        html_body = body.get_content()
    headers = "\n".join(f"{k}: {v}" for k, v in msg.items())
    return {
        "headers": headers,
        "text": text_body,
        "html": html_body,
        "from": str(msg.get("From") or "") or None,
        "to": str(msg.get("To") or "") or None,
        "subject": str(msg.get("Subject") or "") or None,
        "message_id": str(msg.get("Message-ID") or "").strip() or None,
    }


@public_router.post("/inbound-email/{ingest_public_id}")
@limiter.limit("60/minute")
async def receive_inbound_email(
    request: Request,
    ingest_public_id: UUID,
    key: str = Query(..., min_length=16, max_length=512),
    session: Session = Depends(get_session),
):
    """Accept an inbound-parse POST (SendGrid) for a BCC'd website enquiry email.

    Configure the parse webhook URL as
    ``/v1/public/inbound-email/{ingest_public_id}?key=<shared secret>`` using the
    same secret as the website lead feed (Parent account → Website lead feed).
    """
    parent = session.exec(
        select(ParentAccount).where(ParentAccount.mobile_lead_ingest_public_id == ingest_public_id)
    ).first()
    if not parent or not parent.mobile_lead_webhook_secret_hash:
        raise HTTPException(status_code=404, detail="Unknown ingest endpoint")
    if not verify_password(key, parent.mobile_lead_webhook_secret_hash):
        raise HTTPException(status_code=401, detail="Invalid key")

    form = await request.form()

    from_email = _first_str(form, "from")
    to_email = _first_str(form, "to")
    subject = _first_str(form, "subject")
    text_body = _first_str(form, "text")
    html_body = _first_str(form, "html")
    raw_headers = _first_str(form, "headers")
    spf_result = _first_str(form, "SPF", "spf")
    dkim_result = _first_str(form, "dkim")
    sender_ip = _first_str(form, "sender_ip")

    # "POST the raw, full MIME message" mode delivers everything in one field.
    raw_mime = _first_str(form, "email")
    message_id: str | None = None
    if raw_mime and not (text_body or html_body):
        parsed = _parse_raw_mime(raw_mime)
        text_body = text_body or parsed["text"]
        html_body = html_body or parsed["html"]
        raw_headers = raw_headers or parsed["headers"]
        from_email = from_email or parsed["from"]
        to_email = to_email or parsed["to"]
        subject = subject or parsed["subject"]
        message_id = parsed["message_id"]

    if raw_headers and not message_id:
        m = _MESSAGE_ID_RE.search(raw_headers)
        if m:
            message_id = m.group(1)

    if not (text_body or html_body or subject or raw_mime):
        raise HTTPException(status_code=400, detail="No email content in payload")

    if message_id:
        existing = session.exec(
            select(InboundEmail)
            .where(InboundEmail.parent_account_id == parent.id)
            .where(InboundEmail.message_id == message_id)
        ).first()
        if existing:
            return {"inbound_email_id": str(existing.id), "status": "duplicate"}

    row = InboundEmail(
        parent_account_id=parent.id,
        message_id=_clip(message_id, 500),
        from_email=_clip(from_email, 500),
        to_email=_clip(to_email, 500),
        subject=_clip(subject, 1000),
        text_body=_clip(text_body, MAX_TEXT_BODY),
        html_body=_clip(html_body, MAX_HTML_BODY),
        raw_headers=_clip(raw_headers, MAX_RAW_HEADERS),
        spf_result=_clip(spf_result, 200),
        dkim_result=_clip(dkim_result, 500),
        sender_ip=_clip(sender_ip, 60),
    )
    session.add(row)
    session.flush()

    if parent.mobile_lead_default_tenant_id:
        session.add(
            TenantEventLog(
                tenant_id=parent.mobile_lead_default_tenant_id,
                actor_user_id=None,
                actor_email="inbound-email@ingest",
                entity_type="inbound_email",
                entity_id=row.id,
                event_type="inbound_email_received",
                event_summary=f"New email lead — {(subject or '(no subject)').strip()[:200]} — from {(from_email or 'unknown sender').strip()[:200]}",
            )
        )
    session.commit()
    return {"inbound_email_id": str(row.id), "status": "received"}


def _get_owned_inbound_email(session: Session, auth: AuthContext, inbound_email_id: UUID) -> InboundEmail:
    current_user = session.get(User, auth.user_id)
    if not current_user or not current_user.is_active:
        raise HTTPException(status_code=401, detail="Invalid token")
    parent = _get_parent_account_for_user(session, current_user)
    row = session.get(InboundEmail, inbound_email_id)
    if not row or row.parent_account_id != parent.id:
        raise HTTPException(status_code=404, detail="Not found")
    return row


@hq_router.get("/me/inbound-emails", response_model=list[InboundEmailListItem])
def list_inbound_emails(
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(get_session),
):
    """Captured enquiry emails for triage (newest first)."""
    current_user = session.get(User, auth.user_id)
    if not current_user or not current_user.is_active:
        raise HTTPException(status_code=401, detail="Invalid token")
    parent = _get_parent_account_for_user(session, current_user)
    query = select(InboundEmail).where(InboundEmail.parent_account_id == parent.id)
    if status:
        if status not in INBOUND_EMAIL_STATUSES:
            raise HTTPException(status_code=400, detail=f"Invalid status; use one of: {', '.join(sorted(INBOUND_EMAIL_STATUSES))}")
        query = query.where(InboundEmail.status == status)
    rows = session.exec(query.order_by(InboundEmail.created_at.desc()).offset(offset).limit(limit)).all()
    return rows


@hq_router.get("/me/inbound-emails/{inbound_email_id}", response_model=InboundEmailDetail)
def get_inbound_email(
    inbound_email_id: UUID,
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(get_session),
):
    return _get_owned_inbound_email(session, auth, inbound_email_id)


@hq_router.patch("/me/inbound-emails/{inbound_email_id}", response_model=InboundEmailDetail)
def update_inbound_email_status(
    inbound_email_id: UUID,
    body: InboundEmailStatusUpdateRequest,
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(get_session),
):
    """Mark a captured email processed (job created manually) or dismissed."""
    status = body.status.strip().lower()
    if status not in INBOUND_EMAIL_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status; use one of: {', '.join(sorted(INBOUND_EMAIL_STATUSES))}")
    row = _get_owned_inbound_email(session, auth, inbound_email_id)
    row.status = status
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@hq_router.get("/me/inbound-emails/{inbound_email_id}/parsed", response_model=InboundEmailParsedRead)
def get_inbound_email_parsed_preview(
    inbound_email_id: UUID,
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(get_session),
):
    """Read-only preview of what the parser would extract from this email — creates nothing.

    Used to pre-fill the staff review form; some emails (observed for NZ regions)
    carry no field data at all, in which case ``fields_found`` is False and the
    rest of the fields are empty — the form should fall back to blank inputs.
    """
    current_user = session.get(User, auth.user_id)
    if not current_user or not current_user.is_active:
        raise HTTPException(status_code=401, detail="Invalid token")
    parent = _get_parent_account_for_user(session, current_user)
    row = _get_owned_inbound_email(session, auth, inbound_email_id)

    parsed = parse_powerfulform_body(row.text_body)
    suggested_tenant_id: UUID | None = None
    suggested_name: str | None = None
    match_confidence = "no_fields_found"
    if parsed.fields_found:
        match = match_operator_for_lead(session, parent_id=parent.id, parsed=parsed)
        match_confidence = match.confidence
        if match.tenant:
            suggested_tenant_id = match.tenant.id
            suggested_name = match.tenant.name

    return InboundEmailParsedRead(
        fields_found=parsed.fields_found,
        location_state_raw=parsed.location_state_raw,
        nearest_provider_raw=parsed.nearest_provider_raw,
        customer_name=parsed.customer_name,
        email=parsed.email,
        phone=parsed.phone,
        service_required=parsed.service_required,
        vehicle_make=parsed.vehicle_make,
        vehicle_model=parsed.vehicle_model,
        vehicle_year=parsed.vehicle_year,
        details=parsed.details,
        contact_preference=parsed.contact_preference,
        suggested_operator_tenant_id=suggested_tenant_id,
        suggested_operator_name=suggested_name,
        match_confidence=match_confidence,
    )


def _digits_only(value: str | None) -> str | None:
    if not value:
        return None
    digits = "".join(ch for ch in value if ch.isdigit())
    return digits or None


def _find_or_create_customer_for_email_lead(
    session: Session, tenant_id: UUID, body: InboundEmailJobCreateRequest
) -> Customer:
    phone_digits = _digits_only(body.phone)
    if phone_digits:
        customers = session.exec(select(Customer).where(Customer.tenant_id == tenant_id)).all()
        for c in customers:
            if c.phone and _digits_only(c.phone) == phone_digits:
                return c
    if body.email:
        email_norm = body.email.strip().lower()
        existing = session.exec(
            select(Customer).where(Customer.tenant_id == tenant_id).where(Customer.email == email_norm)
        ).first()
        if existing:
            return existing

    address = " ".join(p.strip() for p in (body.suburb, body.state_code) if p and p.strip()) or None
    customer = Customer(
        tenant_id=tenant_id,
        full_name=body.customer_name.strip()[:300],
        phone=body.phone.strip()[:80] if body.phone else None,
        email=body.email.strip().lower()[:320] if body.email else None,
        address=address,
        notes="Created from Mister Minit BCC email lead",
    )
    session.add(customer)
    session.flush()
    return customer


@hq_router.post(
    "/me/inbound-emails/{inbound_email_id}/create-job",
    response_model=InboundEmailJobCreateResult,
    status_code=201,
)
def create_job_from_inbound_email(
    inbound_email_id: UUID,
    body: InboundEmailJobCreateRequest,
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(get_session),
):
    """Create a job from staff-reviewed (and possibly hand-edited) email fields.

    Always lands on the parent's HQ/escalation tenant unless ``target_tenant_id``
    is explicitly given — this never auto-assigns the job to the matched
    operator. No SMS or notification is sent to anyone; this only creates a job
    record so HQ isn't retyping raw email text by hand.
    """
    current_user = session.get(User, auth.user_id)
    if not current_user or not current_user.is_active:
        raise HTTPException(status_code=401, detail="Invalid token")
    parent = _get_parent_account_for_user(session, current_user)
    row = _get_owned_inbound_email(session, auth, inbound_email_id)
    if row.auto_key_job_id:
        raise HTTPException(status_code=409, detail="A job has already been created from this email")

    tenant_id = body.target_tenant_id or _escalation_tenant_id(session, parent)
    if not tenant_id:
        raise HTTPException(
            status_code=400,
            detail="No target tenant — pass target_tenant_id or configure an HQ escalation tenant first",
        )
    tenant = session.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Target tenant not found")

    plan_code = normalize_plan_code(tenant.plan_code)
    if "auto_key" in PLAN_FEATURES.get(plan_code, set()):
        ak_count = int(
            session.exec(
                select(func.count()).select_from(AutoKeyJob).where(AutoKeyJob.tenant_id == tenant_id)
            ).one()
        )
        limit_ctx = AuthContext(tenant_id=tenant_id, user_id=uuid4(), role="owner", plan_code=plan_code)
        enforce_plan_limit(limit_ctx, "auto_key_job", ak_count)

    customer = _find_or_create_customer_for_email_lead(session, tenant_id, body)

    desc_parts = ["Created from a Mister Minit BCC email lead (reviewed by staff before creation)."]
    if body.service_required:
        desc_parts.append(f"Service required: {body.service_required.strip()}")
    if body.details:
        desc_parts.append(body.details.strip())
    if body.contact_preference:
        desc_parts.append(f"Preferred contact method: {body.contact_preference.strip()}")
    description = "\n\n".join(desc_parts)[:8000]

    job_address = " ".join(p.strip() for p in (body.suburb, body.state_code) if p and p.strip()) or None
    vehicle_year: int | None = None
    if body.vehicle_year and body.vehicle_year.strip().isdigit():
        vehicle_year = int(body.vehicle_year.strip())

    job = AutoKeyJob(
        tenant_id=tenant_id,
        customer_id=customer.id,
        job_number=_next_auto_key_job_number(session, tenant_id),
        title=f"Email lead — {body.customer_name.strip()}"[:500],
        description=description or None,
        vehicle_make=body.vehicle_make.strip()[:120] if body.vehicle_make else None,
        vehicle_model=body.vehicle_model.strip()[:120] if body.vehicle_model else None,
        vehicle_year=vehicle_year,
        job_address=job_address,
        job_type="Diagnostic",
        status="awaiting_quote",
        priority="normal",
        key_quantity=1,
        programming_status="pending",
        deposit_cents=0,
        cost_cents=0,
    )
    session.add(job)
    session.flush()

    row.auto_key_job_id = job.id
    row.status = "processed"
    session.add(row)

    session.add(
        TenantEventLog(
            tenant_id=tenant_id,
            actor_user_id=auth.user_id,
            actor_email=current_user.email,
            entity_type="auto_key_job",
            entity_id=job.id,
            event_type="email_lead_job_created",
            event_summary=f"Job #{job.job_number} created from email lead ({body.customer_name.strip()})",
        )
    )

    session.commit()
    session.refresh(job)

    return InboundEmailJobCreateResult(
        inbound_email_id=row.id,
        auto_key_job_id=job.id,
        job_number=job.job_number,
        tenant_id=tenant_id,
        tenant_name=tenant.name,
    )
