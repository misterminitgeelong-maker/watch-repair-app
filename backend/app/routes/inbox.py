from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from ..database import get_session
from ..dependencies import AuthContext, get_auth_context
from ..models import TenantEventLog, TenantEventLogRead

router = APIRouter(prefix="/v1", tags=["inbox"])


@router.get("/inbox", response_model=list[TenantEventLogRead])
def get_inbox(
    limit: int = Query(default=50, ge=1, le=200),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    """Alerts from customer quote approvals and declines."""
    rows = session.exec(
        select(TenantEventLog)
        .where(TenantEventLog.tenant_id == auth.tenant_id)
        .where(TenantEventLog.event_type.in_(["quote_approved", "quote_declined"]))
        .order_by(TenantEventLog.created_at.desc())
        .limit(limit)
    ).all()
    return rows
