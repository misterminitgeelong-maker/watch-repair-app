from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, func, select

from ..config import settings
from ..database import get_session
from ..models import (
    BootstrapResponse,
    LoginRequest,
    PublicUser,
    RepairJob,
    Tenant,
    TenantBootstrap,
    TokenResponse,
    User,
)
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/v1/auth", tags=["auth"])


def _create_default_owner(session: Session, tenant: Tenant) -> User:
    owner = User(
        tenant_id=tenant.id,
        email=settings.startup_seed_owner_email,
        full_name="Admin",
        role="owner",
        password_hash=hash_password(settings.startup_seed_owner_password),
        is_active=True,
    )
    session.add(owner)
    session.commit()
    session.refresh(owner)
    return owner


@router.post("/bootstrap", response_model=BootstrapResponse)
def bootstrap_tenant(payload: TenantBootstrap, session: Session = Depends(get_session)):
    if not settings.allow_public_bootstrap:
        raise HTTPException(status_code=403, detail="Bootstrap is disabled")

    existing_tenant = session.exec(select(Tenant).where(Tenant.slug == payload.tenant_slug)).first()
    if existing_tenant:
        raise HTTPException(status_code=409, detail="Tenant slug already exists")

    tenant = Tenant(name=payload.tenant_name, slug=payload.tenant_slug)
    session.add(tenant)
    session.flush()

    owner = User(
        tenant_id=tenant.id,
        email=payload.owner_email,
        full_name=payload.owner_full_name,
        role="owner",
        password_hash=hash_password(payload.owner_password),
    )
    session.add(owner)
    session.commit()
    session.refresh(owner)

    return BootstrapResponse(
        tenant_id=tenant.id,
        owner_user=PublicUser(
            id=owner.id,
            tenant_id=owner.tenant_id,
            email=owner.email,
            full_name=owner.full_name,
            role=owner.role,
            is_active=owner.is_active,
        ),
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, session: Session = Depends(get_session)):
    tenant = session.exec(select(Tenant).where(Tenant.slug == payload.tenant_slug)).first()
    if not tenant:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user = session.exec(
        select(User).where(User.tenant_id == tenant.id).where(User.email == payload.email)
    ).first()

    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token_subject = f"{tenant.id}:{user.id}:{user.role}"
    token, expires = create_access_token(token_subject)
    return TokenResponse(access_token=token, expires_in_seconds=expires)


@router.post("/dev-auto-login", response_model=TokenResponse)
def dev_auto_login(session: Session = Depends(get_session)):
    if not settings.allow_public_bootstrap:
        raise HTTPException(status_code=403, detail="Dev auto-login is disabled")

    tenants = session.exec(select(Tenant)).all()
    if not tenants:
        tenant = Tenant(name=settings.startup_seed_tenant_name, slug=settings.startup_seed_tenant_slug)
        session.add(tenant)
        session.flush()
        user = _create_default_owner(session, tenant)
        token_subject = f"{tenant.id}:{user.id}:{user.role}"
        token, expires = create_access_token(token_subject)
        return TokenResponse(access_token=token, expires_in_seconds=expires)

    selected_tenant = tenants[0]
    selected_count = -1
    for tenant in tenants:
        tenant_job_count = session.exec(
            select(func.count()).select_from(RepairJob).where(RepairJob.tenant_id == tenant.id)
        ).one()
        count = int(tenant_job_count)
        if count > selected_count:
            selected_count = count
            selected_tenant = tenant

    user = session.exec(
        select(User)
        .where(User.tenant_id == selected_tenant.id)
        .where(User.email == settings.startup_seed_owner_email)
        .where(User.is_active)
    ).first()

    if not user:
        user = session.exec(
            select(User)
            .where(User.tenant_id == selected_tenant.id)
            .where(User.is_active)
            .order_by(User.created_at)
        ).first()

    if not user:
        user = _create_default_owner(session, selected_tenant)

    token_subject = f"{selected_tenant.id}:{user.id}:{user.role}"
    token, expires = create_access_token(token_subject)
    return TokenResponse(access_token=token, expires_in_seconds=expires)
