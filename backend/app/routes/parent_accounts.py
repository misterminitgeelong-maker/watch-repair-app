from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from ..database import get_session
from ..dependencies import (
    AuthContext,
    VALID_PLAN_CODES,
    get_auth_context,
    normalize_plan_code,
    require_feature,
    require_owner,
)
from ..models import (
    MobileSuburbRoute,
    MobileSuburbRouteCreateRequest,
    MobileSuburbRouteRead,
    ParentAccount,
    ParentAccountCreateTenantRequest,
    ParentAccountEventLog,
    ParentAccountEventLogRead,
    ParentAccountLinkTenantRequest,
    ParentAccountMembership,
    ParentAccountSiteRead,
    ParentAccountSummaryResponse,
    ParentMobileLeadDefaultTenantBody,
    ParentMobileLeadWebhookSecretBody,
    Tenant,
    User,
)
from ..security import hash_password

router = APIRouter(
    prefix="/v1/parent-accounts",
    tags=["parent-accounts"],
    dependencies=[Depends(require_feature("multi_site"))],
)

AU_STATES = frozenset({"ACT", "NSW", "NT", "QLD", "SA", "TAS", "VIC", "WA"})


def _normalize_suburb(name: str) -> str:
    return " ".join(name.strip().lower().split())


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

    sites: list[ParentAccountSiteRead] = []
    seen_tenants: set[str] = set()
    for membership in memberships:
        tenant = session.get(Tenant, membership.tenant_id)
        user = session.get(User, membership.user_id)
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

    tenant = Tenant(
        name=tenant_name,
        slug=tenant_slug,
        plan_code=_normalize_plan_code(payload.plan_code),
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
