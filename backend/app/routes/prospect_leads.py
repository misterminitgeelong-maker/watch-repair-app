from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from ..database import get_session
from ..dependencies import AuthContext, get_auth_context
from ..models import CustomerAccount, ProspectLead

router = APIRouter(prefix="/v1/prospect-leads", tags=["prospect-leads"])

STATUSES = ["new", "contacted", "visited", "onboarded"]
ALLOWED_STATUSES = set(STATUSES) | {"quote_needed", "follow_up_due", "won", "lost"}


class ProspectLeadOut(BaseModel):
    id: str
    tenant_id: str
    place_id: Optional[str]
    name: str
    address: Optional[str]
    phone: Optional[str]
    website: Optional[str]
    rating: Optional[float]
    review_count: Optional[int]
    category: Optional[str]
    state_code: Optional[str]
    contact_name: Optional[str]
    contact_email: Optional[str]
    notes: Optional[str]
    status: str
    visit_scheduled_at: Optional[datetime]
    customer_account_id: Optional[str]
    created_at: datetime
    updated_at: datetime


class SaveLeadBody(BaseModel):
    place_id: Optional[str] = None
    name: str
    address: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    category: Optional[str] = None
    state_code: Optional[str] = None


class UpdateLeadBody(BaseModel):
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None
    visit_scheduled_at: Optional[datetime] = None


def _apply_details(lead: ProspectLead, body: UpdateLeadBody) -> None:
    # Explicit null clears a field; omitted fields remain unchanged.
    for field in ("contact_name", "contact_email", "notes", "visit_scheduled_at"):
        if field in body.model_fields_set:
            setattr(lead, field, getattr(body, field))


def _ensure_account(lead: ProspectLead, session: Session) -> None:
    if lead.customer_account_id:
        return
    account = CustomerAccount(
        tenant_id=lead.tenant_id, name=lead.name,
        contact_name=lead.contact_name, contact_email=lead.contact_email,
        contact_phone=lead.phone, billing_address=lead.address, notes=lead.notes,
    )
    session.add(account)
    session.flush()
    lead.customer_account_id = account.id


def _out(lead: ProspectLead) -> ProspectLeadOut:
    return ProspectLeadOut(
        id=str(lead.id),
        tenant_id=str(lead.tenant_id),
        place_id=lead.place_id,
        name=lead.name,
        address=lead.address,
        phone=lead.phone,
        website=lead.website,
        rating=lead.rating,
        review_count=lead.review_count,
        category=lead.category,
        state_code=lead.state_code,
        contact_name=lead.contact_name,
        contact_email=lead.contact_email,
        notes=lead.notes,
        status=lead.status,
        visit_scheduled_at=lead.visit_scheduled_at,
        customer_account_id=str(lead.customer_account_id) if lead.customer_account_id else None,
        created_at=lead.created_at,
        updated_at=lead.updated_at,
    )


@router.get("", response_model=list[ProspectLeadOut])
def list_leads(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    leads = session.exec(
        select(ProspectLead)
        .where(ProspectLead.tenant_id == auth.tenant_id)
        .order_by(ProspectLead.created_at.desc())
    ).all()
    return [_out(l) for l in leads]


@router.post("", response_model=ProspectLeadOut)
def save_lead(
    body: SaveLeadBody,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    if body.place_id:
        existing = session.exec(
            select(ProspectLead)
            .where(ProspectLead.tenant_id == auth.tenant_id)
            .where(ProspectLead.place_id == body.place_id)
        ).first()
        if existing:
            return _out(existing)

    lead = ProspectLead(
        tenant_id=auth.tenant_id,
        place_id=body.place_id,
        name=body.name,
        address=body.address,
        phone=body.phone,
        website=body.website,
        rating=body.rating,
        review_count=body.review_count,
        category=body.category,
        state_code=body.state_code,
    )
    session.add(lead)
    session.commit()
    session.refresh(lead)
    return _out(lead)


@router.patch("/{lead_id}", response_model=ProspectLeadOut)
def update_lead(
    lead_id: str,
    body: UpdateLeadBody,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    lead = session.exec(
        select(ProspectLead)
        .where(ProspectLead.id == UUID(lead_id))
        .where(ProspectLead.tenant_id == auth.tenant_id)
    ).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    _apply_details(lead, body)
    if body.status is not None:
        if body.status not in ALLOWED_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid prospect status")
        lead.status = body.status
    if lead.status in {"onboarded", "won"}:
        _ensure_account(lead, session)

    lead.updated_at = datetime.now(timezone.utc)
    session.add(lead)
    session.commit()
    session.refresh(lead)
    return _out(lead)


@router.delete("/{lead_id}")
def delete_lead(
    lead_id: str,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    lead = session.exec(
        select(ProspectLead)
        .where(ProspectLead.id == UUID(lead_id))
        .where(ProspectLead.tenant_id == auth.tenant_id)
    ).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    session.delete(lead)
    session.commit()
    return {"ok": True}


@router.post("/{lead_id}/advance", response_model=ProspectLeadOut)
def advance_lead(
    lead_id: str,
    body: Optional[UpdateLeadBody] = Body(default=None),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    lead = session.exec(
        select(ProspectLead)
        .where(ProspectLead.id == UUID(lead_id))
        .where(ProspectLead.tenant_id == auth.tenant_id)
    ).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    if body:
        _apply_details(lead, body)
    next_status = {"new": "contacted", "quote_needed": "contacted", "follow_up_due": "contacted", "contacted": "visited", "visited": "onboarded"}
    if lead.status in next_status:
        lead.status = next_status[lead.status]
    elif lead.status not in {"onboarded", "won"}:
        raise HTTPException(status_code=400, detail="This prospect cannot be advanced. Restore it to an active stage first.")
    if lead.status in {"onboarded", "won"}:
        _ensure_account(lead, session)
    lead.updated_at = datetime.now(timezone.utc)
    session.add(lead)
    session.commit()
    session.refresh(lead)
    return _out(lead)
