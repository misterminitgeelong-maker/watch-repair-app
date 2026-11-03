"""Owner-controlled consent and compliance switches for one shop.

- Support access: the owner lets HQ / support staff in for a limited time.
- ID capture requirement: mobile-services jobs need an ID record before completion.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Field, Session, SQLModel

from ..database import get_session
from ..dependencies import AuthContext, get_auth_context, require_owner
from ..models import Tenant, TenantEventLog, User
from ..support_access import SUPPORT_ACCESS_DEFAULT_HOURS, SUPPORT_ACCESS_MAX_HOURS, grant_active

router = APIRouter(prefix="/v1/shop", tags=["shop-compliance"])


class SupportAccessRead(SQLModel):
    enabled: bool
    until: Optional[datetime] = None


class SupportAccessUpdate(SQLModel):
    #: Turn support access on (for `hours`) or off.
    enabled: bool
    hours: int = Field(default=SUPPORT_ACCESS_DEFAULT_HOURS, ge=1, le=SUPPORT_ACCESS_MAX_HOURS)


class IdCaptureSettingRead(SQLModel):
    require_id_capture: bool


def _real_owner(auth: AuthContext) -> None:
    """Consent has to come from the shop itself, never from someone acting through its login."""
    if auth.support_actor_user_id is not None:
        raise HTTPException(status_code=403, detail="Only the shop owner can change this, not a support session.")


def _tenant(session: Session, auth: AuthContext) -> Tenant:
    tenant = session.get(Tenant, auth.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Shop not found")
    return tenant


def _log(session: Session, auth: AuthContext, event_type: str, summary: str) -> None:
    user = session.get(User, auth.user_id)
    session.add(TenantEventLog(
        tenant_id=auth.tenant_id,
        actor_user_id=auth.user_id,
        actor_email=user.email if user else None,
        entity_type="tenant",
        entity_id=auth.tenant_id,
        event_type=event_type,
        event_summary=summary,
    ))


@router.get("/support-access", response_model=SupportAccessRead)
def get_support_access(auth: AuthContext = Depends(get_auth_context), session: Session = Depends(get_session)):
    tenant = _tenant(session, auth)
    active = grant_active(tenant)
    return SupportAccessRead(enabled=active, until=tenant.support_access_until if active else None)


@router.put("/support-access", response_model=SupportAccessRead)
def set_support_access(
    payload: SupportAccessUpdate,
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(get_session),
):
    _real_owner(auth)
    tenant = _tenant(session, auth)
    if payload.enabled:
        tenant.support_access_until = datetime.now(timezone.utc) + timedelta(hours=payload.hours)
        summary = f"Support access allowed for {payload.hours} h"
    else:
        tenant.support_access_until = None
        summary = "Support access turned off"
    session.add(tenant)
    _log(session, auth, "support_access_changed", summary)
    session.commit()
    active = grant_active(tenant)
    return SupportAccessRead(enabled=active, until=tenant.support_access_until if active else None)


@router.get("/id-capture-setting", response_model=IdCaptureSettingRead)
def get_id_capture_setting(auth: AuthContext = Depends(get_auth_context), session: Session = Depends(get_session)):
    return IdCaptureSettingRead(require_id_capture=bool(_tenant(session, auth).require_id_capture))


@router.put("/id-capture-setting", response_model=IdCaptureSettingRead)
def set_id_capture_setting(
    payload: IdCaptureSettingRead,
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(get_session),
):
    tenant = _tenant(session, auth)
    if tenant.require_id_capture != payload.require_id_capture:
        tenant.require_id_capture = payload.require_id_capture
        session.add(tenant)
        _log(session, auth, "id_capture_requirement_changed",
             "ID record now required before completing a mobile job" if payload.require_id_capture
             else "ID record no longer required before completing a mobile job")
        session.commit()
    return IdCaptureSettingRead(require_id_capture=bool(tenant.require_id_capture))
