"""Public claim flow for shop-owner invites.

A provisioned Minit shop starts out sharing the HQ owner's login (see
``minit_provision.py``). HQ can send a one-time invite (see
``routes/parent_accounts.py``) locked to that shop's owner ``User`` row;
these routes let the franchisee open the link, set their own email and
password, and land signed in — no separate login step.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from ..database import get_session
from ..models import (
    ShopOwnerInvite,
    ShopOwnerInviteCompleteRequest,
    ShopOwnerInvitePublicRead,
    Tenant,
    TokenResponse,
    User,
)
from ..security import hash_password
from .auth import _issue_session_tokens, _validate_password_strength

router = APIRouter(prefix="/v1/public/shop-invite", tags=["shop-owner-invites"])


def _mask_email(email: str) -> str:
    name, _, domain = email.partition("@")
    if not domain:
        return email
    visible = name[:2] if len(name) > 2 else name[:1]
    return f"{visible}{'*' * max(len(name) - len(visible), 1)}@{domain}"


def _load_pending_invite(session: Session, token: str) -> ShopOwnerInvite:
    invite = session.exec(select(ShopOwnerInvite).where(ShopOwnerInvite.token == token)).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    expires_at = invite.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if invite.status == "pending" and expires_at < datetime.now(timezone.utc):
        invite.status = "expired"
        session.add(invite)
        session.commit()
    if invite.status != "pending":
        detail = {
            "completed": "This invite has already been used.",
            "revoked": "This invite is no longer valid. Ask HQ to send a new one.",
            "expired": "This invite has expired. Ask HQ to send a new one.",
        }.get(invite.status, "This invite is no longer valid.")
        raise HTTPException(status_code=410, detail=detail)
    return invite


@router.get("/{token}", response_model=ShopOwnerInvitePublicRead)
def get_shop_owner_invite_public(token: str, session: Session = Depends(get_session)):
    invite = _load_pending_invite(session, token)
    tenant = session.get(Tenant, invite.tenant_id)
    owner = session.get(User, invite.owner_user_id)
    if not tenant or not owner:
        raise HTTPException(status_code=404, detail="Invite not found")
    return ShopOwnerInvitePublicRead(
        tenant_name=tenant.name,
        shop_number=tenant.shop_number,
        masked_email=_mask_email(owner.email),
        status=invite.status,
        expires_at=invite.expires_at,
    )


@router.post("/{token}/complete", response_model=TokenResponse)
def complete_shop_owner_invite(
    token: str,
    payload: ShopOwnerInviteCompleteRequest,
    request: Request,
    session: Session = Depends(get_session),
):
    invite = _load_pending_invite(session, token)
    tenant = session.get(Tenant, invite.tenant_id)
    owner = session.get(User, invite.owner_user_id)
    if not tenant or not owner or not owner.is_active:
        raise HTTPException(status_code=404, detail="Invite not found")

    full_name = payload.full_name.strip()
    email = payload.email.strip().lower()
    if not full_name:
        raise HTTPException(status_code=400, detail="Full name is required")
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="A valid email is required")
    _validate_password_strength(payload.password)

    owner.full_name = full_name
    owner.email = email
    owner.password_hash = hash_password(payload.password)
    session.add(owner)
    invite.status = "completed"
    invite.completed_at = datetime.now(timezone.utc)
    session.add(invite)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="That email is already in use on this account")

    access, access_exp, refresh, refresh_exp = _issue_session_tokens(
        session, tenant_id=tenant.id, user_id=owner.id, role=owner.role, request=request
    )
    return TokenResponse(
        access_token=access,
        expires_in_seconds=access_exp,
        refresh_token=refresh,
        refresh_expires_in_seconds=refresh_exp,
    )
