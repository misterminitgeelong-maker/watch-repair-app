from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, func, select

from ..database import get_session
from ..dependencies import AuthContext, get_auth_context
from ..models import TenantEventLog, TenantEventLogRead

router = APIRouter(prefix="/v1", tags=["inbox"])

INBOX_EVENT_TYPES = [
    "quote_approved",
    "quote_declined",
    "mobile_lead_quote_needed",
    "inbound_email_received",
    "shop_booking_pending",
    "invoice_paid",
    "customer_sms_reply",
    "portal_customer_message",
]


class InboxCountRead(BaseModel):
    count: int


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


@router.get("/inbox/count", response_model=InboxCountRead)
def get_inbox_count(
    exclude: str | None = Query(
        default=None,
        description="Comma-separated event types to omit (e.g. inbound_email_received for HQ nav)",
    ),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    """Lightweight badge count — avoids fetching full inbox rows on every screen."""
    exclude_set = {e.strip() for e in (exclude or "").split(",") if e.strip()}
    types = [t for t in INBOX_EVENT_TYPES if t not in exclude_set]
    if not types:
        return InboxCountRead(count=0)
    count = session.exec(
        select(func.count())
        .select_from(TenantEventLog)
        .where(TenantEventLog.tenant_id == auth.tenant_id)
        .where(TenantEventLog.event_type.in_(types))
    ).one()
    return InboxCountRead(count=int(count))


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
