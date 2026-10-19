import hashlib
import hmac
import logging
from base64 import b64encode
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from ..config import settings
from ..database import get_session
from ..models import (
    Approval,
    AutoKeyJob,
    Customer,
    InboundSmsReceipt,
    JobMessage,
    JobStatusHistory,
    Quote,
    RepairJob,
    Shoe,
    ShoeJobStatusHistory,
    ShoeRepairJob,
    SmsLog,
    TenantEventLog,
    Watch,
)
from ..sms_controls import classify_keyword, is_suppressed, set_suppression
from ..phone_utils import (
    normalize_phone as _normalize_phone,
    phone_lookup_variants as _phone_lookup_variants,
)

router = APIRouter(prefix="/v1", tags=["sms-webhook"])

logger = logging.getLogger(__name__)


def _twilio_webhook_url(request: Request) -> str:
    """URL Twilio signed against — prefer public_base_url behind reverse proxies."""
    base = (settings.public_base_url or "").rstrip("/")
    if base:
        return f"{base}/v1/webhook/sms/incoming"
    return str(request.url)


def _twilio_signature_valid(auth_token: str, url: str, params: dict[str, str], signature: str) -> bool:
    """Validate X-Twilio-Signature (HMAC-SHA1) without requiring the twilio package."""
    payload = url + "".join(key + params[key] for key in sorted(params))
    digest = hmac.new(auth_token.encode("utf-8"), payload.encode("utf-8"), hashlib.sha1).digest()
    expected = b64encode(digest).decode("utf-8")
    return hmac.compare_digest(expected, signature or "")


def _validate_twilio_signature(request: Request, form_params: dict[str, str]) -> None:
    """Reject spoofed webhooks when Twilio auth token is configured. Skip in dry-run/test."""
    token = (settings.twilio_auth_token or "").strip()
    if not token:
        if settings.app_env == "production":
            # Without the token nothing can be verified, and an unsigned post
            # can put words in a customer's mouth (including "YES" to a quote).
            raise HTTPException(status_code=403, detail="SMS webhook is not configured")
        return
    # Pytest / unsigned local posts — signature checks run in staging/production.
    if settings.app_env == "test":
        return
    signature = request.headers.get("X-Twilio-Signature", "")
    url = _twilio_webhook_url(request)
    if not _twilio_signature_valid(token, url, form_params, signature):
        logger.warning("sms_webhook.signature invalid url=%s", url)
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")


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
    normalized = _normalize_phone(from_phone)
    if not normalized:
        return []
    return list(
        session.exec(select(Customer).where(Customer.phone_normalized == normalized)).all()
    )


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


def _find_open_job_target(
    session: Session,
    from_phone: str,
    *,
    tenant_id: UUID | None = None,
) -> _InboundTarget | None:
    customers = _find_customers_by_phone(session, from_phone)
    if tenant_id is not None:
        customers = [c for c in customers if c.tenant_id == tenant_id]
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


def _find_sms_log_fallback(session: Session, from_phone: str) -> list[SmsLog]:
    """Recent outbound texts to this phone, newest first — no full-table scan."""
    variants = _phone_lookup_variants(from_phone)
    if not variants:
        return []
    return list(
        session.exec(
            select(SmsLog)
            .where(col(SmsLog.to_phone).in_(variants))
            .where(SmsLog.status == "sent")
            .order_by(SmsLog.created_at.desc())
            .limit(50)
        ).all()
    )


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _resolve_inbound_target(session: Session, from_phone: str) -> tuple[_InboundTarget | None, bool]:
    """Work out which shop (and job) an inbound text belongs to.

    Returns (target, ambiguous). When the phone is known to more than one shop we
    never guess: the shop whose outbound SmsLog to this phone is most recent (within
    sms_attribution_window_days) wins; with no such recent text the result is
    (None, True) and the caller must not act on the message.
    """
    logs = _find_sms_log_fallback(session, from_phone)
    customers = _find_customers_by_phone(session, from_phone)

    tenant_ids = {row.tenant_id for row in logs} | {c.tenant_id for c in customers}
    if len(tenant_ids) > 1:
        cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, settings.sms_attribution_window_days))
        recent = [row for row in logs if _aware(row.created_at) >= cutoff]
        if not recent:
            logger.warning(
                "sms_webhook.inbound ambiguous sender %s across %d tenants and no recent outbound; not acting",
                _mask_phone(from_phone),
                len(tenant_ids),
            )
            return None, True
        preferred = recent[0].tenant_id
        if len({row.tenant_id for row in recent}) > 1:
            logger.warning(
                "sms_webhook.inbound multiple tenants texted %s recently; using most recent tenant=%s",
                _mask_phone(from_phone),
                preferred,
            )
        logs = [row for row in logs if row.tenant_id == preferred]
        customers = [c for c in customers if c.tenant_id == preferred]

    if logs:
        open_job = _find_open_job_target(session, from_phone, tenant_id=logs[0].tenant_id)
        return (open_job or _target_from_sms_log(logs[0])), False

    if customers:
        tenant_id = customers[0].tenant_id
        open_job = _find_open_job_target(session, from_phone, tenant_id=tenant_id)
        if open_job:
            return open_job, False
        # Known customer but no open job and no prior outbound SMS — still surface in inbox.
        customer = customers[0]
        return (
            _InboundTarget(
                tenant_id=customer.tenant_id,
                customer_id=customer.id,
                entity_type="customer",
            ),
            False,
        )

    return None, False


@dataclass
class _QuoteDecisionResult:
    reply: str
    decision: str
    quote_id: UUID | None
    job: RepairJob | ShoeRepairJob | None


def _apply_keyword_quote_decision(
    session: Session,
    target: _InboundTarget,
    body_text: str,
) -> _QuoteDecisionResult | None:
    """Honour YES/NO replies to a watch or shoe repair quote SMS."""
    keyword = "".join(ch for ch in body_text.lower() if ch.isalnum())
    if keyword in _APPROVE_KEYWORDS:
        decision = "approved"
    elif keyword in _DECLINE_KEYWORDS:
        decision = "declined"
    else:
        return None

    if target.repair_job_id:
        quote = session.exec(
            select(Quote)
            .where(Quote.repair_job_id == target.repair_job_id)
            .where(Quote.tenant_id == target.tenant_id)
            .where(Quote.status == "sent")
            .order_by(Quote.sent_at.desc())
        ).first()
        if not quote:
            return None
        from .quotes import _quote_token_is_expired, apply_customer_quote_decision

        if _quote_token_is_expired(quote):
            # The online link refuses an expired quote; a YES by text shouldn't
            # get around that.
            return _QuoteDecisionResult(
                reply="Sorry, that quote has expired. We'll send you an updated one.",
                decision="expired",
                quote_id=quote.id,
                job=None,
            )

        quote.status = decision
        session.add(quote)
        session.add(Approval(
            tenant_id=quote.tenant_id,
            quote_id=quote.id,
            decision=decision,
            user_agent="sms-reply",
        ))

        job = session.get(RepairJob, target.repair_job_id)
        if job:
            apply_customer_quote_decision(session, job, decision, via="SMS reply")

        reply = (
            "Thanks! Your quote has been approved and we'll get started on your repair."
            if decision == "approved"
            else "No problem — we've recorded that you declined the quote. We'll be in touch about returning your watch."
        )
        return _QuoteDecisionResult(reply=reply, decision=decision, quote_id=quote.id, job=job)

    if target.shoe_repair_job_id:
        job = session.get(ShoeRepairJob, target.shoe_repair_job_id)
        if not job or job.tenant_id != target.tenant_id:
            return None
        if job.quote_status not in ("sent",):
            return None

        job.quote_status = decision
        if job.status == "awaiting_go_ahead":
            job.status = "go_ahead" if decision == "approved" else "no_go"
        session.add(job)
        session.add(ShoeJobStatusHistory(
            tenant_id=job.tenant_id,
            shoe_repair_job_id=job.id,
            old_status="awaiting_go_ahead",
            new_status=job.status,
            changed_by_user_id=None,
            change_note=f"Customer {decision} quote via SMS reply",
        ))
        session.add(TenantEventLog(
            tenant_id=job.tenant_id,
            actor_user_id=None,
            entity_type="shoe_repair_job",
            entity_id=job.id,
            event_type="quote_approved" if decision == "approved" else "quote_declined",
            event_summary=(
                f"Customer approved shoe repair quote for job #{job.job_number} via SMS"
                if decision == "approved"
                else f"Customer declined shoe repair quote for job #{job.job_number} via SMS"
            ),
        ))
        reply = (
            "Thanks! Your quote has been approved and we'll get started on your repair."
            if decision == "approved"
            else "No problem — we've recorded that you declined the quote. We'll be in touch about returning your shoes."
        )
        return _QuoteDecisionResult(reply=reply, decision=decision, quote_id=None, job=job)

    return None


def _ticket_label(session: Session, target: _InboundTarget) -> str | None:
    """Human ticket number for the matched job, e.g. '#JOB-00042' — inbox context."""
    if target.repair_job_id:
        job = session.get(RepairJob, target.repair_job_id)
        return f"#{job.job_number}" if job else None
    if target.shoe_repair_job_id:
        job = session.get(ShoeRepairJob, target.shoe_repair_job_id)
        return f"#{job.job_number}" if job else None
    if target.auto_key_job_id:
        job = session.get(AutoKeyJob, target.auto_key_job_id)
        return f"#{job.job_number}" if job else None
    return None


def _receipt_exists(session: Session, message_sid: str) -> bool:
    return session.exec(
        select(InboundSmsReceipt.id).where(InboundSmsReceipt.message_sid == message_sid)
    ).first() is not None


def _commit_receipt(session: Session, message_sid: str) -> bool:
    """Commit the work plus its receipt. False when a concurrent replay won the race."""
    try:
        session.commit()
        return True
    except IntegrityError:
        session.rollback()
        if message_sid and _receipt_exists(session, message_sid):
            logger.info("sms_webhook.inbound duplicate sid=%s lost race; ignored", message_sid)
            return False
        raise


@router.post("/webhook/sms/incoming", include_in_schema=False)
async def twilio_incoming_sms(
    request: Request,
    session: Session = Depends(get_session),
):
    """
    Twilio webhook — configure your Twilio number's inbound webhook URL here.
    Saves the reply to the job's message thread and the inbox. Replies with a
    confirmation when the text is a YES/NO quote decision; otherwise returns
    empty TwiML so Twilio doesn't auto-reply.

    When TWILIO_AUTH_TOKEN is set, validates X-Twilio-Signature (required in
    production). Dry-run / test without a token skips signature checks.

    Routing order:
    0. A phone known to several shops is attributed only to the shop whose outbound
       SmsLog to it is most recent within sms_attribution_window_days; with no
       recent outbound nothing is acted on (never guessed).
    1. Tenant whose SmsLog most recently texted this phone — prefer an open job.
    2. Else the (single) tenant's open job for that phone.
    3. Else a known customer with no open job — inbox alert only.
    4. Unknown sender → no-op (no tenant context).

    STOP/STOPALL/UNSUBSCRIBE/CANCEL/END/QUIT suppress the phone for all outbound
    SMS; START/UNSTOP (and YES, only while suppressed) lift it. Each MessageSid is
    processed once.
    """
    form = await request.form()
    form_params = {k: str(v) for k, v in form.items()}
    _validate_twilio_signature(request, form_params)

    from_phone = (form_params.get("From") or "").strip()
    body_text = (form_params.get("Body") or "").strip()
    if not from_phone:
        raise HTTPException(status_code=422, detail="From is required")

    # Each Twilio MessageSid is processed once: a replayed (validly signed) POST is a no-op.
    message_sid = (form_params.get("MessageSid") or form_params.get("SmsSid") or "").strip()[:64]
    if message_sid and _receipt_exists(session, message_sid):
        logger.info("sms_webhook.inbound duplicate sid=%s ignored", message_sid)
        return Response(content=_EMPTY_TWIML, media_type="text/xml")
    if message_sid:
        session.add(InboundSmsReceipt(message_sid=message_sid))

    target, ambiguous = _resolve_inbound_target(session, from_phone)

    # Opt-out / opt-in applies to the phone number itself, not to any one shop.
    keyword = classify_keyword(body_text)
    opt_type = (form_params.get("OptOutType") or "").strip().upper()
    if opt_type == "STOP":
        keyword = "stop"
    elif opt_type == "START":
        keyword = "start"
    is_stop = keyword == "stop"
    opt_note = ""
    if is_stop:
        set_suppression(
            session,
            from_phone,
            active=True,
            keyword="".join(ch for ch in body_text.lower() if ch.isalnum())[:32] or "stop",
            source_tenant_id=target.tenant_id if target else None,
        )
        opt_note = " [opted out of SMS]"
    elif keyword == "start" and is_suppressed(session, from_phone):
        set_suppression(session, from_phone, active=False, keyword="".join(
            ch for ch in body_text.lower() if ch.isalnum())[:32] or "start")
        opt_note = " [opted back in to SMS]"

    if not target:
        if ambiguous:
            logger.warning("sms_webhook.inbound ambiguous from=%s logged only", _mask_phone(from_phone))
        else:
            logger.info("sms_webhook.inbound unmatched from=%s", _mask_phone(from_phone))
        _commit_receipt(session, message_sid)
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

    decision_result = None if is_stop else _apply_keyword_quote_decision(session, target, body_text)

    ticket = _ticket_label(session, target)
    summary_prefix = f"{ticket} · {from_phone}" if ticket else f"{from_phone} (no open ticket)"
    session.add(TenantEventLog(
        tenant_id=target.tenant_id,
        entity_type=target.entity_type,
        entity_id=target.entity_id,
        event_type="customer_sms_reply",
        event_summary=f"{summary_prefix}: {body_text[:200]}{opt_note}",
    ))
    if not _commit_receipt(session, message_sid):
        return Response(content=_EMPTY_TWIML, media_type="text/xml")

    if decision_result and decision_result.decision == "approved" and decision_result.job:
        from ..services.tenant_webhooks import dispatch_tenant_webhooks
        dispatch_tenant_webhooks(
            session,
            tenant_id=decision_result.job.tenant_id,
            event_type="quote_approved",
            payload={
                "job_id": str(decision_result.job.id),
                "job_number": decision_result.job.job_number,
                "quote_id": str(decision_result.quote_id) if decision_result.quote_id else None,
                "type": "repair_job" if isinstance(decision_result.job, RepairJob) else "shoe_repair_job",
            },
        )

    if decision_result:
        return Response(content=_reply_twiml(decision_result.reply), media_type="text/xml")
    return Response(content=_EMPTY_TWIML, media_type="text/xml")
