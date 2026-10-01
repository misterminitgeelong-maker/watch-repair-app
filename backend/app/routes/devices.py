"""Register phone-app push tokens for the signed-in user."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..database import get_session, unscoped_session
from ..dependencies import AuthContext, require_tech_or_above
from ..models import DeviceToken

router = APIRouter(prefix="/v1/me/devices", tags=["me"])


class DeviceRegister(BaseModel):
    token: str = Field(min_length=20, max_length=512)
    platform: str = Field(default="android", pattern="^(android|ios)$")


@router.post("", status_code=204)
def register_device(
    body: DeviceRegister,
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(unscoped_session),
):
    """Idempotent: a token moves to whoever registered it last (shared phones, re-logins).

    Unscoped on purpose: the same phone can sign in to a different shop, and the
    token's existing row may belong to the previous shop's tenant.
    """
    row = session.exec(select(DeviceToken).where(DeviceToken.token == body.token)).first()
    if row is None:
        session.add(DeviceToken(tenant_id=auth.tenant_id, user_id=auth.user_id, token=body.token, platform=body.platform))
    else:
        row.tenant_id = auth.tenant_id
        row.user_id = auth.user_id
        row.platform = body.platform
        row.last_seen_at = datetime.now(timezone.utc)
        session.add(row)
    session.commit()
    return None


@router.delete("", status_code=204)
def unregister_device(
    token: str,
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    row = session.exec(select(DeviceToken).where(DeviceToken.token == token, DeviceToken.user_id == auth.user_id)).first()
    if row is not None:
        session.delete(row)
        session.commit()
    return None
