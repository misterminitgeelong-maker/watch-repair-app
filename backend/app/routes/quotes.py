from datetime import datetime, timezone
from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlmodel import Session, select

from ..database import get_session
from ..dependencies import AuthContext, get_auth_context
from ..config import settings
from ..models import (
    Approval,
    Customer,
    JobStatusHistory,
    Quote,
    QuoteCreate,
    TenantEventLog,
    QuoteDecisionRequest,
    QuoteDecisionResponse,
    QuoteLineItem,
    QuoteRead,
    QuoteSendResponse,
    Tenant,
    Watch,
)
from ..limiter import limiter
from ..tenant_helpers import get_tenant_quote, get_tenant_repair_job
from .. import sms

router = APIRouter(prefix="/v1", tags=["quotes"])


def get_public_quote_rate_limit() -> str:
    return settings.rate_limit_public_quote_get


def get_public_quote_decision_rate_limit() -> str:
    return settings.rate_limit_public_quote_decision


def _quote_token_is_expired(quote: Quote) -> bool:
    expires_at = quote.approval_token_expires_at
    if not expires_at:
        return False
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) > expires_at


@router.get("/quotes", response_model=list[QuoteRead])
def list_quotes(
    repair_job_id: UUID | None = None,
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=20000),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="created_at"),
    sort_dir: str = Query(default="desc"),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    query = select(Quote).where(Quote.tenant_id == auth.tenant_id)
    if repair_job_id:
        query = query.where(Quote.repair_job_id == repair_job_id)
    if status:
        query = query.where(Quote.status == status)

    sort_fields = {
        "created_at": Quote.created_at,
        "sent_at": Quote.sent_at,
        "status": Quote.status,
        "total_cents": Quote.total_cents,
    }
    sort_col = sort_fields.get(sort_by)
    if sort_col is None:
        raise HTTPException(status_code=400, detail="Invalid sort_by")
    if sort_dir.lower() not in {"asc", "desc"}:
        raise HTTPException(status_code=400, detail="Invalid sort_dir")
    query = query.order_by(sort_col.asc() if sort_dir.lower() == "asc" else sort_col.desc())
    query = query.offset(offset).limit(limit)
    return session.exec(query).all()


@router.get("/quotes/{quote_id}/line-items")
def get_quote_line_items(
    quote_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    quote = get_tenant_quote(session, quote_id, auth.tenant_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    items = session.exec(select(QuoteLineItem).where(QuoteLineItem.quote_id == quote_id)).all()
    return items


@router.post("/quotes", response_model=QuoteRead, status_code=201)
def create_quote(
    payload: QuoteCreate,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    tenant = session.get(Tenant, auth.tenant_id)
    tenant_currency = (tenant.default_currency if tenant and tenant.default_currency else "AUD").upper()
    job = get_tenant_repair_job(session, payload.repair_job_id, auth.tenant_id)
    if not job:
        raise HTTPException(status_code=404, detail="Repair job not found")

    subtotal = 0
    expanded_items: list[QuoteLineItem] = []
    for item in payload.line_items:
        line_total = int(round(item.quantity * item.unit_price_cents))
        subtotal += line_total
        expanded_items.append(
            QuoteLineItem(
                tenant_id=auth.tenant_id,
                quote_id=UUID(int=0),  # temporary, replaced after quote flush
                item_type=item.item_type,
                description=item.description,
                quantity=item.quantity,
                unit_price_cents=item.unit_price_cents,
                total_price_cents=line_total,
            )
        )

    quote = Quote(
        tenant_id=auth.tenant_id,
        repair_job_id=payload.repair_job_id,
        subtotal_cents=subtotal,
        discount_cents=payload.discount_cents,
        tax_cents=payload.tax_cents,
        total_cents=max(0, subtotal - payload.discount_cents + payload.tax_cents),
        currency=tenant_currency,
    )
    session.add(quote)
    session.flush()

    for item in expanded_items:
        item.quote_id = quote.id
        session.add(item)

    session.commit()
    session.refresh(quote)
    return quote


@router.post("/quotes/{quote_id}/send", response_model=QuoteSendResponse)
def send_quote(
    quote_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    quote = get_tenant_quote(session, quote_id, auth.tenant_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    now = datetime.now(timezone.utc)
    quote.status = "sent"
    quote.sent_at = now
    quote.approval_token_expires_at = now + timedelta(hours=max(settings.quote_approval_token_ttl_hours, 1))
    session.add(quote)

    job = get_tenant_repair_job(session, quote.repair_job_id, auth.tenant_id)
    if job and job.status not in ("go_ahead", "no_go", "completed", "awaiting_collection", "collected"):
        prev = job.status
        job.status = "awaiting_go_ahead"
        session.add(job)
        session.add(
            JobStatusHistory(
                tenant_id=job.tenant_id,
                repair_job_id=job.id,
                old_status=prev,
                new_status="awaiting_go_ahead",
                changed_by_user_id=auth.user_id,
                change_note="Quote sent — awaiting customer approval",
            )
        )

    # Send SMS to customer if they have a phone number
    if job:
        watch = session.get(Watch, job.watch_id)
        if watch:
            customer = session.get(Customer, watch.customer_id)
            if customer and customer.phone:
                line_items_db = session.exec(
                    select(QuoteLineItem).where(QuoteLineItem.quote_id == quote.id)
                ).all()
                line_items_data = [
                    {
                        "description": li.description,
                        "quantity": li.quantity,
                        "unit_price_cents": li.unit_price_cents,
                        "total_price_cents": li.total_price_cents,
                    }
                    for li in line_items_db
                ]
                sms.notify_quote_sent(
                    session,
                    tenant_id=auth.tenant_id,
                    repair_job_id=job.id,
                    customer_name=customer.full_name,
                    to_phone=customer.phone,
                    total_cents=quote.total_cents,
                    approval_token=quote.approval_token,
                    line_items=line_items_data,
                )
            if customer and customer.email:
                from ..email_client import send_quote_sent_email
                tenant = session.get(Tenant, auth.tenant_id)
                shop_name = (tenant.name if tenant else None) or "Your repair shop"
                send_quote_sent_email(
                    to_email=customer.email,
                    customer_name=customer.full_name,
                    total_cents=quote.total_cents,
                    approval_token=quote.approval_token,
                    job_number=job.job_number,
                    shop_name=shop_name,
                )

    session.commit()
    session.refresh(quote)

    return QuoteSendResponse(
        id=quote.id,
        status=quote.status,
        sent_at=quote.sent_at,
        approval_token=quote.approval_token,
    )


@router.post("/quotes/{quote_id}/resend", response_model=QuoteSendResponse)
def resend_quote(
    quote_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    quote = get_tenant_quote(session, quote_id, auth.tenant_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    if quote.status not in ("sent", "expired"):
        raise HTTPException(status_code=400, detail="Only sent or expired quotes can be resent")

    now = datetime.now(timezone.utc)
    quote.status = "sent"
    quote.sent_at = now
    quote.approval_token_expires_at = now + timedelta(hours=max(settings.quote_approval_token_ttl_hours, 1))
    session.add(quote)

    job = get_tenant_repair_job(session, quote.repair_job_id, auth.tenant_id)
    if job:
        watch = session.get(Watch, job.watch_id)
        if watch:
            customer = session.get(Customer, watch.customer_id)
            if customer and customer.phone:
                line_items_db = session.exec(
                    select(QuoteLineItem).where(QuoteLineItem.quote_id == quote.id)
                ).all()
                line_items_data = [
                    {
                        "description": li.description,
                        "quantity": li.quantity,
                        "unit_price_cents": li.unit_price_cents,
                        "total_price_cents": li.total_price_cents,
                    }
                    for li in line_items_db
                ]
                sms.notify_quote_sent(
                    session,
                    tenant_id=auth.tenant_id,
                    repair_job_id=job.id,
                    customer_name=customer.full_name,
                    to_phone=customer.phone,
                    total_cents=quote.total_cents,
                    approval_token=quote.approval_token,
                    line_items=line_items_data,
                )

    session.commit()
    session.refresh(quote)

    return QuoteSendResponse(
        id=quote.id,
        status=quote.status,
        sent_at=quote.sent_at,
        approval_token=quote.approval_token,
    )


@router.post("/public/quotes/{token}/decision", response_model=QuoteDecisionResponse)
@limiter.limit(get_public_quote_decision_rate_limit)
def quote_decision(
    request: Request,
    token: str,
    payload: QuoteDecisionRequest,
    session: Session = Depends(get_session),
):
    quote = session.exec(select(Quote).where(Quote.approval_token == token)).first()
    if not quote:
        raise HTTPException(status_code=404, detail="Invalid token")
    if _quote_token_is_expired(quote):
        if quote.status not in {"approved", "declined"}:
            quote.status = "expired"
            session.add(quote)
            session.commit()
        raise HTTPException(status_code=410, detail="Quote approval link has expired")

    if quote.status in {"approved", "declined"}:
        raise HTTPException(status_code=409, detail="Decision already recorded")

    new_status = "approved" if payload.decision == "approved" else "declined"
    quote.status = new_status
    session.add(quote)

    approval = Approval(
        tenant_id=quote.tenant_id,
        quote_id=quote.id,
        decision=payload.decision,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        customer_signature_data_url=payload.signature_data_url if payload.decision == "approved" else None,
    )
    session.add(approval)

    # Update job status and log event for staff bump
    job = get_tenant_repair_job(session, quote.repair_job_id, quote.tenant_id)
    if job and job.status == "awaiting_go_ahead":
        job.status = "go_ahead" if payload.decision == "approved" else "no_go"
        session.add(job)
        session.add(
            JobStatusHistory(
                tenant_id=job.tenant_id,
                repair_job_id=job.id,
                old_status="awaiting_go_ahead",
                new_status=job.status,
                changed_by_user_id=None,
                change_note=f"Customer {payload.decision} quote",
            )
        )
        event_type = "quote_approved" if payload.decision == "approved" else "quote_declined"
        event_summary = (
            f"Customer approved quote for job #{job.job_number}" if payload.decision == "approved"
            else f"Customer declined quote for job #{job.job_number} — return watch"
        )
        session.add(
            TenantEventLog(
                tenant_id=job.tenant_id,
                actor_user_id=None,
                entity_type="repair_job",
                entity_id=job.id,
                event_type=event_type,
                event_summary=event_summary,
            )
        )

    session.commit()

    return QuoteDecisionResponse(
        quote_id=quote.id,
        status=quote.status,
        decision=payload.decision,
    )


@router.get("/public/quotes/{token}")
@limiter.limit(get_public_quote_rate_limit)
def get_public_quote(request: Request, token: str, session: Session = Depends(get_session)):
    quote = session.exec(select(Quote).where(Quote.approval_token == token)).first()
    if not quote:
        raise HTTPException(status_code=404, detail="Invalid token")
    if _quote_token_is_expired(quote):
        if quote.status not in {"approved", "declined"}:
            quote.status = "expired"
            session.add(quote)
            session.commit()
        raise HTTPException(status_code=410, detail="Quote approval link has expired")
    items = session.exec(select(QuoteLineItem).where(QuoteLineItem.quote_id == quote.id)).all()
    return {
        "id": quote.id,
        "status": quote.status,
        "subtotal_cents": quote.subtotal_cents,
        "discount_cents": quote.discount_cents,
        "tax_cents": quote.tax_cents,
        "total_cents": quote.total_cents,
        "currency": quote.currency,
        "sent_at": quote.sent_at,
        "approval_token_expires_at": quote.approval_token_expires_at,
        "line_items": [
            {
                "item_type": i.item_type,
                "description": i.description,
                "quantity": i.quantity,
                "unit_price_cents": i.unit_price_cents,
                "total_price_cents": i.total_price_cents,
            }
            for i in items
        ],
    }
