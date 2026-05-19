"""Shop-initiated mobile operator booking requests (request → accept/decline)."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, func, select

from ..database import get_session
from ..dependencies import (
    AuthContext,
    PLAN_FEATURES,
    enforce_plan_limit,
    get_auth_context,
    normalize_plan_code,
    require_feature,
)
from ..models import (
    AutoKeyJob,
    Customer,
    CustomerAccountMembership,
    MobileSuburbRoute,
    ParentAccountEventLog,
    ParentAccountMembership,
    ShopMobileBookingCreate,
    ShopMobileBookingDeclineBody,
    ShopMobileBookingRead,
    ShopMobileBookingRequest,
    ShopMobileOperatorOption,
    Tenant,
    TenantEventLog,
    User,
)

router = APIRouter(prefix="/v1/shop-mobile-bookings", tags=["shop-mobile-bookings"])

AU_STATES = frozenset({"ACT", "NSW", "NT", "QLD", "SA", "TAS", "VIC", "WA"})
PENDING_EXPIRY_DAYS = 7


def _normalize_suburb(name: str) -> str:
    return " ".join(name.strip().lower().split())


def _digits_phone(p: str | None) -> str | None:
    if not p:
        return None
    d = "".join(c for c in p if c.isdigit())
    return d or None


def _parent_account_ids_for_tenant(session: Session, tenant_id: UUID) -> set[UUID]:
    rows = session.exec(
        select(ParentAccountMembership.parent_account_id)
        .where(ParentAccountMembership.tenant_id == tenant_id)
    ).all()
    return set(rows)


def _assert_parent_account_link(session: Session, shop_tid: UUID, operator_tid: UUID) -> UUID:
    shop_parents = _parent_account_ids_for_tenant(session, shop_tid)
    op_parents = _parent_account_ids_for_tenant(session, operator_tid)
    common = shop_parents & op_parents
    if not common:
        raise HTTPException(status_code=403, detail="Shop and operator are not under the same parent account")
    return next(iter(common))


BOOKABLE_OPERATOR_PLAN_CODES = frozenset(
    {
        "basic_auto_key",
        "basic_shoe_auto_key",
        "basic_watch_auto_key",
        "basic_all_tabs",
        "auto_key",
    }
)


def _tenant_has_auto_key(session: Session, tenant_id: UUID) -> bool:
    tenant = session.get(Tenant, tenant_id)
    if not tenant:
        return False
    plan = normalize_plan_code(tenant.plan_code)
    return "auto_key" in PLAN_FEATURES.get(plan, set())


def _tenant_is_bookable_operator(session: Session, tenant_id: UUID) -> bool:
    tenant = session.get(Tenant, tenant_id)
    if not tenant:
        return False
    plan = normalize_plan_code(tenant.plan_code)
    return plan in BOOKABLE_OPERATOR_PLAN_CODES


def _next_auto_key_job_number(session: Session, tenant_id: UUID) -> str:
    count = session.exec(select(func.count()).select_from(AutoKeyJob).where(AutoKeyJob.tenant_id == tenant_id)).one()
    return f"AK-{int(count) + 1:05d}"


def _find_or_create_customer(
    session: Session,
    tenant_id: UUID,
    *,
    customer_name: str,
    phone: str | None,
    email: str | None,
    address: str | None,
) -> Customer:
    phone_digits = _digits_phone(phone)
    if phone_digits:
        customers = session.exec(select(Customer).where(Customer.tenant_id == tenant_id)).all()
        for c in customers:
            if c.phone and _digits_phone(c.phone) == phone_digits:
                return c
    if email:
        em = email.strip().lower()
        existing = session.exec(
            select(Customer).where(Customer.tenant_id == tenant_id).where(Customer.email == em)
        ).first()
        if existing:
            return existing
    c = Customer(
        tenant_id=tenant_id,
        full_name=customer_name.strip()[:300],
        phone=phone.strip()[:80] if phone else None,
        email=email.strip().lower()[:320] if email else None,
        address=address[:2000] if address else None,
        notes="Created from shop mobile booking",
    )
    session.add(c)
    session.flush()
    return c


def _maybe_expire_pending(session: Session, row: ShopMobileBookingRequest) -> bool:
    if row.status != "pending":
        return False
    created = row.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    if created + timedelta(days=PENDING_EXPIRY_DAYS) >= datetime.now(timezone.utc):
        return False
    row.status = "expired"
    session.add(row)
    return True


def _schedule_conflict_warning(
    session: Session, operator_tid: UUID, preferred_at: datetime | None
) -> str | None:
    if not preferred_at:
        return None
    pref = preferred_at
    if pref.tzinfo is None:
        pref = pref.replace(tzinfo=timezone.utc)
    day_start = pref.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    count = int(
        session.exec(
            select(func.count())
            .select_from(AutoKeyJob)
            .where(AutoKeyJob.tenant_id == operator_tid)
            .where(AutoKeyJob.scheduled_at.isnot(None))  # type: ignore[union-attr]
            .where(AutoKeyJob.scheduled_at >= day_start)  # type: ignore[operator]
            .where(AutoKeyJob.scheduled_at < day_end)  # type: ignore[operator]
        ).one()
    )
    if count == 0:
        return None
    noun = "job" if count == 1 else "jobs"
    return (
        f"This operator already has {count} scheduled {noun} on "
        f"{day_start.strftime('%Y-%m-%d')}. Review the calendar before accepting."
    )


def _to_read(
    session: Session,
    row: ShopMobileBookingRequest,
    *,
    schedule_conflict_warning: str | None = None,
) -> ShopMobileBookingRead:
    shop = session.get(Tenant, row.requesting_tenant_id)
    op = session.get(Tenant, row.target_operator_tenant_id)
    job_number: str | None = None
    job_status: str | None = None
    job_scheduled_at: datetime | None = None
    if row.resulting_auto_key_job_id:
        job = session.get(AutoKeyJob, row.resulting_auto_key_job_id)
        if job:
            job_number = job.job_number
            if row.status == "accepted":
                job_status = job.status
                job_scheduled_at = job.scheduled_at
    return ShopMobileBookingRead(
        id=row.id,
        parent_account_id=row.parent_account_id,
        requesting_tenant_id=row.requesting_tenant_id,
        requesting_shop_name=shop.name if shop else "Unknown shop",
        target_operator_tenant_id=row.target_operator_tenant_id,
        target_operator_name=op.name if op else "Unknown operator",
        created_by_user_id=row.created_by_user_id,
        status=row.status,  # type: ignore[arg-type]
        customer_name=row.customer_name,
        phone=row.phone,
        email=row.email,
        vehicle_make=row.vehicle_make,
        vehicle_model=row.vehicle_model,
        registration_plate=row.registration_plate,
        visit_location_type=row.visit_location_type,  # type: ignore[arg-type]
        job_address=row.job_address,
        preferred_scheduled_at=row.preferred_scheduled_at,
        job_type=row.job_type,
        notes=row.notes,
        operator_response_at=row.operator_response_at,
        operator_response_by_user_id=row.operator_response_by_user_id,
        decline_reason=row.decline_reason,
        resulting_auto_key_job_id=row.resulting_auto_key_job_id,
        resulting_job_number=job_number,
        job_status=job_status,
        job_scheduled_at=job_scheduled_at,
        schedule_conflict_warning=schedule_conflict_warning,
        created_at=row.created_at,
    )


def _get_booking_or_404(session: Session, booking_id: UUID) -> ShopMobileBookingRequest:
    row = session.get(ShopMobileBookingRequest, booking_id)
    if not row:
        raise HTTPException(status_code=404, detail="Booking request not found")
    return row


def _assert_can_view(auth: AuthContext, row: ShopMobileBookingRequest) -> None:
    if auth.tenant_id in (row.requesting_tenant_id, row.target_operator_tenant_id):
        return
    raise HTTPException(status_code=403, detail="Not allowed to view this booking request")


@router.get("/operators", response_model=list[ShopMobileOperatorOption])
def list_operators(
    auth: AuthContext = Depends(require_feature("shop_mobile_booking")),
    session: Session = Depends(get_session),
):
    parent_ids = _parent_account_ids_for_tenant(session, auth.tenant_id)
    if not parent_ids:
        raise HTTPException(status_code=403, detail="Tenant is not linked to a parent account")

    memberships = session.exec(
        select(ParentAccountMembership).where(ParentAccountMembership.parent_account_id.in_(parent_ids))  # type: ignore[attr-defined]
    ).all()
    options: list[ShopMobileOperatorOption] = []
    seen: set[UUID] = set()
    for m in memberships:
        if m.tenant_id == auth.tenant_id or m.tenant_id in seen:
            continue
        if not _tenant_is_bookable_operator(session, m.tenant_id):
            continue
        tenant = session.get(Tenant, m.tenant_id)
        if not tenant:
            continue
        seen.add(m.tenant_id)
        options.append(
            ShopMobileOperatorOption(
                tenant_id=tenant.id,
                tenant_slug=tenant.slug,
                tenant_name=tenant.name,
                plan_code=normalize_plan_code(tenant.plan_code),
            )
        )
    return sorted(options, key=lambda o: o.tenant_name.lower())


@router.get("/suggest-operator", response_model=ShopMobileOperatorOption | None)
def suggest_operator(
    suburb: str = Query(..., min_length=1),
    state_code: str = Query(..., min_length=2, max_length=8),
    auth: AuthContext = Depends(require_feature("shop_mobile_booking")),
    session: Session = Depends(get_session),
):
    parent_ids = _parent_account_ids_for_tenant(session, auth.tenant_id)
    if not parent_ids:
        return None

    st = state_code.strip().upper()
    if st not in AU_STATES:
        raise HTTPException(status_code=400, detail=f"Invalid state_code; use one of: {', '.join(sorted(AU_STATES))}")

    sub_norm = _normalize_suburb(suburb)
    if not sub_norm:
        raise HTTPException(status_code=400, detail="suburb is required")

    route = session.exec(
        select(MobileSuburbRoute)
        .where(MobileSuburbRoute.parent_account_id.in_(parent_ids))  # type: ignore[attr-defined]
        .where(MobileSuburbRoute.state_code == st)
        .where(MobileSuburbRoute.suburb_normalized == sub_norm)
    ).first()
    if not route or not _tenant_is_bookable_operator(session, route.target_tenant_id):
        return None

    tenant = session.get(Tenant, route.target_tenant_id)
    if not tenant:
        return None
    return ShopMobileOperatorOption(
        tenant_id=tenant.id,
        tenant_slug=tenant.slug,
        tenant_name=tenant.name,
        plan_code=normalize_plan_code(tenant.plan_code),
    )


@router.post("", response_model=ShopMobileBookingRead, status_code=201)
def create_booking(
    body: ShopMobileBookingCreate,
    auth: AuthContext = Depends(require_feature("shop_mobile_booking")),
    session: Session = Depends(get_session),
):
    if body.target_operator_tenant_id == auth.tenant_id:
        raise HTTPException(status_code=400, detail="Cannot book your own tenant as the operator")

    parent_id = _assert_parent_account_link(session, auth.tenant_id, body.target_operator_tenant_id)
    if not _tenant_is_bookable_operator(session, body.target_operator_tenant_id):
        raise HTTPException(status_code=400, detail="Target tenant is not a mobile services operator")

    shop = session.get(Tenant, auth.tenant_id)
    job_address = body.job_address.strip()
    if body.visit_location_type == "at_shop":
        if shop and getattr(shop, "business_address", None):
            job_address = shop.business_address.strip()[:2000]
        elif shop and not job_address:
            job_address = f"{shop.name} (shop location)"

    row = ShopMobileBookingRequest(
        parent_account_id=parent_id,
        requesting_tenant_id=auth.tenant_id,
        target_operator_tenant_id=body.target_operator_tenant_id,
        created_by_user_id=auth.user_id,
        status="pending",
        customer_name=body.customer_name.strip(),
        phone=body.phone.strip()[:80] if body.phone else None,
        email=body.email.strip().lower()[:320] if body.email else None,
        vehicle_make=body.vehicle_make.strip()[:120] if body.vehicle_make else None,
        vehicle_model=body.vehicle_model.strip()[:120] if body.vehicle_model else None,
        registration_plate=body.registration_plate.strip()[:32] if body.registration_plate else None,
        visit_location_type=body.visit_location_type,
        job_address=job_address[:2000],
        preferred_scheduled_at=body.preferred_scheduled_at,
        job_type=body.job_type.strip()[:120] if body.job_type else None,
        notes=body.notes.strip()[:4000] if body.notes else None,
    )
    session.add(row)
    session.flush()

    actor = session.get(User, auth.user_id)
    shop_name = shop.name if shop else "Shop"
    session.add(
        TenantEventLog(
            tenant_id=body.target_operator_tenant_id,
            actor_user_id=auth.user_id,
            actor_email=actor.email if actor else None,
            entity_type="shop_mobile_booking",
            entity_id=row.id,
            event_type="shop_booking_pending",
            event_summary=f"New shop booking from {shop_name} — {body.customer_name.strip()} (pending accept)",
        )
    )
    session.add(
        ParentAccountEventLog(
            parent_account_id=parent_id,
            tenant_id=auth.tenant_id,
            actor_user_id=auth.user_id,
            actor_email=actor.email if actor else None,
            event_type="shop_booking_created",
            event_summary=f"{shop_name} sent mobile booking for {body.customer_name.strip()} (pending)",
        )
    )
    # Operator SMS skipped: owner users have no phone field; inbox poll via shop_booking_pending event.
    session.commit()
    session.refresh(row)
    return _to_read(session, row)


@router.get("", response_model=list[ShopMobileBookingRead])
def list_bookings(
    status: str | None = Query(default=None),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    if _tenant_has_auto_key(session, auth.tenant_id):
        q = select(ShopMobileBookingRequest).where(
            ShopMobileBookingRequest.target_operator_tenant_id == auth.tenant_id
        )
    elif "shop_mobile_booking" in PLAN_FEATURES.get(auth.plan_code, set()) or auth.role == "platform_admin":
        q = select(ShopMobileBookingRequest).where(
            ShopMobileBookingRequest.requesting_tenant_id == auth.tenant_id
        )
    else:
        raise HTTPException(status_code=403, detail="Not allowed to list booking requests")

    if status:
        q = q.where(ShopMobileBookingRequest.status == status.strip().lower())
    q = q.order_by(ShopMobileBookingRequest.created_at.desc())
    rows = session.exec(q).all()
    expired_any = False
    for r in rows:
        if _maybe_expire_pending(session, r):
            expired_any = True
    if expired_any:
        session.commit()
    return [_to_read(session, r) for r in rows]


@router.get("/{booking_id}", response_model=ShopMobileBookingRead)
def get_booking(
    booking_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    row = _get_booking_or_404(session, booking_id)
    _assert_can_view(auth, row)
    if _maybe_expire_pending(session, row):
        session.commit()
        session.refresh(row)
    return _to_read(session, row)


@router.post("/{booking_id}/cancel", response_model=ShopMobileBookingRead)
def cancel_booking(
    booking_id: UUID,
    auth: AuthContext = Depends(require_feature("shop_mobile_booking")),
    session: Session = Depends(get_session),
):
    row = _get_booking_or_404(session, booking_id)
    if row.requesting_tenant_id != auth.tenant_id:
        raise HTTPException(status_code=403, detail="Only the requesting shop can cancel")
    if row.status != "pending":
        raise HTTPException(status_code=400, detail="Only pending requests can be cancelled")
    row.status = "cancelled"
    session.add(row)
    session.commit()
    session.refresh(row)
    return _to_read(session, row)


@router.post("/{booking_id}/decline", response_model=ShopMobileBookingRead)
def decline_booking(
    booking_id: UUID,
    body: ShopMobileBookingDeclineBody,
    auth: AuthContext = Depends(require_feature("auto_key")),
    session: Session = Depends(get_session),
):
    row = _get_booking_or_404(session, booking_id)
    if row.target_operator_tenant_id != auth.tenant_id:
        raise HTTPException(status_code=403, detail="Only the target operator can decline")
    if row.status != "pending":
        raise HTTPException(status_code=400, detail="Only pending requests can be declined")

    now = datetime.now(timezone.utc)
    row.status = "declined"
    row.operator_response_at = now
    row.operator_response_by_user_id = auth.user_id
    row.decline_reason = body.decline_reason.strip()[:2000] if body.decline_reason else None
    session.add(row)

    actor = session.get(User, auth.user_id)
    session.add(
        TenantEventLog(
            tenant_id=row.requesting_tenant_id,
            actor_user_id=auth.user_id,
            actor_email=actor.email if actor else None,
            entity_type="shop_mobile_booking",
            entity_id=row.id,
            event_type="shop_booking_declined",
            event_summary=f"Operator declined shop booking for {row.customer_name}",
        )
    )
    session.add(
        ParentAccountEventLog(
            parent_account_id=row.parent_account_id,
            tenant_id=row.target_operator_tenant_id,
            actor_user_id=auth.user_id,
            actor_email=actor.email if actor else None,
            event_type="shop_booking_declined",
            event_summary=f"Declined shop booking for {row.customer_name}",
        )
    )
    session.commit()
    session.refresh(row)
    return _to_read(session, row)


@router.post("/{booking_id}/accept", response_model=ShopMobileBookingRead)
def accept_booking(
    booking_id: UUID,
    auth: AuthContext = Depends(require_feature("auto_key")),
    session: Session = Depends(get_session),
):
    row = _get_booking_or_404(session, booking_id)
    if row.target_operator_tenant_id != auth.tenant_id:
        raise HTTPException(status_code=403, detail="Only the target operator can accept")
    if row.status != "pending":
        raise HTTPException(status_code=400, detail="Only pending requests can be accepted")
    if _maybe_expire_pending(session, row):
        session.commit()
        raise HTTPException(status_code=400, detail="Booking request has expired")

    conflict_warning = _schedule_conflict_warning(session, row.target_operator_tenant_id, row.preferred_scheduled_at)

    operator_tid = row.target_operator_tenant_id
    ak_count = int(
        session.exec(select(func.count()).select_from(AutoKeyJob).where(AutoKeyJob.tenant_id == operator_tid)).one()
    )
    enforce_plan_limit(auth, "auto_key_job", ak_count)

    shop = session.get(Tenant, row.requesting_tenant_id)
    shop_name = shop.name if shop else "Shop"

    customer = _find_or_create_customer(
        session,
        operator_tid,
        customer_name=row.customer_name,
        phone=row.phone,
        email=row.email,
        address=row.job_address,
    )
    inferred = session.exec(
        select(CustomerAccountMembership)
        .where(CustomerAccountMembership.tenant_id == operator_tid)
        .where(CustomerAccountMembership.customer_id == customer.id)
        .order_by(CustomerAccountMembership.created_at)
    ).first()
    customer_account_id = inferred.customer_account_id if inferred else None

    visit_label = "At shop" if row.visit_location_type == "at_shop" else "Customer site"
    desc_parts = [
        f"Shop booking from {shop_name}.",
        f"Visit: {visit_label}.",
    ]
    if row.notes:
        desc_parts.append(row.notes)
    description = "\n\n".join(desc_parts)[:8000]

    vehicle_bits = [row.vehicle_make, row.vehicle_model, row.registration_plate]
    title_vehicle = " · ".join(x.strip() for x in vehicle_bits if x and x.strip())
    title = f"Shop booking — {row.customer_name}" + (f" ({title_vehicle})" if title_vehicle else "")

    job = AutoKeyJob(
        tenant_id=operator_tid,
        customer_id=customer.id,
        customer_account_id=customer_account_id,
        job_number=_next_auto_key_job_number(session, operator_tid),
        title=title[:500],
        description=description or None,
        vehicle_make=row.vehicle_make,
        vehicle_model=row.vehicle_model,
        registration_plate=row.registration_plate,
        job_address=row.job_address,
        job_type=row.job_type or "Diagnostic",
        scheduled_at=row.preferred_scheduled_at,
        status="awaiting_quote",
        priority="normal",
        key_quantity=1,
        programming_status="pending",
        deposit_cents=0,
        cost_cents=0,
        commission_lead_source="shop_referred",
        referring_shop_tenant_id=row.requesting_tenant_id,
        shop_mobile_booking_request_id=row.id,
    )
    session.add(job)
    session.flush()

    now = datetime.now(timezone.utc)
    row.status = "accepted"
    row.operator_response_at = now
    row.operator_response_by_user_id = auth.user_id
    row.resulting_auto_key_job_id = job.id
    session.add(row)

    actor = session.get(User, auth.user_id)
    session.add(
        TenantEventLog(
            tenant_id=operator_tid,
            actor_user_id=auth.user_id,
            actor_email=actor.email if actor else None,
            entity_type="auto_key_job",
            entity_id=job.id,
            event_type="shop_booking_accepted",
            event_summary=f"Accepted shop booking #{job.job_number} from {shop_name} ({row.customer_name})",
        )
    )
    session.add(
        TenantEventLog(
            tenant_id=row.requesting_tenant_id,
            actor_user_id=auth.user_id,
            actor_email=actor.email if actor else None,
            entity_type="shop_mobile_booking",
            entity_id=row.id,
            event_type="shop_booking_accepted",
            event_summary=f"Operator accepted booking — job #{job.job_number}",
        )
    )
    session.add(
        ParentAccountEventLog(
            parent_account_id=row.parent_account_id,
            tenant_id=operator_tid,
            actor_user_id=auth.user_id,
            actor_email=actor.email if actor else None,
            event_type="shop_booking_accepted",
            event_summary=f"{shop_name} booking accepted as job #{job.job_number}",
        )
    )
    session.commit()
    session.refresh(row)
    return _to_read(session, row, schedule_conflict_warning=conflict_warning)
