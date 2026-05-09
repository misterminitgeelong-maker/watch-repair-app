from fastapi import APIRouter, Depends, Form
from fastapi.responses import Response
from sqlmodel import Session, select

from ..database import get_session
from ..models import SmsLog, TenantEventLog

router = APIRouter(prefix="/v1", tags=["sms-webhook"])

_EMPTY_TWIML = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'


@router.post("/webhook/sms/incoming", include_in_schema=False)
def twilio_incoming_sms(
    From: str = Form(...),
    Body: str = Form(...),
    session: Session = Depends(get_session),
):
    """
    Twilio webhook — configure your Twilio number's inbound webhook URL here.
    Stores the customer's reply in the inbox and returns empty TwiML so
    Twilio doesn't auto-reply.
    """
    from_phone = From.strip()
    body_text = Body.strip()

    # Match the sender to a tenant by finding the most recent outbound SMS we sent them
    row = session.exec(
        select(SmsLog)
        .where(SmsLog.to_phone == from_phone)
        .where(SmsLog.status == "sent")
        .order_by(SmsLog.created_at.desc())
    ).first()

    if row:
        entity_id = row.repair_job_id or row.shoe_repair_job_id or row.auto_key_job_id
        if row.repair_job_id:
            entity_type = "repair_job"
        elif row.shoe_repair_job_id:
            entity_type = "shoe_repair_job"
        elif row.auto_key_job_id:
            entity_type = "auto_key_job"
        else:
            entity_type = "customer"

        session.add(TenantEventLog(
            tenant_id=row.tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            event_type="customer_sms_reply",
            event_summary=f"{from_phone}: {body_text[:200]}",
        ))
        session.commit()

    return Response(content=_EMPTY_TWIML, media_type="text/xml")
