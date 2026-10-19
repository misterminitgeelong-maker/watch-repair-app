"""Ring-map dispatch: public intake form + operator job pool + claim endpoint."""

import re
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from sqlalchemy import update as sa_update
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel, Field
from sqlmodel import Session, col, func, select

from ..database import get_session
from ..dependencies import (
    PLAN_FEATURES,
    AuthContext,
    enforce_plan_limit,
    get_auth_context,
    normalize_plan_code,
)
from ..dispatch_utils import geocode_address, operator_ring_for_job
from ..limiter import limiter
from ..parent_network import (
    mobile_dispatch_parent_ids_for_tenant,
    parent_ids_for_tenant,
    tenant_is_live,
    tenant_is_operator,
)
from ..public_dedupe import find_existing, make_ref
from ..models import AutoKeyJob, Customer, IntakeJob, ParentAccount, Tenant, TenantEventLog

router = APIRouter(tags=["intake-dispatch"])


def _require_dispatch_enabled(session: Session, tenant_id: UUID) -> None:
    tenant = session.get(Tenant, tenant_id)
    if not tenant or not tenant.is_active or tenant.mobile_dispatch_paused or tenant.merged_into_tenant_id:
        raise HTTPException(status_code=409, detail="New dispatch is paused for this shop")
    # Same rule as website-lead routing: only operators whose owner accepted the invite.
    if not tenant_is_live(session, tenant_id):
        raise HTTPException(status_code=409, detail="Dispatch opens once your account invite is accepted")


def _operator_parent_ids(session: Session, tenant_id: UUID) -> list[UUID]:
    """HQ networks this operator belongs to (site link or explicit dispatch consent)."""
    return list(dict.fromkeys(
        parent_ids_for_tenant(session, tenant_id) + mobile_dispatch_parent_ids_for_tenant(session, tenant_id)
    ))


_AU_STATES = r"(?:NSW|VIC|QLD|SA|WA|TAS|NT|ACT)"
_AREA_RE = re.compile(rf"([A-Za-z][A-Za-z .'\-]*?)\s*,?\s+({_AU_STATES})\s+(\d{{4}})\s*$", re.IGNORECASE)


def redact_job_address(address: str | None) -> dict[str, str | None]:
    """Suburb / postcode only. Street, number and anything else is withheld pre-claim."""
    text = (address or "").strip().rstrip(",")
    m = _AREA_RE.search(text)
    if m:
        suburb = m.group(1).split(",")[-1].strip()
        return {"suburb": suburb, "state": m.group(2).upper(), "postcode": m.group(3)}
    pc = re.search(r"\b(\d{4})\s*$", text)
    if pc:
        before = text[: pc.start()].rstrip(", ")
        return {"suburb": before.split(",")[-1].strip() or None, "state": None, "postcode": pc.group(1)}
    return {"suburb": None, "state": None, "postcode": None}

# ---------------------------------------------------------------------------
# Public intake endpoint (no auth — embedded on customer-facing website)
# ---------------------------------------------------------------------------


class IntakeSubmitBody(BaseModel):
    customer_name: str = Field(..., min_length=1, max_length=300)
    customer_phone: str | None = Field(default=None, max_length=80)
    customer_email: str | None = Field(default=None, max_length=320)
    job_address: str = Field(..., min_length=5, max_length=2000)
    vehicle_make: str | None = Field(default=None, max_length=120)
    vehicle_model: str | None = Field(default=None, max_length=120)
    vehicle_year: str | None = Field(default=None, max_length=10)
    registration_plate: str | None = Field(default=None, max_length=32)
    description: str | None = Field(default=None, max_length=4000)
    #: Which HQ network's pool this goes to. Optional when only one HQ exists.
    ingest_public_id: UUID | None = None


@router.post("/v1/public/intake")
@limiter.limit("30/minute")
async def submit_public_intake(
    request: Request,
    response: Response,
    body: IntakeSubmitBody,
    session: Session = Depends(get_session),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=200),
):
    """Accept a job from the public-facing intake form. Geocodes the address and places the job in the pool.

    Idempotent: a repeat of the same submission (same Idempotency-Key, or same normalised
    payload within 10 minutes) returns the original job and creates nothing new.
    """
    if body.ingest_public_id is not None:
        parent = session.exec(
            select(ParentAccount).where(ParentAccount.mobile_lead_ingest_public_id == body.ingest_public_id)
        ).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Unknown intake form")
        parent_id: UUID | None = parent.id
    else:
        # Single-HQ deployments need no id; with several the job is unscoped and
        # stays out of every pool until an admin assigns it.
        parents = session.exec(select(ParentAccount.id).limit(2)).all()
        parent_id = parents[0] if len(parents) == 1 else None

    ref, is_key = make_ref(
        parent_id, idempotency_key, body.model_dump(mode="json", exclude={"ingest_public_id"})
    )
    existing = find_existing(session, IntakeJob, ref, is_client_key=is_key)
    if existing is not None:
        response.headers["X-Idempotent-Replay"] = "true"
        return {"id": str(existing.id), "message": "Job submitted. A technician will be in touch shortly."}
    try:
        lat, lng = await geocode_address(body.job_address)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    job = IntakeJob(
        customer_name=body.customer_name.strip(),
        customer_phone=body.customer_phone.strip() if body.customer_phone else None,
        customer_email=body.customer_email.strip().lower() if body.customer_email else None,
        job_address=body.job_address.strip(),
        job_lat=lat,
        job_lng=lng,
        vehicle_make=body.vehicle_make.strip() if body.vehicle_make else None,
        vehicle_model=body.vehicle_model.strip() if body.vehicle_model else None,
        vehicle_year=body.vehicle_year.strip() if body.vehicle_year else None,
        registration_plate=body.registration_plate.strip() if body.registration_plate else None,
        description=body.description.strip() if body.description else None,
        parent_account_id=parent_id,
        external_ref=ref,
    )
    session.add(job)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = find_existing(session, IntakeJob, ref, is_client_key=is_key)
        if existing is None:
            raise
        response.headers["X-Idempotent-Replay"] = "true"
        return {"id": str(existing.id), "message": "Job submitted. A technician will be in touch shortly."}
    session.refresh(job)
    return {"id": str(job.id), "message": "Job submitted. A technician will be in touch shortly."}


# ---------------------------------------------------------------------------
# Operator pool: list unclaimed jobs visible within this operator's rings
# ---------------------------------------------------------------------------


@router.get("/v1/pool")
def list_pool(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
    max_ring: int | None = None,
):
    """Return unclaimed IntakeJobs visible to the authenticated operator, sorted by ring then created_at."""
    _require_auto_key(auth)

    _require_dispatch_enabled(session, auth.tenant_id)

    tenant = session.get(Tenant, auth.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    parent_ids = _operator_parent_ids(session, auth.tenant_id)
    if not parent_ids:
        return []
    unclaimed = session.exec(
        select(IntakeJob)
        .where(IntakeJob.status == "unclaimed")
        .where(col(IntakeJob.parent_account_id).in_(parent_ids))
        .order_by(IntakeJob.created_at)
    ).all()

    results = []
    for job in unclaimed:
        ring = operator_ring_for_job(
            tenant.base_lat, tenant.base_lng,
            job.job_lat, job.job_lng,
            tenant.ring_radius_km or 10,
        )
        if ring is None:
            continue
        if max_ring is not None and ring > max_ring:
            continue
        # Pre-acceptance view: area + job type + vehicle make/model only. Name, street
        # address, plate, phone and free-text notes are released by /claim.
        results.append({
            "id": str(job.id),
            "job_type": "Mobile Key",
            **redact_job_address(job.job_address),
            "vehicle_make": job.vehicle_make,
            "vehicle_model": job.vehicle_model,
            "vehicle_year": job.vehicle_year,
            "ring": ring,
            "created_at": job.created_at.isoformat(),
        })

    results.sort(key=lambda r: (r["ring"], r["created_at"]))
    return results


# ---------------------------------------------------------------------------
# Claim: atomically assign the job to this operator and create the AutoKeyJob
# ---------------------------------------------------------------------------


@router.post("/v1/pool/{job_id}/claim")
def claim_pool_job(
    job_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    """Claim an unclaimed IntakeJob. Creates a Customer + AutoKeyJob in the operator's tenant."""
    _require_auto_key(auth)

    _require_dispatch_enabled(session, auth.tenant_id)

    job = session.get(IntakeJob, job_id)
    if not job or job.parent_account_id is None or job.parent_account_id not in _operator_parent_ids(
        session, auth.tenant_id
    ):
        # Other HQs' jobs are indistinguishable from jobs that do not exist.
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "unclaimed":
        raise HTTPException(status_code=409, detail="Job has already been claimed.")

    ak_count = int(
        session.exec(
            select(func.count()).select_from(AutoKeyJob).where(AutoKeyJob.tenant_id == auth.tenant_id)
        ).one()
    )
    enforce_plan_limit(auth, "auto_key_job", ak_count)

    # Claim with one conditional UPDATE so two operators tapping at once can't
    # both win: whoever's statement runs second matches no row.
    claimed = session.exec(
        sa_update(IntakeJob)
        .where(IntakeJob.id == job.id)
        .where(IntakeJob.status == "unclaimed")
        .values(status="claimed", claimed_by_tenant_id=auth.tenant_id, claimed_at=datetime.now(timezone.utc))
    )
    if claimed.rowcount != 1:
        session.rollback()
        raise HTTPException(status_code=409, detail="Job has already been claimed.")
    session.refresh(job)

    ak_job, customer = create_auto_key_job_from_intake(
        session, auth.tenant_id, job, title_prefix="Pool job", lead_source="minit_sourced"
    )
    ak_number = ak_job.job_number

    session.add(
        TenantEventLog(
            tenant_id=auth.tenant_id,
            actor_user_id=auth.user_id,
            actor_email="dispatch-pool",
            entity_type="auto_key_job",
            entity_id=ak_job.id,
            event_type="pool_job_claimed",
            event_summary=f"Claimed pool job #{ak_number} from dispatch pool ({job.customer_name}, {job.job_address})",
        )
    )

    session.commit()
    session.refresh(ak_job)
    return {
        "message": "Job claimed.",
        "auto_key_job_id": str(ak_job.id),
        "job_number": ak_job.job_number,
        "customer_id": str(customer.id),
        # Released only now that the job is this operator's.
        "customer_name": job.customer_name,
        "customer_phone": job.customer_phone,
        "job_address": job.job_address,
        "registration_plate": job.registration_plate,
    }


# ---------------------------------------------------------------------------
# Update base location for the operator's tenant
# ---------------------------------------------------------------------------


class SetBaseLocationBody(BaseModel):
    address: str = Field(..., min_length=5, max_length=2000)
    ring_radius_km: int = Field(default=10, ge=1, le=200)


@router.post("/v1/settings/dispatch-base-location")
async def set_base_location(
    request: Request,
    body: SetBaseLocationBody,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    """Geocode an address and save it as the operator's base location for ring-map routing."""
    _require_auto_key(auth)
    if auth.role not in ("owner", "manager", "platform_admin"):
        raise HTTPException(status_code=403, detail="Owner or manager required")
    if tenant_is_operator(session, auth.tenant_id):
        raise HTTPException(status_code=403, detail="Your base location and rings are set by HQ")

    try:
        lat, lng = await geocode_address(body.address)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    tenant = session.get(Tenant, auth.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    tenant.base_lat = lat
    tenant.base_lng = lng
    tenant.ring_radius_km = body.ring_radius_km
    session.add(tenant)
    session.commit()
    return {"base_lat": lat, "base_lng": lng, "ring_radius_km": body.ring_radius_km}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_auto_key(auth: AuthContext) -> None:
    if auth.role == "platform_admin":
        return
    features = PLAN_FEATURES.get(auth.plan_code, set())
    if "auto_key" not in features:
        raise HTTPException(status_code=403, detail="Mobile Services plan required")


def create_auto_key_job_from_intake(
    session: Session,
    tenant_id: UUID,
    job: IntakeJob,
    *,
    title_prefix: str,
    lead_source: str,
) -> tuple[AutoKeyJob, Customer]:
    """Turn an intake request into a customer + auto-key job inside ``tenant_id`` and link them.

    Caller is responsible for committing.
    """
    customer = _find_or_create_customer(session, tenant_id, job)

    ak_number = _next_auto_key_job_number(session, tenant_id)
    vehicle_bits = [job.vehicle_make, job.vehicle_model, job.registration_plate]
    title_vehicle = " · ".join(x.strip() for x in vehicle_bits if x and x.strip())
    title = f"{title_prefix} — {job.customer_name}" + (f" ({title_vehicle})" if title_vehicle else "")

    ak_job = AutoKeyJob(
        tenant_id=tenant_id,
        customer_id=customer.id,
        job_number=ak_number,
        title=title[:500],
        description=job.description,
        vehicle_make=job.vehicle_make,
        vehicle_model=job.vehicle_model,
        vehicle_year=int(job.vehicle_year) if job.vehicle_year and job.vehicle_year.isdigit() else None,
        registration_plate=job.registration_plate,
        job_address=job.job_address,
        job_type="Mobile Key",
        status="awaiting_quote",
        priority="normal",
        key_quantity=1,
        programming_status="pending",
        deposit_cents=0,
        cost_cents=0,
        commission_lead_source=lead_source,
    )
    session.add(ak_job)
    session.flush()

    job.resulting_job_id = ak_job.id
    session.add(job)
    return ak_job, customer


def _find_or_create_customer(session: Session, tenant_id: UUID, job: IntakeJob) -> Customer:
    if job.customer_phone:
        digits = "".join(c for c in job.customer_phone if c.isdigit())
        if digits:
            for c in session.exec(select(Customer).where(Customer.tenant_id == tenant_id)).all():
                if c.phone and "".join(ch for ch in c.phone if ch.isdigit()) == digits:
                    return c

    if job.customer_email:
        existing = session.exec(
            select(Customer)
            .where(Customer.tenant_id == tenant_id)
            .where(Customer.email == job.customer_email)
        ).first()
        if existing:
            return existing

    customer = Customer(
        tenant_id=tenant_id,
        full_name=job.customer_name,
        phone=job.customer_phone,
        email=job.customer_email,
        address=job.job_address,
        notes="Created from dispatch pool job",
    )
    session.add(customer)
    session.flush()
    return customer


def _next_auto_key_job_number(session: Session, tenant_id: UUID) -> str:
    count = session.exec(
        select(func.count()).select_from(AutoKeyJob).where(AutoKeyJob.tenant_id == tenant_id)
    ).one()
    return f"AK-{int(count) + 1:05d}"
