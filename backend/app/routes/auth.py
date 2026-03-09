from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..database import get_session
from ..models import (
    BootstrapResponse,
    LoginRequest,
    PublicUser,
    Tenant,
    TenantBootstrap,
    TokenResponse,
    User,
)
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/v1/auth", tags=["auth"])


@router.post("/bootstrap", response_model=BootstrapResponse)
def bootstrap_tenant(payload: TenantBootstrap, session: Session = Depends(get_session)):
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

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token_subject = f"{tenant.id}:{user.id}:{user.role}"
    token, expires = create_access_token(token_subject)
    return TokenResponse(access_token=token, expires_in_seconds=expires)
