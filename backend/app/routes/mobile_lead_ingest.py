"""Public webhook: website submits mobile key enquiry → routed AutoKey job + inbox alert."""

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlmodel import Session, func, select

from ..database import get_session
from ..dependencies import AuthContext, PLAN_FEATURES, enforce_plan_limit, normalize_plan_code
from ..limiter import limiter
from ..models import (
    AutoKeyJob,
    Customer,
    CustomerAccountMembership,
    MobileSuburbRoute,
    ParentAccount,
    ParentAccountMembership,
    Tenant,
    TenantEventLog,
)
from ..security import verify_password

router = APIRouter(prefix="/v1/public", tags=["mobile-lead-ingest"])

AU_STATES = frozenset({"ACT", "NSW", "NT", "QLD", "SA", "TAS", "VIC", "WA"})


def _normalize_suburb(name: str) -> str:
    return " ".join(name.strip().lower().split())


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


def _next_auto_key_job_number(session: Session, tenant_id: UUID) -> str:
    count = session.exec(select(func.count()).select_from(AutoKeyJob).where(AutoKeyJob.tenant_id == tenant_id)).one()
    return f"AK-{int(count) + 1:05d}"


class MobileKeyLeadIngestBody(BaseModel):
    suburb: str = Field(..., min_length=1, max_length=200)
    state_code: str = Field(..., min_length=2, max_length=8)
    customer_name: str = Field(..., min_length=1, max_length=300)
    phone: str | None = Field(default=None, max_length=80)
    email: str | None = Field(default=None, max_length=320)
    vehicle_make: str | None = Field(default=None, max_length=120)
    vehicle_model: str | None = Field(default=None, max_length=120)
    registration_plate: str | None = Field(default=None, max_length=32)
    street_address: str | None = Field(default=None, max_length=500)
    website_notes: str | None = Field(default=None, max_length=4000)
    key_service_result: str | None = Field(default=None, max_length=500)


def _find_or_create_customer(session: Session, tenant_id: UUID, body: MobileKeyLeadIngestBody) -> Customer:
    phone_digits = _digits_phone(body.phone)
    if phone_digits:
        customers = session.exec(select(Customer).where(Customer.tenant_id == tenant_id)).all()
        for c in customers:
            if c.phone and _digits_phone(c.phone) == phone_digits:
                return c
    if body.email:
        em = body.email.strip().lower()
        existing = session.exec(
            select(Customer).where(Customer.tenant_id == tenant_id).where(Customer.email == em)
        ).first()
        if existing:
            return existing
    addr_line = ", ".join(
        p
        for p in [
            body.street_address.strip() if body.street_address else None,
            f"{body.suburb.strip()} {body.state_code.strip().upper()}",
        ]
        if p
    )
    c = Customer(
        tenant_id=tenant_id,
        full_name=body.customer_name.strip()[:300],
        phone=body.phone.strip()[:80] if body.phone else None,
        email=body.email.strip().lower()[:320] if body.email else None,
        address=addr_line[:2000] if addr_line else None,
        notes="Created from website mobile key lead",
    )
    session.add(c)
    session.flush()
    return c


@router.post("/mobile-key-leads/{ingest_public_id}")
@limiter.limit("60/minute")
def ingest_mobile_key_lead(
    request: Request,
    ingest_public_id: UUID,
    body: MobileKeyLeadIngestBody,
    session: Session = Depends(get_session),
    x_mobile_lead_secret: str | None = Header(default=None, alias="X-Mobile-Lead-Secret"),
):
    """Accept a lead from your public website (e.g. Mister Minit key checker). Requires configured parent account + routes.

    Header: ``X-Mobile-Lead-Secret``: shared secret (set in Parent account → Website lead feed).
    """
    if not x_mobile_lead_secret or len(x_mobile_lead_secret) < 16:
        raise HTTPException(status_code=401, detail="Missing or invalid X-Mobile-Lead-Secret header")

    parent = session.exec(
        select(ParentAccount).where(ParentAccount.mobile_lead_ingest_public_id == ingest_public_id)
    ).first()
    if not parent or not parent.mobile_lead_webhook_secret_hash:
        raise HTTPException(status_code=404, detail="Unknown ingest endpoint")

    if not verify_password(x_mobile_lead_secret, parent.mobile_lead_webhook_secret_hash):
        raise HTTPException(status_code=401, detail="Invalid secret")

    st = body.state_code.strip().upper()
    if st not in AU_STATES:
        raise HTTPException(status_code=400, detail=f"Invalid state_code; use one of: {', '.join(sorted(AU_STATES))}")

    sub_norm = _normalize_suburb(body.suburb)
    if not sub_norm:
        raise HTTPException(status_code=400, detail="suburb is required")

    route = session.exec(
        select(MobileSuburbRoute)
        .where(MobileSuburbRoute.parent_account_id == parent.id)
        .where(MobileSuburbRoute.state_code == st)
        .where(MobileSuburbRoute.suburb_normalized == sub_norm)
    ).first()

    target_tid: UUID | None = route.target_tenant_id if route else parent.mobile_lead_default_tenant_id
    if not target_tid:
        raise HTTPException(
            status_code=422,
            detail="No suburb route for this location and no default site is set. Configure routes in Parent account → Website lead feed.",
        )

    if not _tenant_linked_to_parent(session, parent.id, target_tid):
        raise HTTPException(status_code=500, detail="Lead routing misconfigured: target site is not linked to this parent account")

    tenant = session.get(Tenant, target_tid)
    if not tenant:
        raise HTTPException(status_code=500, detail="Target site not found")

    plan_code = normalize_plan_code(tenant.plan_code)
    if "auto_key" not in PLAN_FEATURES.get(plan_code, set()):
        raise HTTPException(
            status_code=422,
            detail="Target site plan does not include Mobile Services (auto_key). Choose another site or upgrade the plan.",
        )

    ak_count = int(
        session.exec(select(func.count()).select_from(AutoKeyJob).where(AutoKeyJob.tenant_id == target_tid)).one()
    )
    ingest_ctx = AuthContext(tenant_id=target_tid, user_id=uuid4(), role="owner", plan_code=plan_code)
    enforce_plan_limit(ingest_ctx, "auto_key_job", ak_count)

    customer = _find_or_create_customer(session, target_tid, body)

    inferred = session.exec(
        select(CustomerAccountMembership)
        .where(CustomerAccountMembership.tenant_id == target_tid)
        .where(CustomerAccountMembership.customer_id == customer.id)
        .order_by(CustomerAccountMembership.created_at)
    ).first()
    customer_account_id = inferred.customer_account_id if inferred else None

    job_address_parts = [
        body.street_address.strip() if body.street_address else None,
        f"{body.suburb.strip()} {st}",
    ]
    job_address = ", ".join(p for p in job_address_parts if p)[:2000] or None

    desc_parts: list[str] = ["Submitted via website lead feed."]
    if body.key_service_result:
        desc_parts.append(f"Key checker / site result: {body.key_service_result.strip()}")
    if body.website_notes:
        desc_parts.append(body.website_notes.strip())
    description = "\n\n".join(desc_parts)[:8000]

    vehicle_bits = [body.vehicle_make, body.vehicle_model, body.registration_plate]
    title_vehicle = " · ".join(x.strip() for x in vehicle_bits if x and x.strip())
    title = f"Web lead — {body.customer_name.strip()}" + (f" ({title_vehicle})" if title_vehicle else "")

    job = AutoKeyJob(
        tenant_id=target_tid,
        customer_id=customer.id,
        customer_account_id=customer_account_id,
        job_number=_next_auto_key_job_number(session, target_tid),
        title=title[:500],
        description=description or None,
        vehicle_make=body.vehicle_make.strip()[:120] if body.vehicle_make else None,
        vehicle_model=body.vehicle_model.strip()[:120] if body.vehicle_model else None,
        registration_plate=body.registration_plate.strip()[:32] if body.registration_plate else None,
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

    session.add(
        TenantEventLog(
            tenant_id=target_tid,
            actor_user_id=None,
            actor_email="website-lead@ingest",
            entity_type="auto_key_job",
            entity_id=job.id,
            event_type="mobile_lead_quote_needed",
            event_summary=f"New website lead #{job.job_number} — quote required ({body.customer_name.strip()}, {body.suburb.strip()} {st})",
        )
    )
    session.commit()
    session.refresh(job)
    return {
        "job_id": str(job.id),
        "job_number": job.job_number,
        "tenant_id": str(target_tid),
        "message": "Job created; mobile services team can send the quote from the app inbox.",
    }
