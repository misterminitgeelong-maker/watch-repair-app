from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..database import get_session
from ..dependencies import get_auth_context, require_feature, require_owner, AuthContext
from ..models import (
    ParentAccount,
    ParentAccountCreateTenantRequest,
    ParentAccountEventLog,
    ParentAccountEventLogRead,
    ParentAccountLinkTenantRequest,
    ParentAccountMembership,
    ParentAccountSiteRead,
    ParentAccountSummaryResponse,
    Tenant,
    User,
)

router = APIRouter(
    prefix="/v1/parent-accounts",
    tags=["parent-accounts"],
    dependencies=[Depends(require_feature("multi_site"))],
)


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
    )


def _normalize_plan_code(value: str | None) -> str:
    if value is None:
        return "enterprise"
    normalized = value.strip().lower()
    if normalized not in {"shoe", "watch", "auto_key", "enterprise"}:
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
    limit: int = 50,
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
