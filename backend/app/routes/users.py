from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..database import get_session
from ..dependencies import AuthContext, ROLE_HIERARCHY, get_auth_context, require_owner
from ..models import PublicUser, User, UserCreateRequest, UserUpdateRequest
from ..security import hash_password

router = APIRouter(prefix="/v1/users", tags=["users"])

TENANT_MANAGED_ROLES = {"owner", "manager", "tech", "intake"}


def _normalize_email(value: str) -> str:
    return value.strip().lower()


def _to_public_user(user: User) -> PublicUser:
    return PublicUser(
        id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
    )


def _validate_role(role: str) -> str:
    normalized = role.strip().lower()
    if normalized not in ROLE_HIERARCHY or normalized not in TENANT_MANAGED_ROLES:
        allowed = ", ".join(sorted(TENANT_MANAGED_ROLES))
        raise HTTPException(status_code=400, detail=f"Invalid role. Allowed: {allowed}")
    return normalized


@router.get("", response_model=list[PublicUser])
def list_users(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    rows = session.exec(
        select(User)
        .where(User.tenant_id == auth.tenant_id)
        .order_by(User.created_at)
    ).all()
    return [_to_public_user(u) for u in rows]


@router.post("", response_model=PublicUser, status_code=201)
def create_user(
    payload: UserCreateRequest,
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(get_session),
):
    email = _normalize_email(payload.email)
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="A valid email is required")

    full_name = payload.full_name.strip()
    if not full_name:
        raise HTTPException(status_code=400, detail="Full name is required")

    if len(payload.password or "") < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    role = _validate_role(payload.role)

    existing = session.exec(
        select(User)
        .where(User.tenant_id == auth.tenant_id)
        .where(User.email == email)
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="User with this email already exists")

    user = User(
        tenant_id=auth.tenant_id,
        email=email,
        full_name=full_name,
        role=role,
        password_hash=hash_password(payload.password),
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return _to_public_user(user)


@router.patch("/{user_id}", response_model=PublicUser)
def update_user(
    user_id: UUID,
    payload: UserUpdateRequest,
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(get_session),
):
    user = session.get(User, user_id)
    if not user or user.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="User not found")

    if payload.full_name is not None:
        full_name = payload.full_name.strip()
        if not full_name:
            raise HTTPException(status_code=400, detail="Full name cannot be empty")
        user.full_name = full_name

    if payload.role is not None:
        user.role = _validate_role(payload.role)

    if payload.password is not None:
        if len(payload.password) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
        user.password_hash = hash_password(payload.password)

    if payload.is_active is not None:
        user.is_active = payload.is_active

    session.add(user)
    session.commit()
    session.refresh(user)
    return _to_public_user(user)
