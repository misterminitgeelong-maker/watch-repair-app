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


_ENQUIRY_SERVICES = {
    "lost_all_keys": "Lost all keys",
    "spare_key": "Spare key (I still have a working key)",
    "broken_key": "Broken or damaged key",
    "locked_out": "Locked out of the car",
    "remote_repair": "Remote / key fob repair or replacement",
    "other": "Something else",
}
_ENQUIRY_KEY_TYPES = {
    "standard": "Standard metal key",
    "remote_flip": "Remote / flip key",
    "push_start": "Push-button start (smart key)",
    "unsure": "Not sure",
}
_ENQUIRY_LOCATIONS = {
    "home": "At home",
    "work": "At work",
    "roadside": "Roadside / street",
    "carpark": "Car park / shopping centre",
    "other": "Other",
}
_ENQUIRY_URGENCY = {
    "asap": "As soon as possible",
    "today": "Today",
    "this_week": "This week",
    "flexible": "Flexible",
}


class KeyEnquiryBody(BaseModel):
    """Public car key enquiry form. Richer than the webhook body so operators can quote without a call-back."""

    customer_name: str = Field(..., min_length=1, max_length=300)
    phone: str = Field(..., min_length=6, max_length=80)
    email: str | None = Field(default=None, max_length=320)
    suburb: str = Field(..., min_length=1, max_length=200)
    state_code: str = Field(..., min_length=2, max_length=8)
    street_address: str | None = Field(default=None, max_length=500)
    location_type: str | None = Field(default=None, max_length=32)
    service: str = Field(..., max_length=32)
    key_type: str | None = Field(default=None, max_length=32)
    vehicle_make: str = Field(..., min_length=1, max_length=120)
    vehicle_model: str | None = Field(default=None, max_length=120)
    vehicle_year: str | None = Field(default=None, max_length=10)
    registration_plate: str | None = Field(default=None, max_length=32)
    has_working_key: bool | None = None
    urgency: str | None = Field(default=None, max_length=32)
    notes: str | None = Field(default=None, max_length=2000)
    #: Honeypot: real people never see or fill this.
    website: str | None = Field(default=None, max_length=200)


def _enquiry_option(options: dict[str, str], value: str | None, field: str) -> str | None:
    if not value:
        return None
    if value not in options:
        raise HTTPException(status_code=400, detail=f"Invalid {field}")
    return options[value]


@router.post("/key-enquiry/{ingest_public_id}")
@limiter.limit("10/minute")
def submit_key_enquiry(
    request: Request,
    ingest_public_id: UUID,
    body: KeyEnquiryBody,
    session: Session = Depends(get_session),
):
    """Public car key enquiry form → same routing as the website lead feed (operator Lead Inbox, else HQ).

    No shared secret: the form is public by design. The unguessable ingest id, a per-IP rate
    limit and a honeypot field keep it from being abused.
    """
    if body.website:
        # Bot filled the hidden field — pretend success so it doesn't retry.
        return {"message": "Thanks, we'll be in touch shortly."}

    parent = session.exec(
        select(ParentAccount).where(ParentAccount.mobile_lead_ingest_public_id == ingest_public_id)
    ).first()
    if not parent:
        raise HTTPException(status_code=404, detail="Unknown enquiry form")

    st = body.state_code.strip().upper()
    if st not in AU_STATES:
        raise HTTPException(status_code=400, detail=f"Invalid state_code; use one of: {', '.join(sorted(AU_STATES))}")
    if not normalize_suburb_name(body.suburb):
        raise HTTPException(status_code=400, detail="suburb is required")

    service = _enquiry_option(_ENQUIRY_SERVICES, body.service, "service")
    if not service:
        raise HTTPException(status_code=400, detail="service is required")
    lines = [f"Service: {service}"]
    for label, text in (
        ("Key type", _enquiry_option(_ENQUIRY_KEY_TYPES, body.key_type, "key_type")),
        ("Car location", _enquiry_option(_ENQUIRY_LOCATIONS, body.location_type, "location_type")),
        ("When needed", _enquiry_option(_ENQUIRY_URGENCY, body.urgency, "urgency")),
    ):
        if text:
            lines.append(f"{label}: {text}")
    if body.has_working_key is not None:
        lines.append(f"Has a working key: {'Yes' if body.has_working_key else 'No'}")
    if body.vehicle_year and body.vehicle_year.strip():
        lines.append(f"Year: {body.vehicle_year.strip()}")
    if body.street_address and body.street_address.strip():
        lines.append(f"Address: {body.street_address.strip()}")
    if body.notes and body.notes.strip():
        lines.append(f"Customer notes: {body.notes.strip()}")

    payload = {
        "customer_name": body.customer_name,
        "phone": body.phone,
        "email": body.email,
        "vehicle_make": body.vehicle_make,
        "vehicle_model": body.vehicle_model,
        "registration_plate": body.registration_plate,
        "website_notes": "\n".join(lines),
    }
    try:
        lead = route_website_lead_to_prospect(
            session,
            parent=parent,
            payload=payload,
            suburb=body.suburb.strip(),
            state_code=st,
        )
    except ValueError:
        raise HTTPException(status_code=503, detail="We can't take online enquiries right now. Please call us instead.")
    session.commit()
    return {"message": "Thanks, we'll be in touch shortly."}
