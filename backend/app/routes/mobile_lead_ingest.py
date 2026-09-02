"""Public webhook: website submits mobile key enquiry → routed to Lead Inbox + SMS/email alert.

This is an async enquiry, not a live lead — no offer timer, no operator-to-operator cascade.
Compare shop_mobile_bookings.py, which handles the live, timed "book mobile now" case.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..database import get_session
from ..limiter import limiter
from ..models import ParentAccount
from ..security import verify_password
from ..services.mobile_lead_dispatch import lead_payload_from_body, route_website_lead_to_prospect
from ..minit_mobile_routing import AU_STATES, normalize_suburb_name

router = APIRouter(prefix="/v1/public", tags=["mobile-lead-ingest"])


class MobileKeyLeadIngestBody(BaseModel):
    suburb: str = Field(..., min_length=1, max_length=200)
    state_code: str = Field(..., min_length=2, max_length=8)
    customer_name: str = Field(..., min_length=1, max_length=300)
    phone: str | None = Field(default=None, max_length=80)
    email: str | None = Field(default=None, max_length=320)
    vehicle_make: str | None = Field(default=None, max_length=120)
    vehicle_model: str | None = Field(default=None, max_length=120)
    registration_plate: str | None = Field(default=None, max_length=32)
    street_address: str | None = Field(default=None, max_length=500)
    website_notes: str | None = Field(default=None, max_length=4000)
    key_service_result: str | None = Field(default=None, max_length=500)


@router.post("/mobile-key-leads/{ingest_public_id}")
@limiter.limit("60/minute")
def ingest_mobile_key_lead(
    request: Request,
    ingest_public_id: UUID,
    body: MobileKeyLeadIngestBody,
    session: Session = Depends(get_session),
    x_mobile_lead_secret: str | None = Header(default=None, alias="X-Mobile-Lead-Secret"),
):
    """Accept a lead from your public website (e.g. Mister Minit key checker). Requires configured parent account + routes.

    Header: ``X-Mobile-Lead-Secret``: shared secret (set in Parent account → Website lead feed).
    """
    if not x_mobile_lead_secret or len(x_mobile_lead_secret) < 16:
        raise HTTPException(status_code=401, detail="Missing or invalid X-Mobile-Lead-Secret header")

    parent = session.exec(
        select(ParentAccount).where(ParentAccount.mobile_lead_ingest_public_id == ingest_public_id)
    ).first()
    if not parent or not parent.mobile_lead_webhook_secret_hash:
        raise HTTPException(status_code=404, detail="Unknown ingest endpoint")

    if not verify_password(x_mobile_lead_secret, parent.mobile_lead_webhook_secret_hash):
        raise HTTPException(status_code=401, detail="Invalid secret")

    st = body.state_code.strip().upper()
    if st not in AU_STATES:
        raise HTTPException(status_code=400, detail=f"Invalid state_code; use one of: {', '.join(sorted(AU_STATES))}")

    sub_norm = normalize_suburb_name(body.suburb)
    if not sub_norm:
        raise HTTPException(status_code=400, detail="suburb is required")

    payload = lead_payload_from_body(body)
    try:
        lead = route_website_lead_to_prospect(
            session,
            parent=parent,
            payload=payload,
            suburb=body.suburb.strip(),
            state_code=st,
        )
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=(
                "No operator or HQ escalation site configured for this lead. "
                "Configure suburb routes, a fallback operator, or an HQ escalation site."
            ),
        )
    session.commit()
    session.refresh(lead)

    return {
        "lead_id": str(lead.id),
        "tenant_id": str(lead.tenant_id),
        "message": "Lead added to the operator's Lead Inbox; they've been alerted by SMS and email.",
    }
