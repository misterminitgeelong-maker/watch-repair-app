from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, func, select

from ..config import settings
from ..database import get_session
from ..models import (
    BootstrapResponse,
    LoginRequest,
    PublicUser,
    RepairJob,
    TenantSignupRequest,
    TenantSignupResponse,
    Tenant,
    TenantBootstrap,
    TokenResponse,
    User,
)
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/v1/auth", tags=["auth"])


def _normalize_email(value: str) -> str:
    return value.strip().lower()


def _normalize_slug(value: str) -> str:
    return value.strip().lower()


def _validate_password_strength(value: str) -> None:
    password = value or ""
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")


def _build_public_user(user: User) -> PublicUser:
    return PublicUser(
        id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
    )


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


@router.post("/signup", response_model=TenantSignupResponse)
def signup(payload: TenantSignupRequest, session: Session = Depends(get_session)):
    tenant_slug = _normalize_slug(payload.tenant_slug)
    owner_email = _normalize_email(payload.email)
    owner_name = payload.full_name.strip()
    tenant_name = payload.tenant_name.strip()

    if not tenant_slug:
        raise HTTPException(status_code=400, detail="Tenant slug is required")
    if not tenant_name:
        raise HTTPException(status_code=400, detail="Tenant name is required")
    if not owner_name:
        raise HTTPException(status_code=400, detail="Full name is required")
    if not owner_email or "@" not in owner_email:
        raise HTTPException(status_code=400, detail="A valid email is required")

    _validate_password_strength(payload.password)

    existing_tenant = session.exec(select(Tenant).where(Tenant.slug == tenant_slug)).first()
    if existing_tenant:
        raise HTTPException(status_code=409, detail="Tenant slug already exists")

    tenant = Tenant(name=tenant_name, slug=tenant_slug)
    session.add(tenant)
    session.flush()

    owner = User(
        tenant_id=tenant.id,
        email=owner_email,
        full_name=owner_name,
        role="owner",
        password_hash=hash_password(payload.password),
    )
    session.add(owner)
    session.commit()
    session.refresh(owner)

    token_subject = f"{tenant.id}:{owner.id}:{owner.role}"
    token, expires = create_access_token(token_subject)
    return TenantSignupResponse(
        tenant_id=tenant.id,
        user=_build_public_user(owner),
        access_token=token,
        expires_in_seconds=expires,
    )


@router.post("/bootstrap", response_model=BootstrapResponse)
def bootstrap_tenant(payload: TenantBootstrap, session: Session = Depends(get_session)):
    if not settings.allow_public_bootstrap:
        raise HTTPException(status_code=403, detail="Bootstrap is disabled")

    tenant_slug = _normalize_slug(payload.tenant_slug)
    owner_email = _normalize_email(payload.owner_email)
    _validate_password_strength(payload.owner_password)

    existing_tenant = session.exec(select(Tenant).where(Tenant.slug == tenant_slug)).first()
    if existing_tenant:
        raise HTTPException(status_code=409, detail="Tenant slug already exists")

    tenant = Tenant(name=payload.tenant_name.strip(), slug=tenant_slug)
    session.add(tenant)
    session.flush()

    owner = User(
        tenant_id=tenant.id,
        email=owner_email,
        full_name=payload.owner_full_name.strip(),
        role="owner",
        password_hash=hash_password(payload.owner_password),
    )
    session.add(owner)
    session.commit()
    session.refresh(owner)

    return BootstrapResponse(tenant_id=tenant.id, owner_user=_build_public_user(owner))


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, session: Session = Depends(get_session)):
    tenant = session.exec(select(Tenant).where(Tenant.slug == _normalize_slug(payload.tenant_slug))).first()
    if not tenant:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user = session.exec(
        select(User).where(User.tenant_id == tenant.id).where(User.email == _normalize_email(payload.email))
    ).first()

    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token_subject = f"{tenant.id}:{user.id}:{user.role}"
    token, expires = create_access_token(token_subject)
    return TokenResponse(access_token=token, expires_in_seconds=expires)


@router.post("/dev-auto-login", response_model=TokenResponse)
def dev_auto_login(session: Session = Depends(get_session)):
    if settings.app_env.lower() == "production" or not settings.allow_dev_auto_login:
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
