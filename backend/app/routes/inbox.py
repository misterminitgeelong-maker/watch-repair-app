from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from ..database import get_session
from ..dependencies import AuthContext, get_auth_context
from ..models import TenantEventLog, TenantEventLogRead

router = APIRouter(prefix="/v1", tags=["inbox"])

INBOX_EVENT_TYPES = [
    "quote_approved",
    "quote_declined",
    "mobile_lead_quote_needed",
    "invoice_paid",
]


@router.delete("/inbox/{event_id}", status_code=204)
def delete_inbox_event(
    event_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    """Remove an inbox alert."""
    event = session.get(TenantEventLog, event_id)
    if not event or event.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Not found")
    if event.event_type not in INBOX_EVENT_TYPES:
        raise HTTPException(status_code=400, detail="Can only delete inbox alerts")
    session.delete(event)
    session.commit()
    return None


@router.get("/inbox", response_model=list[TenantEventLogRead])
def get_inbox(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    """Quote approvals/declines, website mobile leads, and invoice payments."""
    rows = session.exec(
        select(TenantEventLog)
        .where(TenantEventLog.tenant_id == auth.tenant_id)
        .where(TenantEventLog.event_type.in_(INBOX_EVENT_TYPES))
        .order_by(TenantEventLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return rows
