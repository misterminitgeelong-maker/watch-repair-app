"""Twilio inbound SMS webhook — processes customer replies to quote/booking texts."""
import logging

from fastapi import APIRouter, Form, Request, Response
from sqlmodel import Session, select

from ..database import engine
from ..models import AutoKeyJob, AutoKeyQuote, SmsLog, TenantEventLog

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])

_TWIML_EMPTY = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'


def _twiml(message: str) -> Response:
    body = f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{message}</Message></Response>'
    return Response(content=body, media_type="application/xml")


@router.post("/sms")
async def inbound_sms(
    request: Request,
    From: str = Form(...),
    Body: str = Form(...),
):

    reply = Body.strip().upper()
    from_phone = From.strip()

    with Session(engine) as session:
        # Find the most recent auto_key_quote_sent SMS to this number
        sms_log = session.exec(
            select(SmsLog)
            .where(SmsLog.to_phone == from_phone)
            .where(SmsLog.event == "auto_key_quote_sent")
            .where(SmsLog.auto_key_job_id.is_not(None))
            .order_by(SmsLog.created_at.desc())
        ).first()

        if not sms_log or not sms_log.auto_key_job_id:
            logger.info("sms_webhook.no_matching_job from=%s body=%r", from_phone, Body)
            return Response(content=_TWIML_EMPTY, media_type="application/xml")

        job = session.get(AutoKeyJob, sms_log.auto_key_job_id)
        if not job:
            return Response(content=_TWIML_EMPTY, media_type="application/xml")

        # Find the most recent sent quote for this job
        quote = session.exec(
            select(AutoKeyQuote)
            .where(AutoKeyQuote.auto_key_job_id == job.id)
            .where(AutoKeyQuote.status == "sent")
            .order_by(AutoKeyQuote.created_at.desc())
        ).first()

        if not quote:
            logger.info("sms_webhook.no_sent_quote job=%s from=%s", job.id, from_phone)
            return Response(content=_TWIML_EMPTY, media_type="application/xml")

        if reply in ("YES", "Y", "YEP", "YEAH", "OK", "CONFIRM", "CONFIRMED", "APPROVE", "APPROVED"):
            quote.status = "approved"
            if job.status == "quote_sent":
                job.status = "go_ahead"
            session.add(TenantEventLog(
                tenant_id=job.tenant_id,
                entity_type="auto_key_job",
                entity_id=job.id,
                event_type="quote_approved_sms",
                event_summary=f"Customer approved quote for job #{job.job_number} via SMS reply",
            ))
            session.commit()
            logger.info("sms_webhook.quote_approved job=%s", job.id)
            return _twiml("Thanks! Your quote is confirmed. We'll be in touch to arrange your appointment.")

        if reply in ("NO", "N", "NOPE", "CANCEL", "DECLINE", "DECLINED"):
            quote.status = "declined"
            session.add(TenantEventLog(
                tenant_id=job.tenant_id,
                entity_type="auto_key_job",
                entity_id=job.id,
                event_type="quote_declined_sms",
                event_summary=f"Customer declined quote for job #{job.job_number} via SMS reply",
            ))
            session.commit()
            logger.info("sms_webhook.quote_declined job=%s", job.id)
            return _twiml("Understood, your quote has been declined. Contact us if you change your mind.")

        # Unrecognised reply — don't log an error, just ignore silently
        logger.info("sms_webhook.unrecognised_reply from=%s body=%r", from_phone, Body)
        return Response(content=_TWIML_EMPTY, media_type="application/xml")
