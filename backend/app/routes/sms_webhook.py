import re
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Form
from fastapi.responses import Response
from sqlmodel import Session, select

from ..database import get_session
from ..models import (
    AutoKeyJob,
    Customer,
    JobMessage,
    RepairJob,
    Shoe,
    ShoeRepairJob,
    SmsLog,
    TenantEventLog,
    Watch,
)

router = APIRouter(prefix="/v1", tags=["sms-webhook"])

_EMPTY_TWIML = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'

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


def _normalize_phone(raw: str) -> str | None:
    if not raw or not raw.strip():
        return None
    digits = re.sub(r"\D", "", raw.strip())
    if not digits:
        return None
    # AU international → local (e.g. +61412345678 → 0412345678)
    if digits.startswith("61") and len(digits) >= 11:
        digits = "0" + digits[2:11]
    if len(digits) == 9 and digits[0] in ("4", "3"):
        digits = "0" + digits
    if len(digits) > 10:
        digits = digits[-10:]
    if len(digits) < 8:
        return None
    return digits


def _phones_match(a: str | None, b: str | None) -> bool:
    left = _normalize_phone(a or "")
    right = _normalize_phone(b or "")
    return bool(left and right and left == right)


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


@router.post("/webhook/sms/incoming", include_in_schema=False)
def twilio_incoming_sms(
    From: str = Form(...),
    Body: str = Form(...),
    session: Session = Depends(get_session),
):
    """
    Twilio webhook — configure your Twilio number's inbound webhook URL here.
    Saves the reply to the job's message thread and the inbox, then returns
    empty TwiML so Twilio doesn't auto-reply.

    Routing order:
    1. Customer phone match → most recent open job (watch / shoe / auto key).
    2. Fallback → most recent sent SmsLog to that phone (exact or normalized).
    3. If customer exists but no job/SmsLog match → inbox alert only (no thread).
    4. Unknown sender → no-op (no tenant context).
    """
    from_phone = From.strip()
    body_text = Body.strip()

    target = _resolve_inbound_target(session, from_phone)
    if not target:
        return Response(content=_EMPTY_TWIML, media_type="text/xml")

    if target.has_job:
        session.add(JobMessage(
            tenant_id=target.tenant_id,
            repair_job_id=target.repair_job_id,
            shoe_repair_job_id=target.shoe_repair_job_id,
            auto_key_job_id=target.auto_key_job_id,
            direction="inbound",
            body=body_text,
            from_phone=from_phone,
        ))

    session.add(TenantEventLog(
        tenant_id=target.tenant_id,
        entity_type=target.entity_type,
        entity_id=target.entity_id,
        event_type="customer_sms_reply",
        event_summary=f"{from_phone}: {body_text[:200]}",
    ))
    session.commit()

    return Response(content=_EMPTY_TWIML, media_type="text/xml")
