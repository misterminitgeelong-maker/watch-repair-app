from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from ..database import get_session
from ..dependencies import AuthContext, get_auth_context
from ..models import CustomerAccount, ProspectLead

router = APIRouter(prefix="/v1/prospect-leads", tags=["prospect-leads"])

STATUSES = ["new", "contacted", "visited", "onboarded"]


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

    if body.contact_name is not None:
        lead.contact_name = body.contact_name
    if body.contact_email is not None:
        lead.contact_email = body.contact_email
    if body.notes is not None:
        lead.notes = body.notes
    if body.status is not None:
        if body.status not in STATUSES:
            raise HTTPException(status_code=400, detail=f"Invalid status. Choose from: {', '.join(STATUSES)}")
        lead.status = body.status
    if body.visit_scheduled_at is not None:
        lead.visit_scheduled_at = body.visit_scheduled_at

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

    current_idx = STATUSES.index(lead.status) if lead.status in STATUSES else 0
    if current_idx < len(STATUSES) - 1:
        lead.status = STATUSES[current_idx + 1]
        lead.updated_at = datetime.now(timezone.utc)

        if lead.status == "onboarded" and not lead.customer_account_id:
            account = CustomerAccount(
                tenant_id=lead.tenant_id,
                name=lead.name,
                contact_name=lead.contact_name,
                contact_email=lead.contact_email,
                contact_phone=lead.phone,
                billing_address=lead.address,
                notes=lead.notes,
            )
            session.add(account)
            session.flush()
            lead.customer_account_id = account.id

        session.add(lead)
        session.commit()
        session.refresh(lead)
    return _out(lead)
