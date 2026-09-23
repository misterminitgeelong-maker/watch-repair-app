"""Public customer self-service portal — no auth headers required."""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..config import settings
from ..database import get_session
from ..dispatch_utils import geocode_address
from ..limiter import limiter
from ..loyalty_utils import _get_tiers, _resolve_tier, _rolling_12m_spend, get_or_create_loyalty
from ..models import (
    Customer,
    CustomerLoyalty,
    CustomerPortalOtp,
    CustomerPortalSession,
    IntakeJob,
    Tenant,
    TenantEventLog,
)
from .intake_dispatch import create_auto_key_job_from_intake

router = APIRouter(prefix="/v1/public/portal", tags=["customer-portal"])

SESSION_TTL_DAYS = 30


def _resolve_tenant(slug: str, session: Session) -> Tenant:
    tenant = session.exec(select(Tenant).where(Tenant.slug == slug.lower())).first()
    if not tenant or not tenant.is_active:
        raise HTTPException(status_code=404, detail="Shop not found")
    return tenant


def _validate_session(token: str, tenant_id: UUID, session: Session) -> CustomerPortalSession:
    portal_session = session.exec(
        select(CustomerPortalSession)
        .where(CustomerPortalSession.token == token)
        .where(CustomerPortalSession.tenant_id == tenant_id)
    ).first()
    if not portal_session:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    if portal_session.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session expired")
    return portal_session


def _make_token() -> str:
    return uuid4().hex + uuid4().hex  # 64 chars


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

class LookupBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=300)
    phone: str = Field(..., min_length=6, max_length=80)


class VerifyBody(BaseModel):
    phone: str = Field(..., min_length=6, max_length=80)
    code: str = Field(..., min_length=4, max_length=12)


class LookupResponse(BaseModel):
    token: str
    customer_id: str
    name: str
    phone: Optional[str]
    email: Optional[str]


class IntakeJobOut(BaseModel):
    id: str
    customer_name: str
    job_address: str
    vehicle_make: Optional[str]
    vehicle_model: Optional[str]
    vehicle_year: Optional[str]
    description: Optional[str]
    status: str
    created_at: datetime


class LoyaltyOut(BaseModel):
    tier_name: str
    tier_label: str
    points_balance: int
    points_dollar_value: float
    rolling_12m_spend_cents: int


class ProfileResponse(BaseModel):
    customer_id: str
    name: str
    phone: Optional[str]
    email: Optional[str]
    intake_jobs: list[IntakeJobOut]
    loyalty: Optional[LoyaltyOut]


class BookBody(BaseModel):
    job_address: str = Field(..., min_length=5, max_length=2000)
    vehicle_make: Optional[str] = Field(default=None, max_length=120)
    vehicle_model: Optional[str] = Field(default=None, max_length=120)
    vehicle_year: Optional[str] = Field(default=None, max_length=10)
    registration_plate: Optional[str] = Field(default=None, max_length=32)
    description: Optional[str] = Field(default=None, max_length=4000)
    preferred_date: Optional[str] = Field(default=None, max_length=20)  # YYYY-MM-DD


class BookResponse(BaseModel):
    intake_job_id: str
    status: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

OTP_TTL_MINUTES = 10
OTP_MAX_ATTEMPTS = 5
OTP_MAX_PER_PHONE_PER_HOUR = 5


def _hash_code(tenant_id: UUID, phone: str, code: str) -> str:
    message = f"{tenant_id}:{phone}:{code}".encode()
    return hmac.new(settings.jwt_secret.encode(), message, hashlib.sha256).hexdigest()


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


@router.post("/{slug}/lookup")
@limiter.limit("5/minute")
async def portal_lookup(
    request: Request,
    slug: str,
    body: LookupBody,
    session: Session = Depends(get_session),
):
    """Text a sign-in code to the phone number; /verify exchanges it for a session.

    A phone number is not a password: this used to return a 30-day session for
    whoever typed one, showing that customer's details to anyone.
    """
    tenant = _resolve_tenant(slug, session)
    phone = body.phone.strip()

    if settings.app_env == "production" and not (
        settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_from_number
    ):
        raise HTTPException(status_code=503, detail="Phone sign-in isn't available for this shop yet.")

    now = datetime.now(timezone.utc)
    recent = session.exec(
        select(CustomerPortalOtp)
        .where(CustomerPortalOtp.tenant_id == tenant.id)
        .where(CustomerPortalOtp.phone == phone)
        .where(CustomerPortalOtp.created_at >= now - timedelta(hours=1))
    ).all()
    if len(recent) >= OTP_MAX_PER_PHONE_PER_HOUR:
        raise HTTPException(status_code=429, detail="Too many codes sent to this number. Try again later.")

    code = f"{secrets.randbelow(1_000_000):06d}"
    session.add(
        CustomerPortalOtp(
            tenant_id=tenant.id,
            phone=phone,
            name=body.name.strip(),
            code_hash=_hash_code(tenant.id, phone, code),
            expires_at=now + timedelta(minutes=OTP_TTL_MINUTES),
        )
    )
    session.commit()

    from ..sms import send_portal_login_code

    send_portal_login_code(session, tenant_id=tenant.id, to_phone=phone, shop_name=tenant.name, code=code)
    return {"sent": True, "expires_minutes": OTP_TTL_MINUTES}


@router.post("/{slug}/verify", response_model=LookupResponse)
@limiter.limit("10/minute")
async def portal_verify(
    request: Request,
    slug: str,
    body: VerifyBody,
    session: Session = Depends(get_session),
):
    """Exchange the texted code for a portal session."""
    tenant = _resolve_tenant(slug, session)
    phone = body.phone.strip()
    now = datetime.now(timezone.utc)

    otp = session.exec(
        select(CustomerPortalOtp)
        .where(CustomerPortalOtp.tenant_id == tenant.id)
        .where(CustomerPortalOtp.phone == phone)
        .where(CustomerPortalOtp.consumed_at.is_(None))  # type: ignore[union-attr]
        .order_by(CustomerPortalOtp.created_at.desc())  # type: ignore[attr-defined]
    ).first()
    if otp is None or _aware(otp.expires_at) < now or otp.attempts >= OTP_MAX_ATTEMPTS:
        raise HTTPException(status_code=401, detail="That code has expired. Request a new one.")

    otp.attempts += 1
    if not hmac.compare_digest(otp.code_hash, _hash_code(tenant.id, phone, body.code.strip())):
        session.add(otp)
        session.commit()
        raise HTTPException(status_code=401, detail="That code isn't right. Check the text and try again.")

    otp.consumed_at = now
    session.add(otp)

    customer = session.exec(
        select(Customer)
        .where(Customer.tenant_id == tenant.id)
        .where(Customer.phone == phone)
    ).first()
    if not customer:
        customer = Customer(
            tenant_id=tenant.id,
            full_name=otp.name,
            phone=phone,
        )
        session.add(customer)
        session.flush()

    token = _make_token()
    session.add(
        CustomerPortalSession(
            tenant_id=tenant.id,
            customer_id=customer.id,
            token=token,
            expires_at=now + timedelta(days=SESSION_TTL_DAYS),
        )
    )
    session.commit()

    return LookupResponse(
        token=token,
        customer_id=str(customer.id),
        name=customer.full_name,
        phone=customer.phone,
        email=customer.email,
    )


@router.get("/{slug}/profile", response_model=ProfileResponse)
async def portal_profile(
    slug: str,
    token: str = Query(...),
    session: Session = Depends(get_session),
):
    """Return the authenticated customer's profile, intake jobs, and loyalty."""
    tenant = _resolve_tenant(slug, session)
    portal_session = _validate_session(token, tenant.id, session)

    customer = session.get(Customer, portal_session.customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    intake_jobs = session.exec(
        select(IntakeJob)
        .where(IntakeJob.claimed_by_tenant_id == tenant.id)
        .where(IntakeJob.customer_phone == customer.phone)
        .order_by(IntakeJob.created_at.desc())
    ).all()

    loyalty_out: Optional[LoyaltyOut] = None
    loyalty = session.exec(
        select(CustomerLoyalty)
        .where(CustomerLoyalty.tenant_id == tenant.id)
        .where(CustomerLoyalty.customer_id == customer.id)
    ).first()
    if loyalty:
        tiers = _get_tiers(session)
        tier = next((t for t in tiers if t.id == loyalty.tier_id), tiers[0] if tiers else None)
        if tier:
            rolling = _rolling_12m_spend(session, loyalty.id)
            loyalty_out = LoyaltyOut(
                tier_name=tier.name,
                tier_label=tier.label,
                points_balance=loyalty.points_balance,
                points_dollar_value=round(loyalty.points_balance / 100, 2),
                rolling_12m_spend_cents=rolling,
            )

    return ProfileResponse(
        customer_id=str(customer.id),
        name=customer.full_name,
        phone=customer.phone,
        email=customer.email,
        intake_jobs=[
            IntakeJobOut(
                id=str(j.id),
                customer_name=j.customer_name,
                job_address=j.job_address,
                vehicle_make=j.vehicle_make,
                vehicle_model=j.vehicle_model,
                vehicle_year=j.vehicle_year,
                description=j.description,
                status=j.status,
                created_at=j.created_at,
            )
            for j in intake_jobs
        ],
        loyalty=loyalty_out,
    )


@router.post("/{slug}/book", response_model=BookResponse)
@limiter.limit("10/minute")
async def portal_book(
    request: Request,
    slug: str,
    body: BookBody,
    token: str = Query(...),
    session: Session = Depends(get_session),
):
    """Submit a mobile key job booking from the customer portal."""
    tenant = _resolve_tenant(slug, session)
    portal_session = _validate_session(token, tenant.id, session)

    customer = session.get(Customer, portal_session.customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    try:
        lat, lng = await geocode_address(body.job_address)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    description_parts = []
    if body.description:
        description_parts.append(body.description.strip())
    if body.preferred_date:
        description_parts.append(f"Preferred date: {body.preferred_date}")
    description = "\n".join(description_parts) if description_parts else None

    # A booking made through a shop's own portal belongs to that shop. It is recorded as an
    # intake already claimed by the shop (so the customer's profile can list it) and becomes an
    # auto-key job in the shop straight away; it never goes to the shared dispatch pool, which
    # is only for leads that don't belong to any shop yet (``/v1/public/intake``).
    intake_job = IntakeJob(
        customer_name=customer.full_name,
        customer_phone=customer.phone,
        customer_email=customer.email,
        job_address=body.job_address.strip(),
        job_lat=lat,
        job_lng=lng,
        vehicle_make=body.vehicle_make,
        vehicle_model=body.vehicle_model,
        vehicle_year=body.vehicle_year,
        registration_plate=body.registration_plate,
        description=description,
        status="claimed",
        current_ring=1,
        claimed_by_tenant_id=tenant.id,
        claimed_at=datetime.now(timezone.utc),
    )
    session.add(intake_job)
    session.flush()
    ak_job, _ = create_auto_key_job_from_intake(
        session, tenant.id, intake_job, title_prefix="Portal booking", lead_source="shop"
    )
    session.add(
        TenantEventLog(
            tenant_id=tenant.id,
            actor_email="customer-portal",
            entity_type="auto_key_job",
            entity_id=ak_job.id,
            event_type="portal_booking_received",
            event_summary=(
                f"New portal booking #{ak_job.job_number} from {customer.full_name} ({intake_job.job_address})"
            ),
        )
    )
    session.commit()
    session.refresh(intake_job)

    return BookResponse(
        intake_job_id=str(intake_job.id),
        status=intake_job.status,
    )
