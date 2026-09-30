"""HQ account troubleshooting: HQ admins help people in their own network.

Everything here is limited to HQ admins and to users of
sites linked to HQ's own network. HQ never sees or sets a password: a reset is
a one-time link the person opens themselves. Every change is written to HQ's
activity log.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, col, select

from .. import email_client
from .. import sms as sms_service
from ..config import settings
from ..database import unscoped_session
from ..dependencies import AuthContext, invalidate_auth_cache, require_feature, require_owner
from ..models import (
    EmailLog,
    ParentAccount,
    ParentAccountUser,
    RefreshSession,
    ShopOwnerInvite,
    SmsLog,
    Tenant,
    TenantEventLog,
    User,
)
from .parent_accounts import (
    SHOP_OWNER_INVITE_EXPIRY_DAYS,
    _parent_for_write,
    _record_event,
    _tenant_linked_to_parent,
)

router = APIRouter(
    prefix="/v1/parent-accounts",
    tags=["hq-account-support"],
    dependencies=[Depends(require_feature("multi_site"))],
)


class HqAccountRead(SQLModel):
    user_id: UUID
    email: str
    full_name: str
    role: str
    mobile: Optional[str] = None
    is_active: bool
    last_login_at: Optional[datetime] = None
    #: A copy of an HQ login: reset it through the shop invite, not here.
    is_hq_login: bool = False
    #: pending | completed | revoked | expired, for the latest link sent to this user.
    latest_link_status: Optional[str] = None
    latest_link_sent_at: Optional[datetime] = None


class HqAccountEmailBody(SQLModel):
    email: str


class HqResetLinkResponse(SQLModel):
    email_sent: bool
    sms_sent: bool
    sent_to_email: Optional[str] = None
    expires_at: datetime


class HqMessageLogRead(SQLModel):
    channel: str
    to: str
    event: str
    status: str
    error: Optional[str] = None
    created_at: datetime


def _mask_email(email: str) -> str:
    local, _, domain = (email or "").partition("@")
    if not domain:
        return ""
    return f"{local[:1]}***@{domain}"


def _target_user(session: Session, parent: ParentAccount, tenant_id: UUID, user_id: UUID) -> tuple[Tenant, User]:
    if not _tenant_linked_to_parent(session, parent.id, tenant_id):
        raise HTTPException(status_code=404, detail="Site is not linked to your account")
    tenant = session.get(Tenant, tenant_id)
    user = session.get(User, user_id)
    if not tenant or not user or user.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="User not found")
    return tenant, user


def _require_not_hq_login(session: Session, user: User) -> None:
    """A copy of an HQ login carries HQ access; claiming it drops that access,
    so changing it here would lock HQ out. Those go through the shop invite."""
    grant = session.exec(select(ParentAccountUser.id).where(ParentAccountUser.user_id == user.id).limit(1)).first()
    if grant is not None:
        raise HTTPException(
            status_code=409,
            detail="This is an HQ login. Use the shop invite to hand it to the shop instead.",
        )


def _revoke_sessions(session: Session, user_id: UUID) -> None:
    now = datetime.now(timezone.utc)
    for row in session.exec(
        select(RefreshSession).where(RefreshSession.user_id == user_id).where(RefreshSession.revoked_at.is_(None))
    ).all():
        row.revoked_at = now
        session.add(row)


@router.get("/me/sites/{tenant_id}/accounts", response_model=list[HqAccountRead])
def list_site_accounts(
    tenant_id: UUID,
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(unscoped_session),
):
    """Everyone with a login at a site, with sign-in and reset-link status."""
    _user, parent = _parent_for_write(session, auth)
    if not _tenant_linked_to_parent(session, parent.id, tenant_id):
        raise HTTPException(status_code=404, detail="Site is not linked to your account")
    users = session.exec(select(User).where(User.tenant_id == tenant_id).order_by(col(User.created_at))).all()
    ids = [u.id for u in users]
    granted = set(session.exec(select(ParentAccountUser.user_id).where(col(ParentAccountUser.user_id).in_(ids))).all()) if ids else set()
    last_login: dict[UUID, datetime] = {}
    for actor_id, created in session.exec(
        select(TenantEventLog.actor_user_id, TenantEventLog.created_at)
        .where(TenantEventLog.tenant_id == tenant_id)
        .where(TenantEventLog.event_type == "login")
        .order_by(col(TenantEventLog.created_at))
    ).all():
        if actor_id is not None:
            last_login[actor_id] = created
    latest_link: dict[UUID, ShopOwnerInvite] = {}
    for invite in session.exec(
        select(ShopOwnerInvite)
        .where(ShopOwnerInvite.tenant_id == tenant_id)
        .order_by(col(ShopOwnerInvite.created_at))
    ).all():
        latest_link[invite.owner_user_id] = invite
    now = datetime.now(timezone.utc)
    out = []
    for u in users:
        link = latest_link.get(u.id)
        status = link.status if link else None
        if link and status == "pending":
            expires = link.expires_at if link.expires_at.tzinfo else link.expires_at.replace(tzinfo=timezone.utc)
            if expires < now:
                status = "expired"
        out.append(
            HqAccountRead(
                user_id=u.id,
                email=u.email,
                full_name=u.full_name,
                role=u.role,
                mobile=u.mobile,
                is_active=u.is_active,
                last_login_at=last_login.get(u.id),
                is_hq_login=u.id in granted,
                latest_link_status=status,
                latest_link_sent_at=link.created_at if link else None,
            )
        )
    return out


@router.post("/me/sites/{tenant_id}/accounts/{user_id}/reset-link", response_model=HqResetLinkResponse)
def send_account_reset_link(
    tenant_id: UUID,
    user_id: UUID,
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(unscoped_session),
):
    """Email and/or text the person a one-time link to choose their own new
    email and password. HQ is never shown the link."""
    hq_user, parent = _parent_for_write(session, auth)
    tenant, target = _target_user(session, parent, tenant_id, user_id)
    _require_not_hq_login(session, target)
    if not target.is_active:
        raise HTTPException(status_code=409, detail="This account is deactivated")
    to_email = (target.email or "").strip()
    to_phone = (target.mobile or "").strip() or None
    if "@" not in to_email and not to_phone:
        raise HTTPException(status_code=409, detail="No email or mobile on file to send the link to")

    for row in session.exec(
        select(ShopOwnerInvite)
        .where(ShopOwnerInvite.owner_user_id == target.id)
        .where(ShopOwnerInvite.status == "pending")
    ).all():
        row.status = "revoked"
        session.add(row)
    invite = ShopOwnerInvite(
        tenant_id=tenant.id,
        parent_account_id=parent.id,
        owner_user_id=target.id,
        created_by_user_id=hq_user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=SHOP_OWNER_INVITE_EXPIRY_DAYS),
    )
    session.add(invite)
    _record_event(
        session,
        parent_account_id=parent.id,
        tenant_id=tenant.id,
        actor_user_id=hq_user.id,
        actor_email=hq_user.email,
        event_type="account_reset_link_sent",
        event_summary=f"Sent a login reset link to {target.email} at '{tenant.name}'",
    )
    session.commit()
    session.refresh(invite)

    reset_url = f"{settings.public_base_url.rstrip('/')}/shop-invite/{invite.token}"
    email_sent = sms_sent = False
    log = logging.getLogger(__name__)
    if "@" in to_email:
        try:
            email_sent, _ = email_client.send_account_reset_email(
                to_email=to_email,
                full_name=target.full_name,
                tenant_name=tenant.name,
                reset_url=reset_url,
                expiry_days=SHOP_OWNER_INVITE_EXPIRY_DAYS,
                session=session,
                tenant_id=tenant.id,
            )
        except Exception:
            log.exception("Failed to send account reset email for user %s", target.id)
    if to_phone:
        try:
            sms_sent = sms_service.notify_account_reset(
                session,
                tenant_id=tenant.id,
                to_phone=to_phone,
                tenant_name=tenant.name,
                reset_url=reset_url,
                expiry_days=SHOP_OWNER_INVITE_EXPIRY_DAYS,
            )
        except Exception:
            log.exception("Failed to send account reset SMS for user %s", target.id)
    session.commit()
    return HqResetLinkResponse(
        email_sent=email_sent,
        sms_sent=sms_sent,
        sent_to_email=_mask_email(to_email) if email_sent else None,
        expires_at=invite.expires_at,
    )


@router.patch("/me/sites/{tenant_id}/accounts/{user_id}/email", response_model=HqAccountRead)
def change_account_email(
    tenant_id: UUID,
    user_id: UUID,
    body: HqAccountEmailBody,
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(unscoped_session),
):
    """Correct someone's login email (a typo, or an address they can't reach)."""
    hq_user, parent = _parent_for_write(session, auth)
    tenant, target = _target_user(session, parent, tenant_id, user_id)
    _require_not_hq_login(session, target)
    new_email = body.email.strip().lower()
    if not new_email or "@" not in new_email:
        raise HTTPException(status_code=400, detail="A valid email is required")
    old_email = target.email
    if new_email == (old_email or "").strip().lower():
        raise HTTPException(status_code=400, detail="That is already this account's email")
    clash = session.exec(
        select(User.id).where(User.tenant_id == tenant.id).where(User.email == new_email).where(User.id != target.id)
    ).first()
    if clash is not None:
        raise HTTPException(status_code=409, detail="That email is already in use at this shop")
    target.email = new_email
    session.add(target)
    _revoke_sessions(session, target.id)
    _record_event(
        session,
        parent_account_id=parent.id,
        tenant_id=tenant.id,
        actor_user_id=hq_user.id,
        actor_email=hq_user.email,
        event_type="account_email_changed",
        event_summary=f"Changed login email at '{tenant.name}' from {old_email} to {new_email}",
    )
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="That email is already in use at this shop")
    invalidate_auth_cache()
    session.refresh(target)
    return HqAccountRead(
        user_id=target.id,
        email=target.email,
        full_name=target.full_name,
        role=target.role,
        mobile=target.mobile,
        is_active=target.is_active,
    )


@router.get("/me/sites/{tenant_id}/message-logs", response_model=list[HqMessageLogRead])
def list_site_message_logs(
    tenant_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(unscoped_session),
):
    """Recent SMS and emails a site sent, newest first. Message text is left
    out: it often carries customer details."""
    _user, parent = _parent_for_write(session, auth)
    if not _tenant_linked_to_parent(session, parent.id, tenant_id):
        raise HTTPException(status_code=404, detail="Site is not linked to your account")
    rows = [
        HqMessageLogRead(channel="sms", to=r.to_phone, event=r.event, status=r.status, created_at=r.created_at)
        for r in session.exec(
            select(SmsLog).where(SmsLog.tenant_id == tenant_id).order_by(col(SmsLog.created_at).desc()).limit(limit)
        ).all()
    ] + [
        HqMessageLogRead(
            channel="email", to=r.to_email, event=r.event, status=r.status, error=r.error, created_at=r.created_at
        )
        for r in session.exec(
            select(EmailLog).where(EmailLog.tenant_id == tenant_id).order_by(col(EmailLog.created_at).desc()).limit(limit)
        ).all()
    ]
    rows.sort(key=lambda r: r.created_at, reverse=True)
    return rows[:limit]
