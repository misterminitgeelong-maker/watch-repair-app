"""Read-only SMS fair-use usage for the current Melbourne calendar month.

Soft limit only: nothing here (or in the send path) blocks a message.
"""
import math
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from ..database import unscoped_session
from ..dependencies import AuthContext, require_owner
from ..models import NETWORK_ROLE_HQ, ParentAccountSite, Tenant
from ..parent_network import site_for_tenant_in_parent
from ..sms_controls import FAIR_USE_THRESHOLDS, usage_for_tenant
from ..tenant_scope import without_scope

router = APIRouter(prefix="/v1", tags=["sms-usage"])


class SmsUsageRead(BaseModel):
    tenant_id: UUID
    period_start: datetime
    period_end: datetime
    timezone: str = "Australia/Melbourne"
    sent: int
    suppressed: int
    limit: int
    percent_used: float | None
    remaining: int | None
    warn_threshold_reached: bool
    limit_reached: bool
    enforced: bool = False


def _hq_can_view(session: Session, auth: AuthContext, tenant_id: UUID) -> bool:
    with without_scope(session):
        parent_ids = session.exec(
            select(ParentAccountSite.parent_account_id)
            .where(ParentAccountSite.tenant_id == auth.tenant_id)
            .where(ParentAccountSite.network_role == NETWORK_ROLE_HQ)
        ).all()
    return any(site_for_tenant_in_parent(session, pid, tenant_id) is not None for pid in parent_ids)


@router.get("/sms/usage", response_model=SmsUsageRead)
def get_sms_usage(
    tenant_id: UUID | None = Query(default=None, description="Operator to inspect; defaults to your own shop"),
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(unscoped_session),
):
    """Outbound SMS this calendar month (Melbourne) against the soft fair-use limit.

    Owners see their own shop; a platform admin sees any tenant; an owner of an HQ
    tenant sees the operators linked to its network.
    """
    target_id = tenant_id or auth.tenant_id
    if target_id != auth.tenant_id and auth.role != "platform_admin":
        if not _hq_can_view(session, auth, target_id):
            # Same answer as a missing tenant so shop ids cannot be probed.
            raise HTTPException(status_code=404, detail="Tenant not found")
    if session.get(Tenant, target_id) is None:
        raise HTTPException(status_code=404, detail="Tenant not found")

    usage = usage_for_tenant(session, target_id)
    limit = usage.limit
    warn_at = math.ceil(limit * FAIR_USE_THRESHOLDS[0] / 100) if limit else None
    return SmsUsageRead(
        tenant_id=target_id,
        period_start=usage.period_start,
        period_end=usage.period_end,
        sent=usage.sent,
        suppressed=usage.suppressed,
        limit=limit,
        percent_used=round(usage.sent * 100 / limit, 1) if limit else None,
        remaining=max(0, limit - usage.sent) if limit else None,
        warn_threshold_reached=bool(limit and usage.sent >= warn_at),
        limit_reached=bool(limit and usage.sent >= limit),
    )
