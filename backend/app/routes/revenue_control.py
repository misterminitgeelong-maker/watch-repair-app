"""Tenant-scoped revenue exceptions and internally scheduled follow-ups.

No messages are sent by these routes. Resolution is derived from source records,
so recording contact or scheduling a follow-up cannot hide unpaid revenue.
"""
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select, update

from ..auto_key_status import canonical_auto_key_status, AUTO_KEY_CANONICAL_FINAL_STATUSES
from ..config import settings
from ..database import get_session
from ..datetime_utils import as_utc_for_json, naive_utc_from_any
from ..dependencies import AuthContext, require_feature, require_tech_or_above
from ..models import AutoKeyJob, AutoKeyQuote, AutoKeyInvoice, Customer, User, TenantEventLog, RevenueFollowUp

router = APIRouter(prefix="/v1/revenue-control", tags=["revenue-control"],
                   dependencies=[Depends(require_feature("auto_key"))])
Kind = Literal["quote_draft", "quote_followup", "booking_confirmation", "unscheduled", "unassigned", "blocked", "uninvoiced", "unpaid"]


class RevenueItem(BaseModel):
    key: str
    kind: Kind
    job_id: UUID
    job_number: str
    title: str
    customer_name: str
    owner_user_id: UUID | None
    owner_name: str | None
    amount_cents: int | None
    currency: str
    deposit_cents: int
    age_days: int
    due_at: datetime
    due: bool
    priority: Literal["high", "normal"]
    next_action: str
    note: str = ""
    last_contact_at: datetime | None = None
    version: int = 0


class RevenueBucket(BaseModel):
    kind: Kind
    count: int = 0
    due_count: int = 0
    amount_cents: int = 0
    unknown_amount_count: int = 0


class RevenueOwner(BaseModel):
    id: UUID
    name: str


class RevenueResponse(BaseModel):
    items: list[RevenueItem]
    total: int
    limit: int
    offset: int
    buckets: list[RevenueBucket]
    owners: list[RevenueOwner]
    generated_at: datetime
    timezone: str
    warnings: list[str]


class FollowUpUpdate(BaseModel):
    expected_version: int = Field(ge=0)
    owner_user_id: UUID | None = None
    next_follow_up_at: datetime | None = None
    note: str = Field(default="", max_length=2000)
    contacted: bool = False


ACTIONS = {
    "quote_draft": "Prepare and send quote",
    "quote_followup": "Follow up on quote decision",
    "booking_confirmation": "Confirm booking with customer",
    "unscheduled": "Schedule the job",
    "unassigned": "Assign a technician",
    "blocked": "Resolve the booking hold",
    "uninvoiced": "Review completed work and raise invoice",
    "unpaid": "Review payment and follow up with customer",
}


def _items(session: Session, tenant_id: UUID, now: datetime) -> tuple[list[RevenueItem], list[RevenueOwner], list[str]]:
    # Fixed number of tenant-scoped queries, independent of job count.
    jobs = session.exec(select(AutoKeyJob).where(AutoKeyJob.tenant_id == tenant_id)).all()
    quotes = session.exec(select(AutoKeyQuote).where(AutoKeyQuote.tenant_id == tenant_id)
                          .order_by(AutoKeyQuote.created_at, AutoKeyQuote.id)).all()
    invoices = session.exec(select(AutoKeyInvoice).where(AutoKeyInvoice.tenant_id == tenant_id)).all()
    customers = {c.id: c.full_name for c in session.exec(select(Customer).where(Customer.tenant_id == tenant_id)).all()}
    users = {u.id: u for u in session.exec(select(User).where(User.tenant_id == tenant_id)).all()}
    followups = {f.issue_key: f for f in session.exec(select(RevenueFollowUp).where(RevenueFollowUp.tenant_id == tenant_id)).all()}
    latest_quotes = {q.auto_key_job_id: q for q in quotes}
    invoices_by_job: dict[UUID, list[AutoKeyInvoice]] = {}
    for invoice in invoices:
        invoices_by_job.setdefault(invoice.auto_key_job_id, []).append(invoice)
    tz = ZoneInfo(settings.schedule_calendar_timezone)
    items: list[RevenueItem] = []
    warnings = ["Invoice amounts are unpaid invoice face values, not reconciled balances. Deposits are shown separately; reconcile them before requesting payment.",
                "Invoice age is measured from issue date. Payment terms and due dates are not recorded, so aged invoices are not labelled overdue.",
                "Category values can refer to the same job. Do not add quote, scheduling and invoice amounts together."]

    def add(job, kind, source, started, amount, currency="AUD", delay_days=0):
        key = f"{kind}:{source}"
        followup = followups.get(key)
        owner = followup.owner_user_id if followup else job.assigned_user_id
        started = as_utc_for_json(started)
        due_at = as_utc_for_json(followup.next_follow_up_at) if followup and followup.next_follow_up_at else started + timedelta(days=delay_days)
        age = max(0, (now.astimezone(tz).date() - started.astimezone(tz).date()).days)
        items.append(RevenueItem(
            key=key, kind=kind, job_id=job.id, job_number=job.job_number, title=job.title,
            customer_name=customers.get(job.customer_id, "Customer unavailable"), owner_user_id=owner,
            owner_name=users[owner].full_name if owner in users else None,
            amount_cents=amount if currency == "AUD" else None, currency=currency,
            deposit_cents=max(0, job.deposit_cents), age_days=age, due_at=due_at, due=due_at <= now,
            priority="high" if kind == "uninvoiced" or (kind == "unpaid" and age >= 7) or job.priority == "urgent" else "normal",
            next_action=ACTIONS[kind], note=followup.note if followup else "",
            last_contact_at=as_utc_for_json(followup.last_contact_at) if followup else None,
            version=followup.version if followup else 0,
        ))

    for job in jobs:
        status = canonical_auto_key_status(job.status)
        quote = latest_quotes.get(job.id)
        job_invoices = invoices_by_job.get(job.id, [])
        amount = quote.total_cents if quote and quote.status != "rejected" else None
        currency = quote.currency if quote else "AUD"
        for invoice in job_invoices:
            if invoice.status == "unpaid" and invoice.total_cents > 0:
                add(job, "unpaid", invoice.id, invoice.created_at, invoice.total_cents, invoice.currency)
        if status in {"work_completed", "booking_completed", "invoice_paid"}:
            if not job_invoices:
                add(job, "uninvoiced", job.id, job.work_completed_at or job.updated_at, amount, currency)
            continue
        if status in AUTO_KEY_CANONICAL_FINAL_STATUSES:
            continue
        if status == "awaiting_quote":
            add(job, "quote_draft", quote.id if quote else job.id, quote.created_at if quote else job.created_at, amount, currency)
        elif status == "quote_sent" and quote and quote.status == "sent":
            add(job, "quote_followup", quote.id, quote.sent_at or quote.created_at, amount, currency, max(1, settings.quote_reminder_days))
        elif status == "awaiting_booking_confirmation":
            add(job, "booking_confirmation", job.id, job.updated_at, amount, currency)
        elif status == "booking_on_hold":
            add(job, "blocked", job.id, job.updated_at, amount, currency)
        if status in {"booking_confirmed", "booked", "en_route", "on_site"}:
            if not job.scheduled_at:
                add(job, "unscheduled", job.id, job.updated_at, amount, currency)
            if not job.assigned_user_id:
                add(job, "unassigned", job.id, job.updated_at, amount, currency)
    if any(i.currency != "AUD" for i in items):
        warnings.append("Non-AUD amounts are excluded from AUD category totals; review the original document.")
    items.sort(key=lambda i: (not i.due, i.priority != "high", i.due_at, -(i.amount_cents or 0), i.key))
    owners = sorted([RevenueOwner(id=u.id, name=u.full_name) for u in users.values()
                     if u.is_active and u.role in {"owner", "manager", "tech", "platform_admin"}], key=lambda u: u.name)
    return items, owners, warnings


@router.get("", response_model=RevenueResponse)
def get_revenue_control(
    kind: Kind | None = None, state: Literal["due", "scheduled", "all"] = "due",
    owner: str | None = None, search: str = Query(default="", max_length=200),
    limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0),
    auth: AuthContext = Depends(require_tech_or_above), session: Session = Depends(get_session),
):
    now = datetime.now(timezone.utc)
    items, owners, warnings = _items(session, auth.tenant_id, now)
    # Summary honours owner/search, but remains stable when switching category or due view.
    if owner:
        if owner == "unassigned":
            items = [i for i in items if not i.owner_user_id]
        else:
            try:
                owner_id = auth.user_id if owner == "me" else UUID(owner)
            except ValueError:
                raise HTTPException(422, "Invalid owner")
            items = [i for i in items if i.owner_user_id == owner_id]
    if search.strip():
        term = search.strip().casefold()
        items = [i for i in items if term in f"{i.job_number} {i.title} {i.customer_name}".casefold()]
    buckets = [RevenueBucket(kind=k, count=sum(i.kind == k for i in items),
                             due_count=sum(i.kind == k and i.due for i in items),
                             amount_cents=sum(i.amount_cents or 0 for i in items if i.kind == k),
                             unknown_amount_count=sum(i.amount_cents is None for i in items if i.kind == k)) for k in ACTIONS]
    filtered = [i for i in items if (not kind or i.kind == kind) and
                (state == "all" or (i.due if state == "due" else not i.due))]
    return RevenueResponse(items=filtered[offset:offset + limit], total=len(filtered), limit=limit, offset=offset,
                           buckets=buckets, owners=owners, generated_at=now,
                           timezone=settings.schedule_calendar_timezone, warnings=warnings)


@router.put("/{issue_key}/follow-up", response_model=RevenueItem)
def save_follow_up(issue_key: str, body: FollowUpUpdate,
                   auth: AuthContext = Depends(require_tech_or_above), session: Session = Depends(get_session)):
    now = datetime.now(timezone.utc)
    items, owners, _ = _items(session, auth.tenant_id, now)
    item = next((i for i in items if i.key == issue_key), None)
    if not item:
        raise HTTPException(404, "This item has resolved or is unavailable. Refresh the queue.")
    if body.owner_user_id and body.owner_user_id not in {o.id for o in owners}:
        raise HTTPException(422, "Choose an active team member from this shop")
    due_at = as_utc_for_json(body.next_follow_up_at)
    if due_at and (due_at <= now or due_at > now + timedelta(days=90)):
        raise HTTPException(422, "Choose a follow-up time in the next 90 days")
    values = dict(owner_user_id=body.owner_user_id, next_follow_up_at=naive_utc_from_any(due_at),
                  note=body.note.strip(), last_contact_at=naive_utc_from_any(now if body.contacted else item.last_contact_at),
                  version=body.expected_version + 1)
    try:
        if body.expected_version == 0:
            session.add(RevenueFollowUp(tenant_id=auth.tenant_id, issue_key=issue_key, auto_key_job_id=item.job_id, **values))
            session.flush()
        else:
            result = session.exec(update(RevenueFollowUp).where(RevenueFollowUp.tenant_id == auth.tenant_id,
                                  RevenueFollowUp.issue_key == issue_key, RevenueFollowUp.version == body.expected_version).values(**values))
            if result.rowcount != 1:
                raise HTTPException(409, "Another team member updated this item. Refresh before saving.")
        session.add(TenantEventLog(tenant_id=auth.tenant_id, actor_user_id=auth.user_id,
                    entity_type="auto_key_job", entity_id=item.job_id, event_type="revenue_follow_up",
                    event_summary=f"{item.kind}: {'contact recorded' if body.contacted else 'follow-up updated'}; "
                    f"owner={body.owner_user_id or 'unassigned'}; next={due_at.isoformat() if due_at else 'due now'}; {body.note.strip()}"))
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "Another team member updated this item. Refresh before saving.")
    updated, _, _ = _items(session, auth.tenant_id, now)
    return next(i for i in updated if i.key == issue_key)
