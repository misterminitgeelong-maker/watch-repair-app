import logging
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, Form
from fastapi.responses import Response
from sqlmodel import Session, select

from ..database import get_session
from ..models import (
    Approval,
    AutoKeyJob,
    Customer,
    JobMessage,
    JobStatusHistory,
    Quote,
    RepairJob,
    Shoe,
    ShoeRepairJob,
    SmsLog,
    TenantEventLog,
    Watch,
)
from ..phone_utils import normalize_phone as _normalize_phone, phones_match as _phones_match

router = APIRouter(prefix="/v1", tags=["sms-webhook"])

logger = logging.getLogger(__name__)


def _mask_phone(raw: str) -> str:
    digits = "".join(ch for ch in (raw or "") if ch.isdigit())
    return f"…{digits[-3:]}" if len(digits) >= 3 else "unknown"

_EMPTY_TWIML = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'

# Keyword replies honoured for watch repair quotes ("Reply YES to approve or NO to decline").
_APPROVE_KEYWORDS = frozenset({"yes", "y", "approve", "approved"})
_DECLINE_KEYWORDS = frozenset({"no", "n", "decline", "declined"})


def _reply_twiml(message: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f"<Response><Message>{escape(message)}</Message></Response>"
    )

# Terminal statuses — inbound SMS should prefer an open job over stale SmsLog routing.
_REPAIR_TERMINAL = frozenset({"collected", "no_go", "cancelled"})
_SHOE_TERMINAL = frozenset({"collected", "no_go"})
_AUTO_KEY_TERMINAL = frozenset({
    "booking_completed",
    "work_completed",
    "invoice_paid",
    "failed_job",
    "cancelled",
})


@dataclass
class _InboundTarget:
    tenant_id: UUID
    repair_job_id: UUID | None = None
    shoe_repair_job_id: UUID | None = None
    auto_key_job_id: UUID | None = None
    customer_id: UUID | None = None
    entity_type: str = "customer"

    @property
    def entity_id(self) -> UUID | None:
        return (
            self.repair_job_id
            or self.shoe_repair_job_id
            or self.auto_key_job_id
            or self.customer_id
        )

    @property
    def has_job(self) -> bool:
        return bool(self.repair_job_id or self.shoe_repair_job_id or self.auto_key_job_id)


def _find_customers_by_phone(session: Session, from_phone: str) -> list[Customer]:
    rows = session.exec(
        select(Customer).where(Customer.phone.isnot(None)).where(Customer.phone != "")
    ).all()
    return [row for row in rows if _phones_match(row.phone, from_phone)]


def _collect_open_jobs_for_customer(
    session: Session,
    customer: Customer,
) -> list[tuple[datetime, _InboundTarget]]:
    matches: list[tuple[datetime, _InboundTarget]] = []

    watches = session.exec(
        select(Watch)
        .where(Watch.customer_id == customer.id)
        .where(Watch.tenant_id == customer.tenant_id)
    ).all()
    for watch in watches:
        repair_jobs = session.exec(
            select(RepairJob)
            .where(RepairJob.watch_id == watch.id)
            .where(RepairJob.tenant_id == customer.tenant_id)
        ).all()
        for job in repair_jobs:
            if job.status in _REPAIR_TERMINAL:
                continue
            matches.append((
                job.created_at,
                _InboundTarget(
                    tenant_id=customer.tenant_id,
                    repair_job_id=job.id,
                    entity_type="repair_job",
                ),
            ))

    shoes = session.exec(
        select(Shoe)
        .where(Shoe.customer_id == customer.id)
        .where(Shoe.tenant_id == customer.tenant_id)
    ).all()
    for shoe in shoes:
        shoe_jobs = session.exec(
            select(ShoeRepairJob)
            .where(ShoeRepairJob.shoe_id == shoe.id)
            .where(ShoeRepairJob.tenant_id == customer.tenant_id)
        ).all()
        for job in shoe_jobs:
            if job.status in _SHOE_TERMINAL:
                continue
            matches.append((
                job.created_at,
                _InboundTarget(
                    tenant_id=customer.tenant_id,
                    shoe_repair_job_id=job.id,
                    entity_type="shoe_repair_job",
                ),
            ))

    auto_key_jobs = session.exec(
        select(AutoKeyJob)
        .where(AutoKeyJob.customer_id == customer.id)
        .where(AutoKeyJob.tenant_id == customer.tenant_id)
    ).all()
    for job in auto_key_jobs:
        if job.status in _AUTO_KEY_TERMINAL:
            continue
        matches.append((
            job.created_at,
            _InboundTarget(
                tenant_id=customer.tenant_id,
                auto_key_job_id=job.id,
                entity_type="auto_key_job",
            ),
        ))

    return matches


def _find_open_job_target(session: Session, from_phone: str) -> _InboundTarget | None:
    customers = _find_customers_by_phone(session, from_phone)
    if not customers:
        return None

    candidates: list[tuple[datetime, _InboundTarget]] = []
    for customer in customers:
        candidates.extend(_collect_open_jobs_for_customer(session, customer))

    if not candidates:
        return None

    candidates.sort(key=lambda pair: pair[0], reverse=True)
    return candidates[0][1]


def _target_from_sms_log(row: SmsLog) -> _InboundTarget:
    if row.repair_job_id:
        entity_type = "repair_job"
    elif row.shoe_repair_job_id:
        entity_type = "shoe_repair_job"
    elif row.auto_key_job_id:
        entity_type = "auto_key_job"
    else:
        entity_type = "customer"
    return _InboundTarget(
        tenant_id=row.tenant_id,
        repair_job_id=row.repair_job_id,
        shoe_repair_job_id=row.shoe_repair_job_id,
        auto_key_job_id=row.auto_key_job_id,
        entity_type=entity_type,
    )


def _find_sms_log_fallback(session: Session, from_phone: str) -> SmsLog | None:
    row = session.exec(
        select(SmsLog)
        .where(SmsLog.to_phone == from_phone)
        .where(SmsLog.status == "sent")
        .order_by(SmsLog.created_at.desc())
    ).first()
    if row:
        return row

    recent = session.exec(
        select(SmsLog)
        .where(SmsLog.status == "sent")
        .order_by(SmsLog.created_at.desc())
        .limit(200)
    ).all()
    for log in recent:
        if _phones_match(log.to_phone, from_phone):
            return log
    return None


def _resolve_inbound_target(session: Session, from_phone: str) -> _InboundTarget | None:
    open_job = _find_open_job_target(session, from_phone)
    if open_job:
        return open_job

    sms_log = _find_sms_log_fallback(session, from_phone)
    if sms_log:
        return _target_from_sms_log(sms_log)

    customers = _find_customers_by_phone(session, from_phone)
    if customers:
        # Known customer but no open job and no prior outbound SMS — still surface in inbox.
        customer = customers[0]
        return _InboundTarget(
            tenant_id=customer.tenant_id,
            customer_id=customer.id,
            entity_type="customer",
        )

    return None


@dataclass
class _QuoteDecisionResult:
    reply: str
    decision: str
    quote_id: UUID
    job: RepairJob | None


def _apply_keyword_quote_decision(
    session: Session,
    target: _InboundTarget,
    body_text: str,
) -> _QuoteDecisionResult | None:
    """Honour YES/NO replies to a watch repair quote SMS.

    Returns the decision outcome (with a confirmation message to text back), or
    None when the reply is not a quote decision or there is no pending quote on
    the matched job.
    """
    if not target.repair_job_id:
        return None
    keyword = "".join(ch for ch in body_text.lower() if ch.isalnum())
    if keyword in _APPROVE_KEYWORDS:
        decision = "approved"
    elif keyword in _DECLINE_KEYWORDS:
        decision = "declined"
    else:
        return None

    # "expired" only means the link timed out — an explicit SMS reply still counts.
    quote = session.exec(
        select(Quote)
        .where(Quote.repair_job_id == target.repair_job_id)
        .where(Quote.tenant_id == target.tenant_id)
        .where(Quote.status.in_(("sent", "expired")))
        .order_by(Quote.sent_at.desc())
    ).first()
    if not quote:
        return None

    quote.status = decision
    session.add(quote)
    session.add(Approval(
        tenant_id=quote.tenant_id,
        quote_id=quote.id,
        decision=decision,
        user_agent="sms-reply",
    ))

    job = session.get(RepairJob, target.repair_job_id)
    if job and job.status == "awaiting_go_ahead":
        job.status = "go_ahead" if decision == "approved" else "no_go"
        session.add(job)
        session.add(JobStatusHistory(
            tenant_id=job.tenant_id,
            repair_job_id=job.id,
            old_status="awaiting_go_ahead",
            new_status=job.status,
            changed_by_user_id=None,
            change_note=f"Customer {decision} quote via SMS reply",
        ))
        session.add(TenantEventLog(
            tenant_id=job.tenant_id,
            actor_user_id=None,
            entity_type="repair_job",
            entity_id=job.id,
            event_type="quote_approved" if decision == "approved" else "quote_declined",
            event_summary=(
                f"Customer approved quote for job #{job.job_number} via SMS"
                if decision == "approved"
                else f"Customer declined quote for job #{job.job_number} via SMS — return watch"
            ),
        ))

    reply = (
        "Thanks! Your quote has been approved and we'll get started on your repair."
        if decision == "approved"
        else "No problem — we've recorded that you declined the quote. We'll be in touch about returning your watch."
    )
    return _QuoteDecisionResult(reply=reply, decision=decision, quote_id=quote.id, job=job)


@router.post("/webhook/sms/incoming", include_in_schema=False)
def twilio_incoming_sms(
    From: str = Form(...),
    Body: str = Form(...),
    session: Session = Depends(get_session),
):
    """
    Twilio webhook — configure your Twilio number's inbound webhook URL here.
    Saves the reply to the job's message thread and the inbox. Replies with a
    confirmation when the text is a YES/NO quote decision; otherwise returns
    empty TwiML so Twilio doesn't auto-reply.

    Routing order:
    1. Customer phone match → most recent open job (watch / shoe / auto key).
    2. Fallback → most recent sent SmsLog to that phone (exact or normalized).
    3. If customer exists but no job/SmsLog match → message is still saved
       (surfaced via phone-matched threads) plus an inbox alert.
    4. Unknown sender → no-op (no tenant context).
    """
    from_phone = From.strip()
    body_text = Body.strip()

    target = _resolve_inbound_target(session, from_phone)
    if not target:
        logger.info("sms_webhook.inbound unmatched from=%s", _mask_phone(from_phone))
        return Response(content=_EMPTY_TWIML, media_type="text/xml")

    logger.info(
        "sms_webhook.inbound matched from=%s tenant=%s entity=%s entity_id=%s",
        _mask_phone(from_phone),
        target.tenant_id,
        target.entity_type,
        target.entity_id,
    )

    # Always persist the message so it shows in phone-matched ticket threads,
    # even when no open job could be resolved.
    session.add(JobMessage(
        tenant_id=target.tenant_id,
        repair_job_id=target.repair_job_id,
        shoe_repair_job_id=target.shoe_repair_job_id,
        auto_key_job_id=target.auto_key_job_id,
        direction="inbound",
        body=body_text,
        from_phone=from_phone,
    ))

    decision_result = _apply_keyword_quote_decision(session, target, body_text)

    session.add(TenantEventLog(
        tenant_id=target.tenant_id,
        entity_type=target.entity_type,
        entity_id=target.entity_id,
        event_type="customer_sms_reply",
        event_summary=f"{from_phone}: {body_text[:200]}",
    ))
    session.commit()

    if decision_result and decision_result.decision == "approved" and decision_result.job:
        from ..services.tenant_webhooks import dispatch_tenant_webhooks
        dispatch_tenant_webhooks(
            session,
            tenant_id=decision_result.job.tenant_id,
            event_type="quote_approved",
            payload={
                "job_id": str(decision_result.job.id),
                "job_number": decision_result.job.job_number,
                "quote_id": str(decision_result.quote_id),
                "type": "repair_job",
            },
        )

    if decision_result:
        return Response(content=_reply_twiml(decision_result.reply), media_type="text/xml")
    return Response(content=_EMPTY_TWIML, media_type="text/xml")
