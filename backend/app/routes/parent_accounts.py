from calendar import monthrange
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, func, select

from ..database import get_session
from ..dependencies import (
    AuthContext,
    PLAN_FEATURES,
    VALID_PLAN_CODES,
    get_auth_context,
    normalize_plan_code,
    require_feature,
    require_owner,
)
from ..minit_branding import MINIT_HQ_PLAN, tenant_product
from ..minit_provision import import_minit_shops
from ..minit_shops import parse_minit_shops_xlsx_detailed
from ..models import (
    MobileSuburbRoute,
    MobileSuburbRouteCreateRequest,
    MobileSuburbRouteRead,
    ParentAccount,
    ParentAccountCreateTenantRequest,
    ParentImportShopsResponse,
    ParentProvisionShopRequest,
    ParentAccountEventLog,
    ParentAccountEventLogRead,
    ParentAccountLinkTenantRequest,
    ParentAccountMembership,
    ParentAccountSiteRead,
    ParentAccountSummaryResponse,
    ParentMobileLeadDefaultTenantBody,
    ParentMobileLeadWebhookSecretBody,
    ShopBookingUsageResponse,
    ShopBookingUsageShopBreakdown,
    ShopMobileBookingRequest,
    Tenant,
    User,
)
from ..security import hash_password
from ..minit_shops import MinitShopRow, tenant_slug_for_shop
from ..shop_number import (
    assert_shop_number_unique_in_parent,
    format_tenant_label,
    normalize_shop_number,
    validate_shop_number_format,
)

router = APIRouter(
    prefix="/v1/parent-accounts",
    tags=["parent-accounts"],
    dependencies=[Depends(require_feature("multi_site"))],
)

AU_STATES = frozenset({"ACT", "NSW", "NT", "QLD", "SA", "TAS", "VIC", "WA"})
MAX_IMPORT_SHOPS_XLSX_BYTES = 5 * 1024 * 1024
_ALLOWED_XLSX_SUFFIXES = frozenset({".xlsx", ".xlsm"})


def _normalize_suburb(name: str) -> str:
    return " ".join(name.strip().lower().split())


def _require_minit_hq(auth: AuthContext, session: Session) -> Tenant:
    tenant = session.get(Tenant, auth.tenant_id)
    if not tenant:
        raise HTTPException(status_code=401, detail="Invalid token")
    if normalize_plan_code(auth.plan_code) != MINIT_HQ_PLAN:
        raise HTTPException(status_code=403, detail="Minit HQ plan required")
    if tenant_product(tenant.slug) != "minit":
        raise HTTPException(status_code=403, detail="Minit product required")
    return tenant


def _get_parent_account_for_user(session: Session, user: User) -> ParentAccount:
    parent = session.exec(
        select(ParentAccount).where(ParentAccount.owner_email == user.email)
    ).first()
    if not parent:
        raise HTTPException(status_code=404, detail="Parent account not found")
    return parent


def _to_summary(session: Session, parent: ParentAccount) -> ParentAccountSummaryResponse:
    memberships = session.exec(
        select(ParentAccountMembership)
        .where(ParentAccountMembership.parent_account_id == parent.id)
        .order_by(ParentAccountMembership.created_at)
    ).all()

    tenant_ids = list(dict.fromkeys(m.tenant_id for m in memberships))
    user_ids = list(dict.fromkeys(m.user_id for m in memberships))
    tenants_by_id = {
        t.id: t
        for t in session.exec(select(Tenant).where(col(Tenant.id).in_(tenant_ids))).all()
    } if tenant_ids else {}
    users_by_id = {
        u.id: u
        for u in session.exec(select(User).where(col(User.id).in_(user_ids))).all()
    } if user_ids else {}

    sites: list[ParentAccountSiteRead] = []
    seen_tenants: set[str] = set()
    for membership in memberships:
        tenant = tenants_by_id.get(membership.tenant_id)
        user = users_by_id.get(membership.user_id)
        if not tenant or not user:
            continue
        if str(tenant.id) in seen_tenants:
            continue
        seen_tenants.add(str(tenant.id))
        sites.append(
            ParentAccountSiteRead(
                tenant_id=tenant.id,
                tenant_slug=tenant.slug,
                tenant_name=tenant.name,
                shop_number=tenant.shop_number,
                area=tenant.minit_area,
                region=tenant.minit_region,
                plan_code=normalize_plan_code(tenant.plan_code),
                owner_user_id=user.id,
                owner_email=user.email,
                owner_full_name=user.full_name,
            )
        )

    return ParentAccountSummaryResponse(
        parent_account_id=parent.id,
        parent_account_name=parent.name,
        owner_email=parent.owner_email,
        sites=sorted(sites, key=lambda s: (s.tenant_name.lower(), s.tenant_slug.lower())),
        mobile_lead_ingest_public_id=parent.mobile_lead_ingest_public_id,
        mobile_lead_webhook_secret_configured=bool(parent.mobile_lead_webhook_secret_hash),
        mobile_lead_default_tenant_id=parent.mobile_lead_default_tenant_id,
    )


def _normalize_plan_code(value: str | None) -> str:
    if value is None:
        return "pro"
    normalized = normalize_plan_code(value, default_if_empty="")
    if normalized not in VALID_PLAN_CODES:
        raise HTTPException(status_code=400, detail=f"Unsupported plan code '{value}'")
    return normalized


def _record_event(
    session: Session,
    *,
    parent_account_id: UUID,
    tenant_id: UUID | None,
    actor_user_id: UUID | None,
    actor_email: str | None,
    event_type: str,
    event_summary: str,
) -> None:
    session.add(
        ParentAccountEventLog(
            parent_account_id=parent_account_id,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            actor_email=actor_email,
            event_type=event_type,
            event_summary=event_summary,
        )
    )


def _tenant_linked_to_parent(session: Session, parent_id: UUID, tenant_id: UUID) -> bool:
    return (
        session.exec(
            select(ParentAccountMembership)
            .where(ParentAccountMembership.parent_account_id == parent_id)
            .where(ParentAccountMembership.tenant_id == tenant_id)
        ).first()
        is not None
    )


@router.post("/me/mobile-lead-ingest/enable", response_model=ParentAccountSummaryResponse)
def enable_mobile_lead_ingest(
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(get_session),
):
    """Assign a public ingest id for website POSTs (if not already set)."""
    current_user = session.get(User, auth.user_id)
    if not current_user or not current_user.is_active:
        raise HTTPException(status_code=401, detail="Invalid token")
    parent = _get_parent_account_for_user(session, current_user)
    if parent.mobile_lead_ingest_public_id is None:
        parent.mobile_lead_ingest_public_id = uuid4()
        _record_event(
            session,
            parent_account_id=parent.id,
            tenant_id=None,
            actor_user_id=current_user.id,
            actor_email=current_user.email,
            event_type="mobile_lead_ingest_enabled",
            event_summary="Enabled website mobile key lead ingest URL",
        )
        session.add(parent)
        session.commit()
    session.refresh(parent)
    return _to_summary(session, parent)


@router.put("/me/mobile-lead-ingest/secret", response_model=ParentAccountSummaryResponse)
def set_mobile_lead_webhook_secret(
    body: ParentMobileLeadWebhookSecretBody,
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(get_session),
):
    current_user = session.get(User, auth.user_id)
    if not current_user or not current_user.is_active:
        raise HTTPException(status_code=401, detail="Invalid token")
    parent = _get_parent_account_for_user(session, current_user)
    if parent.mobile_lead_ingest_public_id is None:
        parent.mobile_lead_ingest_public_id = uuid4()
    parent.mobile_lead_webhook_secret_hash = hash_password(body.webhook_secret.strip())
    _record_event(
        session,
        parent_account_id=parent.id,
        tenant_id=None,
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        event_type="mobile_lead_secret_set",
        event_summary="Set website mobile key lead webhook secret",
    )
    session.add(parent)
    session.commit()
    session.refresh(parent)
    return _to_summary(session, parent)


@router.delete("/me/mobile-lead-ingest/secret", response_model=ParentAccountSummaryResponse)
def clear_mobile_lead_webhook_secret(
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(get_session),
):
    current_user = session.get(User, auth.user_id)
    if not current_user or not current_user.is_active:
        raise HTTPException(status_code=401, detail="Invalid token")
    parent = _get_parent_account_for_user(session, current_user)
    parent.mobile_lead_webhook_secret_hash = None
    _record_event(
        session,
        parent_account_id=parent.id,
        tenant_id=None,
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        event_type="mobile_lead_secret_cleared",
        event_summary="Cleared website mobile key lead webhook secret",
    )
    session.add(parent)
    session.commit()
    session.refresh(parent)
    return _to_summary(session, parent)


@router.put("/me/mobile-lead-ingest/default-tenant", response_model=ParentAccountSummaryResponse)
def set_mobile_lead_default_tenant(
    body: ParentMobileLeadDefaultTenantBody,
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(get_session),
):
    current_user = session.get(User, auth.user_id)
    if not current_user or not current_user.is_active:
        raise HTTPException(status_code=401, detail="Invalid token")
    parent = _get_parent_account_for_user(session, current_user)
    if body.tenant_id is None:
        parent.mobile_lead_default_tenant_id = None
        summary = "Cleared default site for unmatched suburbs"
    else:
        if not _tenant_linked_to_parent(session, parent.id, body.tenant_id):
            raise HTTPException(status_code=400, detail="That site is not linked to this parent account")
        parent.mobile_lead_default_tenant_id = body.tenant_id
        summary = "Set default site for website leads when suburb is not mapped"
    _record_event(
        session,
        parent_account_id=parent.id,
        tenant_id=body.tenant_id,
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        event_type="mobile_lead_default_tenant",
        event_summary=summary,
    )
    session.add(parent)
    session.commit()
    session.refresh(parent)
    return _to_summary(session, parent)


@router.get("/me/mobile-lead-routes", response_model=list[MobileSuburbRouteRead])
def list_mobile_suburb_routes(
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(get_session),
):
    current_user = session.get(User, auth.user_id)
    if not current_user or not current_user.is_active:
        raise HTTPException(status_code=401, detail="Invalid token")
    parent = _get_parent_account_for_user(session, current_user)
    rows = session.exec(
        select(MobileSuburbRoute)
        .where(MobileSuburbRoute.parent_account_id == parent.id)
        .order_by(MobileSuburbRoute.state_code, MobileSuburbRoute.suburb_normalized)
    ).all()
    return [
        MobileSuburbRouteRead(
            id=r.id,
            state_code=r.state_code,
            suburb_normalized=r.suburb_normalized,
            target_tenant_id=r.target_tenant_id,
        )
        for r in rows
    ]


@router.post("/me/mobile-lead-routes", response_model=MobileSuburbRouteRead)
def create_mobile_suburb_route(
    payload: MobileSuburbRouteCreateRequest,
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(get_session),
):
    current_user = session.get(User, auth.user_id)
    if not current_user or not current_user.is_active:
        raise HTTPException(status_code=401, detail="Invalid token")
    parent = _get_parent_account_for_user(session, current_user)
    st = payload.state_code.strip().upper()
    if st not in AU_STATES:
        raise HTTPException(status_code=400, detail=f"Invalid state_code; use one of: {', '.join(sorted(AU_STATES))}")
    sub_norm = _normalize_suburb(payload.suburb)
    if not sub_norm:
        raise HTTPException(status_code=400, detail="suburb is required")
    if not _tenant_linked_to_parent(session, parent.id, payload.target_tenant_id):
        raise HTTPException(status_code=400, detail="Target site is not linked to this parent account")
    row = MobileSuburbRoute(
        parent_account_id=parent.id,
        state_code=st,
        suburb_normalized=sub_norm,
        target_tenant_id=payload.target_tenant_id,
    )
    session.add(row)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="A route for this state and suburb already exists",
        ) from None
    _record_event(
        session,
        parent_account_id=parent.id,
        tenant_id=payload.target_tenant_id,
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        event_type="mobile_lead_route_added",
        event_summary=f"Mapped suburb '{sub_norm}' ({st}) to a linked site",
    )
    session.commit()
    session.refresh(row)
    return MobileSuburbRouteRead(
        id=row.id,
        state_code=row.state_code,
        suburb_normalized=row.suburb_normalized,
        target_tenant_id=row.target_tenant_id,
    )


@router.delete("/me/mobile-lead-routes/{route_id}")
def delete_mobile_suburb_route(
    route_id: UUID,
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(get_session),
):
    current_user = session.get(User, auth.user_id)
    if not current_user or not current_user.is_active:
        raise HTTPException(status_code=401, detail="Invalid token")
    parent = _get_parent_account_for_user(session, current_user)
    row = session.get(MobileSuburbRoute, route_id)
    if not row or row.parent_account_id != parent.id:
        raise HTTPException(status_code=404, detail="Route not found")
    session.delete(row)
    _record_event(
        session,
        parent_account_id=parent.id,
        tenant_id=row.target_tenant_id,
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        event_type="mobile_lead_route_removed",
        event_summary=f"Removed suburb route {row.suburb_normalized} ({row.state_code})",
    )
    session.commit()
    return {"ok": True}


def _tenant_has_shop_mobile_booking(plan_code: str) -> bool:
    plan = normalize_plan_code(plan_code)
    return "shop_mobile_booking" in PLAN_FEATURES.get(plan, set())


@router.get("/me/shop-booking-usage", response_model=ShopBookingUsageResponse)
def get_shop_booking_usage(
    month: str = Query(..., pattern=r"^\d{4}-\d{2}$", description="Calendar month YYYY-MM"),
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(get_session),
):
    """Per-shop booking counts for Minit-style billing (accepted + pending in month)."""
    current_user = session.get(User, auth.user_id)
    if not current_user or not current_user.is_active:
        raise HTTPException(status_code=401, detail="Invalid token")

    try:
        year_s, mon_s = month.split("-", 1)
        year, mon = int(year_s), int(mon_s)
        if mon < 1 or mon > 12:
            raise ValueError("month")
        last_day = monthrange(year, mon)[1]
        month_start = datetime(year, mon, 1, tzinfo=timezone.utc)
        month_end = datetime(year, mon, last_day, 23, 59, 59, tzinfo=timezone.utc)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="month must be YYYY-MM") from exc

    parent = _get_parent_account_for_user(session, current_user)
    memberships = session.exec(
        select(ParentAccountMembership).where(ParentAccountMembership.parent_account_id == parent.id)
    ).all()

    shop_tenant_ids: list[UUID] = []
    booking_tenant_count = 0
    seen_shops: set[UUID] = set()
    for m in memberships:
        if m.tenant_id in seen_shops:
            continue
        tenant = session.get(Tenant, m.tenant_id)
        if not tenant:
            continue
        seen_shops.add(m.tenant_id)
        plan = normalize_plan_code(tenant.plan_code)
        if plan == "booking_only" or _tenant_has_shop_mobile_booking(plan):
            booking_tenant_count += 1
            if _tenant_has_shop_mobile_booking(plan):
                shop_tenant_ids.append(m.tenant_id)

    shops: list[ShopBookingUsageShopBreakdown] = []
    for tid in shop_tenant_ids:
        tenant = session.get(Tenant, tid)
        if not tenant:
            continue
        accepted = int(
            session.exec(
                select(func.count())
                .select_from(ShopMobileBookingRequest)
                .where(ShopMobileBookingRequest.parent_account_id == parent.id)
                .where(ShopMobileBookingRequest.requesting_tenant_id == tid)
                .where(ShopMobileBookingRequest.status == "accepted")
                .where(col(ShopMobileBookingRequest.created_at) >= month_start)
                .where(col(ShopMobileBookingRequest.created_at) <= month_end)
            ).one()
        )
        pending = int(
            session.exec(
                select(func.count())
                .select_from(ShopMobileBookingRequest)
                .where(ShopMobileBookingRequest.parent_account_id == parent.id)
                .where(ShopMobileBookingRequest.requesting_tenant_id == tid)
                .where(ShopMobileBookingRequest.status == "pending")
                .where(col(ShopMobileBookingRequest.created_at) >= month_start)
                .where(col(ShopMobileBookingRequest.created_at) <= month_end)
            ).one()
        )
        shops.append(
            ShopBookingUsageShopBreakdown(
                tenant_id=tid,
                tenant_name=tenant.name,
                shop_number=tenant.shop_number,
                accepted_bookings_count=accepted,
                pending_count=pending,
            )
        )

    return ShopBookingUsageResponse(
        month=month,
        booking_tenant_count=booking_tenant_count,
        shops=sorted(shops, key=lambda s: s.tenant_name.lower()),
    )


@router.get("/me", response_model=ParentAccountSummaryResponse)
def get_parent_account_summary(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    user = session.get(User, auth.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid token")

    parent = _get_parent_account_for_user(session, user)
    return _to_summary(session, parent)


@router.get("/me/activity", response_model=list[ParentAccountEventLogRead])
def list_parent_account_activity(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    user = session.get(User, auth.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid token")

    parent = _get_parent_account_for_user(session, user)
    safe_limit = max(1, min(limit, 200))
    rows = session.exec(
        select(ParentAccountEventLog)
        .where(ParentAccountEventLog.parent_account_id == parent.id)
        .order_by(ParentAccountEventLog.created_at.desc())
        .offset(offset)
        .limit(safe_limit)
    ).all()

    return [
        ParentAccountEventLogRead(
            id=row.id,
            parent_account_id=row.parent_account_id,
            tenant_id=row.tenant_id,
            actor_user_id=row.actor_user_id,
            actor_email=row.actor_email,
            event_type=row.event_type,
            event_summary=row.event_summary,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.post("/me/link-tenant", response_model=ParentAccountSummaryResponse)
def link_tenant_to_parent_account(
    payload: ParentAccountLinkTenantRequest,
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(get_session),
):
    current_user = session.get(User, auth.user_id)
    if not current_user or not current_user.is_active:
        raise HTTPException(status_code=401, detail="Invalid token")

    parent = _get_parent_account_for_user(session, current_user)

    tenant_slug = payload.tenant_slug.strip().lower()
    owner_email = payload.owner_email.strip().lower()
    if not tenant_slug:
        raise HTTPException(status_code=400, detail="tenant_slug is required")
    if not owner_email or "@" not in owner_email:
        raise HTTPException(status_code=400, detail="owner_email is invalid")

    tenant = session.exec(select(Tenant).where(Tenant.slug == tenant_slug)).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    owner_user = session.exec(
        select(User)
        .where(User.tenant_id == tenant.id)
        .where(User.email == owner_email)
        .where(User.role == "owner")
        .where(User.is_active)
    ).first()
    if not owner_user:
        raise HTTPException(status_code=404, detail="Owner user not found for tenant")

    shop_number = validate_shop_number_format(payload.shop_number)
    if shop_number:
        assert_shop_number_unique_in_parent(
            session,
            parent_id=parent.id,
            shop_number=shop_number,
            exclude_tenant_id=tenant.id,
        )
        tenant.shop_number = shop_number
        session.add(tenant)

    existing = session.exec(
        select(ParentAccountMembership)
        .where(ParentAccountMembership.parent_account_id == parent.id)
        .where(ParentAccountMembership.tenant_id == tenant.id)
    ).first()

    if not existing:
        session.add(
            ParentAccountMembership(
                parent_account_id=parent.id,
                tenant_id=tenant.id,
                user_id=owner_user.id,
            )
        )
        _record_event(
            session,
            parent_account_id=parent.id,
            tenant_id=tenant.id,
            actor_user_id=current_user.id,
            actor_email=current_user.email,
            event_type="link_tenant",
            event_summary=f"Linked site '{tenant.name}' ({tenant.slug})",
        )
        session.commit()

    session.refresh(parent)
    return _to_summary(session, parent)


@router.post("/me/create-tenant", response_model=ParentAccountSummaryResponse)
def create_tenant_from_parent_account(
    payload: ParentAccountCreateTenantRequest,
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(get_session),
):
    current_user = session.get(User, auth.user_id)
    if not current_user or not current_user.is_active:
        raise HTTPException(status_code=401, detail="Invalid token")

    parent = _get_parent_account_for_user(session, current_user)

    tenant_name = payload.tenant_name.strip()
    tenant_slug = payload.tenant_slug.strip().lower()
    if not tenant_name:
        raise HTTPException(status_code=400, detail="tenant_name is required")
    if not tenant_slug:
        raise HTTPException(status_code=400, detail="tenant_slug is required")

    existing_tenant = session.exec(select(Tenant).where(Tenant.slug == tenant_slug)).first()
    if existing_tenant:
        raise HTTPException(status_code=409, detail="Tenant slug already exists")

    shop_number = validate_shop_number_format(payload.shop_number)
    if shop_number:
        assert_shop_number_unique_in_parent(session, parent_id=parent.id, shop_number=shop_number)

    business_address = payload.business_address.strip()[:2000] if payload.business_address else None
    tenant = Tenant(
        name=tenant_name,
        slug=tenant_slug,
        plan_code=_normalize_plan_code(payload.plan_code),
        business_address=business_address,
        shop_number=shop_number,
    )
    session.add(tenant)
    session.flush()

    new_owner = User(
        tenant_id=tenant.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role="owner",
        password_hash=current_user.password_hash,
        is_active=True,
    )
    session.add(new_owner)
    session.flush()

    session.add(
        ParentAccountMembership(
            parent_account_id=parent.id,
            tenant_id=tenant.id,
            user_id=new_owner.id,
        )
    )
    _record_event(
        session,
        parent_account_id=parent.id,
        tenant_id=tenant.id,
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        event_type="create_tenant",
        event_summary=f"Created and linked site '{tenant.name}' ({tenant.slug})",
    )

    session.commit()
    session.refresh(parent)
    return _to_summary(session, parent)


@router.post("/me/import-shops", response_model=ParentImportShopsResponse)
async def import_shops_from_xlsx(
    file: UploadFile = File(...),
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(get_session),
):
    """Bulk create/update retail shops from a Minit shop-list Excel workbook (HQ only)."""
    _require_minit_hq(auth, session)
    current_user = session.get(User, auth.user_id)
    if not current_user or not current_user.is_active:
        raise HTTPException(status_code=401, detail="Invalid token")

    parent = _get_parent_account_for_user(session, current_user)
    filename = (file.filename or "").strip()
    if not filename:
        raise HTTPException(status_code=400, detail="File name is required")
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if f".{suffix}" not in _ALLOWED_XLSX_SUFFIXES:
        raise HTTPException(status_code=400, detail="Only .xlsx or .xlsm workbooks are supported")

    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(raw_bytes) > MAX_IMPORT_SHOPS_XLSX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum size of {MAX_IMPORT_SHOPS_XLSX_BYTES // (1024 * 1024)} MB",
        )

    try:
        parsed = parse_minit_shops_xlsx_detailed(file_obj=raw_bytes, collect_row_errors=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not parsed.shops:
        return ParentImportShopsResponse(
            parsed_count=0,
            sheet_name=parsed.sheet_name,
            errors=parsed.errors or ["No valid shop rows found in workbook"],
        )

    summary = import_minit_shops(
        session,
        parent_name=parent.name,
        hq_owner_email=current_user.email,
        shops=parsed.shops,
        apply=True,
    )

    errors: list[str] = list(parsed.errors)
    if summary.get("error"):
        errors.append(str(summary["error"]))

    created = int(summary.get("created_count", 0))
    updated = int(summary.get("updated_count", 0))
    skipped = int(summary.get("skipped_count", summary.get("would_skip_count", 0)))

    _record_event(
        session,
        parent_account_id=parent.id,
        tenant_id=None,
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        event_type="import_shops",
        event_summary=(
            f"Imported shops from {filename}: "
            f"{created} created, {updated} updated, {skipped} skipped"
        ),
    )
    session.commit()

    return ParentImportShopsResponse(
        created_count=created,
        updated_count=updated,
        skipped_count=skipped,
        parsed_count=len(parsed.shops),
        sheet_name=parsed.sheet_name,
        errors=errors[:100],
    )


@router.post("/me/provision-shop", response_model=ParentAccountSummaryResponse)
def provision_minit_retail_shop(
    payload: ParentProvisionShopRequest,
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(get_session),
):
    """Create a booking_only Minit retail shop (slug minit-{shop_number}) under this parent."""
    current_user = session.get(User, auth.user_id)
    if not current_user or not current_user.is_active:
        raise HTTPException(status_code=401, detail="Invalid token")

    parent = _get_parent_account_for_user(session, current_user)
    shop_number = validate_shop_number_format(payload.shop_number)
    if not shop_number:
        raise HTTPException(status_code=400, detail="shop_number is required")
    assert_shop_number_unique_in_parent(session, parent_id=parent.id, shop_number=shop_number)

    tenant_name = payload.tenant_name.strip()
    if not tenant_name:
        raise HTTPException(status_code=400, detail="tenant_name is required")
    tenant_slug = tenant_slug_for_shop(
        MinitShopRow(shop_number=normalize_shop_number(shop_number) or shop_number, name=tenant_name, area=None, region=None)
    )

    existing_tenant = session.exec(select(Tenant).where(Tenant.slug == tenant_slug)).first()
    if existing_tenant:
        raise HTTPException(status_code=409, detail="Shop slug already exists")

    business_address = payload.business_address.strip()[:2000] if payload.business_address else None
    tenant = Tenant(
        name=tenant_name,
        slug=tenant_slug,
        plan_code="booking_only",
        business_address=business_address,
        shop_number=shop_number,
    )
    session.add(tenant)
    session.flush()

    new_owner = User(
        tenant_id=tenant.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role="owner",
        password_hash=current_user.password_hash,
        is_active=True,
    )
    session.add(new_owner)
    session.flush()

    session.add(
        ParentAccountMembership(
            parent_account_id=parent.id,
            tenant_id=tenant.id,
            user_id=new_owner.id,
        )
    )
    _record_event(
        session,
        parent_account_id=parent.id,
        tenant_id=tenant.id,
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        event_type="provision_shop",
        event_summary=f"Provisioned Minit shop '{tenant.name}' ({tenant.slug})",
    )
    session.commit()
    session.refresh(parent)
    return _to_summary(session, parent)


@router.delete("/me/sites/{tenant_id}", response_model=ParentAccountSummaryResponse)
def unlink_tenant_from_parent_account(
    tenant_id: UUID,
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(get_session),
):
    current_user = session.get(User, auth.user_id)
    if not current_user or not current_user.is_active:
        raise HTTPException(status_code=401, detail="Invalid token")

    parent = _get_parent_account_for_user(session, current_user)

    if tenant_id == auth.tenant_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot unlink the currently active site. Switch to another site first.",
        )

    memberships = session.exec(
        select(ParentAccountMembership).where(
            ParentAccountMembership.parent_account_id == parent.id
        )
    ).all()

    if len(memberships) <= 1:
        raise HTTPException(status_code=400, detail="Cannot unlink the last remaining site")

    membership = next((m for m in memberships if m.tenant_id == tenant_id), None)
    if not membership:
        raise HTTPException(status_code=404, detail="Site is not linked to this parent account")

    tenant = session.get(Tenant, membership.tenant_id)
    tenant_name = tenant.name if tenant else str(membership.tenant_id)
    tenant_slug = tenant.slug if tenant else "unknown"

    for r in session.exec(
        select(MobileSuburbRoute).where(
            MobileSuburbRoute.parent_account_id == parent.id,
            MobileSuburbRoute.target_tenant_id == tenant_id,
        )
    ).all():
        session.delete(r)
    if parent.mobile_lead_default_tenant_id == tenant_id:
        parent.mobile_lead_default_tenant_id = None
        session.add(parent)

    session.delete(membership)
    _record_event(
        session,
        parent_account_id=parent.id,
        tenant_id=membership.tenant_id,
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        event_type="unlink_tenant",
        event_summary=f"Unlinked site '{tenant_name}' ({tenant_slug})",
    )
    session.commit()
    session.refresh(parent)
    return _to_summary(session, parent)
