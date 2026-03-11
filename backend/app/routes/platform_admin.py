from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from ..database import get_session
from ..dependencies import require_platform_admin
from ..models import PlatformUserRead, Tenant, User

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
