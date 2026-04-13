from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, func, select

from ..database import get_session
from ..dependencies import require_platform_admin
from ..models import PlatformEnterShopResponse, PlatformTenantRead, PlatformUserRead, Tenant, User
from ..security import create_access_token, create_refresh_token

router = APIRouter(prefix="/v1/platform-admin", tags=["platform-admin"])


@router.get("/users", response_model=list[PlatformUserRead])
def list_all_users(
    _: object = Depends(require_platform_admin),
    session: Session = Depends(get_session),
):
    rows = session.exec(
        select(User, Tenant)
        .join(Tenant, Tenant.id == User.tenant_id)
        .order_by(Tenant.slug, User.created_at)
    ).all()

    return [
        PlatformUserRead(
            id=user.id,
            tenant_id=user.tenant_id,
            tenant_slug=tenant.slug,
            tenant_name=tenant.name,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
        )
        for user, tenant in rows
    ]


@router.get("/tenants", response_model=list[PlatformTenantRead])
def list_all_tenants(
    _: object = Depends(require_platform_admin),
    session: Session = Depends(get_session),
):
    tenants = session.exec(select(Tenant).order_by(Tenant.name)).all()

    # Count users per tenant with a simple per-tenant query to avoid SQLModel aggregation issues
    user_counts: dict[UUID, int] = {}
    for t in tenants:
        user_counts[t.id] = session.exec(
            select(func.count(User.id)).where(User.tenant_id == t.id)
        ).one()

    return [
        PlatformTenantRead(
            id=t.id,
            slug=t.slug,
            name=t.name,
            plan_code=t.plan_code,
            user_count=user_counts.get(t.id, 0),
            created_at=t.created_at,
        )
        for t in tenants
    ]


@router.post("/enter-shop/{tenant_id}", response_model=PlatformEnterShopResponse)
def enter_shop(
    tenant_id: UUID,
    auth: object = Depends(require_platform_admin),
    session: Session = Depends(get_session),
):
    """Issue a platform_admin-scoped token for any tenant, allowing the admin to
    view and manage that shop's data as if they were the owner."""
    tenant = session.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Shop not found.")

    # Find first active owner in the target tenant to anchor the user_id
    owner = session.exec(
        select(User)
        .where(User.tenant_id == tenant_id)
        .where(User.role == "owner")
        .where(User.is_active == True)  # noqa: E712
        .order_by(User.created_at)
    ).first()
    if not owner:
        raise HTTPException(status_code=400, detail="This shop has no active owner account.")

    # Issue tokens with platform_admin role but scoped to the target tenant
    access_token, expires = create_access_token(tenant_id, owner.id, "platform_admin")
    refresh_token, refresh_expires = create_refresh_token(tenant_id, owner.id, "platform_admin")

    return PlatformEnterShopResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in_seconds=expires,
        refresh_expires_in_seconds=refresh_expires,
        tenant_id=tenant_id,
        tenant_name=tenant.name,
    )
