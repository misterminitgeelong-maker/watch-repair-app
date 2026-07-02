"""Public webhook: website submits mobile key enquiry → dispatch cascade + inbox alert."""

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..database import get_session
from ..limiter import limiter
from ..models import ParentAccount
from ..security import verify_password
from ..services.mobile_lead_dispatch import lead_payload_from_body, start_mobile_lead_dispatch
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
    dispatch = start_mobile_lead_dispatch(
        session,
        parent=parent,
        payload=payload,
        suburb=body.suburb.strip(),
        state_code=st,
    )
    if dispatch.status == "failed" and not dispatch.auto_key_job_id:
        raise HTTPException(
            status_code=422,
            detail=(
                "No operator or HQ escalation site configured for this lead. "
                "Configure suburb routes, a fallback operator, or an HQ escalation site."
            ),
        )
    session.commit()
    session.refresh(dispatch)

    job_id = dispatch.auto_key_job_id
    tenant_id = dispatch.current_operator_tenant_id
    message = "Lead dispatched to mobile operator; quote within the configured time window."
    if dispatch.status == "escalated_hq":
        message = "No operator available; lead escalated to HQ for manual quoting."

    return {
        "dispatch_id": str(dispatch.id),
        "dispatch_status": dispatch.status,
        "job_id": str(job_id) if job_id else None,
        "tenant_id": str(tenant_id) if tenant_id else None,
        "offer_expires_at": dispatch.offer_expires_at.isoformat() if dispatch.offer_expires_at else None,
        "message": message,
    }
