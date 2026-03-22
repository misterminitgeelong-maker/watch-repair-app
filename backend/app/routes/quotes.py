from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select

from ..database import get_session
from ..dependencies import AuthContext, get_auth_context
from ..models import (
    Approval,
    Customer,
    Quote,
    QuoteCreate,
    QuoteDecisionRequest,
    QuoteDecisionResponse,
    QuoteLineItem,
    QuoteRead,
    QuoteSendResponse,
    Watch,
)
from ..limiter import limiter
from ..tenant_helpers import get_tenant_quote, get_tenant_repair_job
from .. import sms

router = APIRouter(prefix="/v1", tags=["quotes"])


@router.get("/quotes", response_model=list[QuoteRead])
def list_quotes(
    repair_job_id: UUID | None = None,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    query = select(Quote).where(Quote.tenant_id == auth.tenant_id)
    if repair_job_id:
        query = query.where(Quote.repair_job_id == repair_job_id)
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
        tax_cents=payload.tax_cents,
        total_cents=subtotal + payload.tax_cents,
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

    quote.status = "sent"
    quote.sent_at = datetime.now(timezone.utc)
    session.add(quote)

    # Send SMS to customer if they have a phone number
    job = get_tenant_repair_job(session, quote.repair_job_id, auth.tenant_id)
    if job:
        watch = session.get(Watch, job.watch_id)
        if watch:
            customer = session.get(Customer, watch.customer_id)
            if customer and customer.phone:
                sms.notify_quote_sent(
                    session,
                    tenant_id=auth.tenant_id,
                    repair_job_id=job.id,
                    customer_name=customer.full_name,
                    to_phone=customer.phone,
                    total_cents=quote.total_cents,
                    approval_token=quote.approval_token,
                )
            if customer and customer.email:
                from ..email_client import send_quote_sent_email
                send_quote_sent_email(
                    to_email=customer.email,
                    customer_name=customer.full_name,
                    total_cents=quote.total_cents,
                    approval_token=quote.approval_token,
                    job_number=job.job_number,
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
@limiter.limit("20/minute")
def quote_decision(
    request: Request,
    token: str,
    payload: QuoteDecisionRequest,
    session: Session = Depends(get_session),
):
    quote = session.exec(select(Quote).where(Quote.approval_token == token)).first()
    if not quote:
        raise HTTPException(status_code=404, detail="Invalid token")

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
    session.commit()

    return QuoteDecisionResponse(
        quote_id=quote.id,
        status=quote.status,
        decision=payload.decision,
    )


@router.get("/public/quotes/{token}")
@limiter.limit("30/minute")
def get_public_quote(request: Request, token: str, session: Session = Depends(get_session)):
    quote = session.exec(select(Quote).where(Quote.approval_token == token)).first()
    if not quote:
        raise HTTPException(status_code=404, detail="Invalid or expired link")
    items = session.exec(select(QuoteLineItem).where(QuoteLineItem.quote_id == quote.id)).all()
    return {
        "id": quote.id,
        "status": quote.status,
        "subtotal_cents": quote.subtotal_cents,
        "tax_cents": quote.tax_cents,
        "total_cents": quote.total_cents,
        "currency": quote.currency,
        "sent_at": quote.sent_at,
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
