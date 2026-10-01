"""Cross-tenant by design: platform invitations and their public acceptance."""
from datetime import datetime, timedelta, timezone
import hashlib
import html
import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from .. import email_client
from ..config import settings
from ..database import unscoped_session
from ..dependencies import AuthContext, require_platform_admin, invalidate_auth_cache
from ..limiter import limiter, public_read_limit, public_write_limit
from ..models import HqOwnerInvite, ParentAccount, ParentAccountSite, ParentAccountEventLog, TenantEventLog, Tenant, User, TokenResponse, PARENT_ROLE_HQ_ADMIN
from ..parent_network import grant_parent_role
from ..refresh_cookie import deliver_tokens
from ..security import hash_password, verify_password
from .auth import _issue_session_tokens, _validate_password_strength

router = APIRouter(tags=["hq-owner-invites"])
ADMIN = "/v1/platform-admin/hq-owners"
PUBLIC = "/v1/public/hq-invite"


class InviteRequest(BaseModel):
    parent_account_id: UUID
    tenant_id: UUID
    email: str = Field(min_length=3, max_length=254)
    full_name: str = Field(min_length=1, max_length=200)
    send_email: bool = True


class AcceptRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)


def _utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _target(session, parent_id, tenant_id):
    parent, tenant = session.get(ParentAccount, parent_id), session.get(Tenant, tenant_id)
    site = session.exec(select(ParentAccountSite).where(
        ParentAccountSite.parent_account_id == parent_id,
        ParentAccountSite.tenant_id == tenant_id,
        ParentAccountSite.network_role == "hq",
    )).first()
    if not parent or not tenant or not tenant.is_active or tenant.merged_into_tenant_id or not site:
        raise HTTPException(400, "Select an active HQ account linked to this network.")
    return parent, tenant


def _existing_user(session, invite):
    return session.exec(select(User).where(User.tenant_id == invite.tenant_id, User.email == invite.email)).first()


def _read(invite):
    status = invite.status
    if status == "pending" and _utc(invite.expires_at) <= datetime.now(timezone.utc):
        status = "expired"
    return {"id": str(invite.id), "parent_account_id": str(invite.parent_account_id), "tenant_id": str(invite.tenant_id),
            "email": invite.email, "full_name": invite.full_name, "status": status,
            "expires_at": _utc(invite.expires_at), "created_at": _utc(invite.created_at)}


def _audit(session, invite, actor, event):
    session.add(TenantEventLog(tenant_id=invite.tenant_id, actor_user_id=actor.id, actor_email=actor.email,
        entity_type="hq_owner_invite", entity_id=invite.id, event_type=f"hq_owner_invite_{event}",
        event_summary=f"HQ owner invitation {event} for {invite.email}"))
    session.add(ParentAccountEventLog(parent_account_id=invite.parent_account_id, tenant_id=invite.tenant_id,
        actor_user_id=actor.id, actor_email=actor.email, event_type=f"hq_owner_invite_{event}",
        event_summary=f"HQ owner invitation {event} for {invite.email}"))


@router.get(ADMIN)
def list_hq_owners(auth: AuthContext = Depends(require_platform_admin), session: Session = Depends(unscoped_session)):
    accounts = []
    for site in session.exec(select(ParentAccountSite).where(ParentAccountSite.network_role == "hq")).all():
        parent, tenant = session.get(ParentAccount, site.parent_account_id), session.get(Tenant, site.tenant_id)
        if parent and tenant and tenant.is_active and not tenant.merged_into_tenant_id:
            accounts.append({"parent_account_id": str(parent.id), "tenant_id": str(tenant.id),
                             "name": parent.name, "tenant_name": tenant.name, "tenant_slug": tenant.slug})
    invites = session.exec(select(HqOwnerInvite).order_by(HqOwnerInvite.created_at.desc()).limit(100)).all()
    return {"accounts": accounts, "invites": [_read(i) for i in invites]}


@router.post(ADMIN)
def create_hq_invite(payload: InviteRequest, auth: AuthContext = Depends(require_platform_admin), session: Session = Depends(unscoped_session)):
    parent, tenant = _target(session, payload.parent_account_id, payload.tenant_id)
    email, name = payload.email.strip().lower(), payload.full_name.strip()
    if not name or email.count("@") != 1 or any(c.isspace() for c in email) or not all(email.split("@")):
        raise HTTPException(400, "Enter the owner's name and a valid email.")
    # Serialise issuance per HQ account so concurrent resends leave one valid link.
    session.exec(select(Tenant).where(Tenant.id == tenant.id).with_for_update()).first()
    for old in session.exec(select(HqOwnerInvite).where(HqOwnerInvite.tenant_id == tenant.id, HqOwnerInvite.email == email, HqOwnerInvite.status == "pending")).all():
        old.status = "revoked"
        session.add(old)
    raw = secrets.token_urlsafe(32)
    invite = HqOwnerInvite(parent_account_id=parent.id, tenant_id=tenant.id, email=email, full_name=name,
        token_hash=hashlib.sha256(raw.encode()).hexdigest(), expires_at=datetime.now(timezone.utc) + timedelta(days=7))
    existing = _existing_user(session, invite)
    if existing and (not existing.is_active or existing.role == "platform_admin"):
        raise HTTPException(400, "This user cannot accept an HQ owner invitation.")
    session.add(invite)
    _audit(session, invite, session.get(User, auth.user_id), "created")
    session.commit()
    url = f"{settings.public_base_url.rstrip('/')}/hq-invite/{raw}"
    sent = False
    if payload.send_email:
        sent, _ = email_client.send_email_from_payload(to_email=email, event="hq_owner_invite", payload={
            "subject": f"Your {parent.name} HQ invitation",
            "body_plain": f"Hi {name},\n\nYou have been invited to manage {parent.name} in Mainspring HQ.\n\nAccept your invitation: {url}\n\nThis link expires in 7 days and can be used once. Your account ID is {tenant.slug}. If you already have a login for this account, use your existing password.\n",
            "body_html": f"<p>Hi {html.escape(name)},</p><p>You have been invited to manage {html.escape(parent.name)} in Mainspring HQ.</p><p><a href='{html.escape(url, quote=True)}'>Accept HQ invitation</a></p><p>This link expires in 7 days. Account ID: {html.escape(tenant.slug)}.</p>",
            "shop_name": "Mainspring",
        }, session=session, tenant_id=tenant.id)
        session.commit()
    return {**_read(invite), "invite_url": url, "email_sent": sent}


@router.delete(ADMIN + "/{invite_id}")
def revoke_hq_invite(invite_id: UUID, auth: AuthContext = Depends(require_platform_admin), session: Session = Depends(unscoped_session)):
    invite = session.get(HqOwnerInvite, invite_id)
    if not invite:
        raise HTTPException(404, "Invitation not found")
    result = session.execute(update(HqOwnerInvite).where(HqOwnerInvite.id == invite_id, HqOwnerInvite.status == "pending").values(status="revoked"))
    if result.rowcount:
        _audit(session, invite, session.get(User, auth.user_id), "revoked")
    session.commit()
    return {"revoked": bool(result.rowcount)}


def _pending(session, token):
    invite = session.exec(select(HqOwnerInvite).where(HqOwnerInvite.token_hash == hashlib.sha256(token.encode()).hexdigest())).first()
    if not invite:
        raise HTTPException(404, "Invitation not found")
    if invite.status != "pending" or _utc(invite.expires_at) <= datetime.now(timezone.utc):
        raise HTTPException(410, "This invitation has expired or is no longer valid. Ask your platform admin for a new link.")
    _target(session, invite.parent_account_id, invite.tenant_id)
    return invite


@router.get(PUBLIC + "/{token}")
@limiter.limit(public_read_limit)
def public_hq_invite(request: Request, token: str, session: Session = Depends(unscoped_session)):
    invite = _pending(session, token)
    parent, tenant = _target(session, invite.parent_account_id, invite.tenant_id)
    return {"name": parent.name, "email": invite.email, "full_name": invite.full_name,
            "tenant_slug": tenant.slug, "existing_account": _existing_user(session, invite) is not None,
            "expires_at": _utc(invite.expires_at)}


@router.post(PUBLIC + "/{token}/complete", response_model=TokenResponse)
@limiter.limit(public_write_limit)
def accept_hq_invite(request: Request, response: Response, token: str, payload: AcceptRequest, session: Session = Depends(unscoped_session)):
    invite = _pending(session, token)
    if len(payload.password.encode()) > 72:
        raise HTTPException(400, "Password must be at most 72 bytes.")
    user = _existing_user(session, invite)
    if user:
        if not user.is_active or user.role == "platform_admin" or not verify_password(payload.password, user.password_hash):
            raise HTTPException(403, "Use your existing password for this HQ account. Reset it from the login page if needed.")
    else:
        _validate_password_strength(payload.password)
        user = User(tenant_id=invite.tenant_id, email=invite.email, full_name=invite.full_name, role="owner", password_hash=hash_password(payload.password))
    now = datetime.now(timezone.utc)
    result = session.execute(update(HqOwnerInvite).where(HqOwnerInvite.id == invite.id, HqOwnerInvite.status == "pending", HqOwnerInvite.expires_at > now).values(status="completed", completed_at=now).execution_options(synchronize_session=False))
    if result.rowcount != 1:
        session.rollback()
        raise HTTPException(410, "This invitation is no longer valid.")
    try:
        session.add(user)
        session.flush()
        grant_parent_role(session, parent_id=invite.parent_account_id, user_id=user.id, role=PARENT_ROLE_HQ_ADMIN)
        _audit(session, invite, user, "accepted")
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "This account changed while accepting. Reload the invitation and try again.")
    invalidate_auth_cache()
    access, access_exp, refresh, refresh_exp = _issue_session_tokens(session, tenant_id=user.tenant_id, user_id=user.id, role=user.role, request=request)
    return deliver_tokens(request, response, TokenResponse(access_token=access, expires_in_seconds=access_exp,
        refresh_token=refresh, refresh_expires_in_seconds=refresh_exp))
