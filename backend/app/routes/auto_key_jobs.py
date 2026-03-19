from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlmodel import Session, delete, func, select

from ..database import get_session
from ..dependencies import AuthContext, enforce_plan_limit, get_auth_context, require_feature, require_tech_or_above
from ..models import (
    AutoKeyJob,
    AutoKeyJobCreate,
    AutoKeyJobFieldUpdate,
    AutoKeyInvoice,
    AutoKeyInvoiceRead,
    AutoKeyJobRead,
    AutoKeyJobStatusUpdate,
    AutoKeyQuote,
    AutoKeyQuoteCreate,
    AutoKeyQuoteLineItem,
    AutoKeyQuoteLineItemRead,
    AutoKeyQuoteRead,
    Customer,
    CustomerAccount,
    CustomerAccountMembership,
)

router = APIRouter(
    prefix="/v1/auto-key-jobs",
    tags=["auto-key-jobs"],
    dependencies=[Depends(require_feature("auto_key"))],
)


def _next_auto_key_job_number(session: Session, tenant_id: UUID) -> str:
    count = session.exec(
        select(func.count()).select_from(AutoKeyJob).where(AutoKeyJob.tenant_id == tenant_id)
    ).one()
    return f"AK-{int(count) + 1:05d}"


def _next_auto_key_invoice_number(session: Session, tenant_id: UUID) -> str:
    count = session.exec(
        select(func.count()).select_from(AutoKeyInvoice).where(AutoKeyInvoice.tenant_id == tenant_id)
    ).one()
    return f"AKI-{int(count) + 1:05d}"


def _to_quote_read(session: Session, quote: AutoKeyQuote) -> AutoKeyQuoteRead:
    items = session.exec(
        select(AutoKeyQuoteLineItem)
        .where(AutoKeyQuoteLineItem.auto_key_quote_id == quote.id)
        .order_by(AutoKeyQuoteLineItem.created_at)
    ).all()
    return AutoKeyQuoteRead(
        id=quote.id,
        tenant_id=quote.tenant_id,
        auto_key_job_id=quote.auto_key_job_id,
        status=quote.status,
        subtotal_cents=quote.subtotal_cents,
        tax_cents=quote.tax_cents,
        total_cents=quote.total_cents,
        currency=quote.currency,
        sent_at=quote.sent_at,
        created_at=quote.created_at,
        line_items=[
            AutoKeyQuoteLineItemRead(
                id=i.id,
                auto_key_quote_id=i.auto_key_quote_id,
                description=i.description,
                quantity=i.quantity,
                unit_price_cents=i.unit_price_cents,
                total_price_cents=i.total_price_cents,
            )
            for i in items
        ],
    )


@router.post("", response_model=AutoKeyJobRead, status_code=201)
def create_auto_key_job(
    payload: AutoKeyJobCreate,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    # Plan limit check
    ak_count = int(
        session.exec(
            select(func.count()).select_from(AutoKeyJob).where(AutoKeyJob.tenant_id == auth.tenant_id)
        ).one()
    )
    enforce_plan_limit(auth, "auto_key_job", ak_count)

    customer = session.get(Customer, payload.customer_id)
    if not customer or customer.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Customer not found")

    customer_account_id = payload.customer_account_id
    if customer_account_id:
        account = session.get(CustomerAccount, customer_account_id)
        if not account or account.tenant_id != auth.tenant_id:
            raise HTTPException(status_code=404, detail="Customer account not found")
    else:
        inferred = session.exec(
            select(CustomerAccountMembership)
            .where(CustomerAccountMembership.tenant_id == auth.tenant_id)
            .where(CustomerAccountMembership.customer_id == payload.customer_id)
            .order_by(CustomerAccountMembership.created_at)
        ).first()
        customer_account_id = inferred.customer_account_id if inferred else None

    data = payload.model_dump()
    data["key_quantity"] = max(1, int(data.get("key_quantity", 1)))
    data["customer_account_id"] = customer_account_id

    job = AutoKeyJob(
        tenant_id=auth.tenant_id,
        job_number=_next_auto_key_job_number(session, auth.tenant_id),
        **data,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


@router.get("", response_model=list[AutoKeyJobRead])
def list_auto_key_jobs(
    status: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=500, ge=1, le=2000),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    query = select(AutoKeyJob).where(AutoKeyJob.tenant_id == auth.tenant_id)
    if status:
        query = query.where(AutoKeyJob.status == status)
    return session.exec(query.order_by(AutoKeyJob.created_at.desc()).offset(skip).limit(limit)).all()


@router.get("/{job_id}", response_model=AutoKeyJobRead)
def get_auto_key_job(
    job_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    job = session.get(AutoKeyJob, job_id)
    if not job or job.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Auto key job not found")
    return job


@router.post("/{job_id}/status", response_model=AutoKeyJobRead)
def update_auto_key_job_status(
    job_id: UUID,
    payload: AutoKeyJobStatusUpdate,
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    job = session.get(AutoKeyJob, job_id)
    if not job or job.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Auto key job not found")

    previous_status = job.status
    job.status = payload.status
    session.add(job)

    # Auto-create invoice on completion when a quote exists and no invoice is present yet.
    moved_to_completed = previous_status != "completed" and job.status == "completed"
    if moved_to_completed:
      existing_invoice = session.exec(
          select(AutoKeyInvoice)
          .where(AutoKeyInvoice.tenant_id == auth.tenant_id)
          .where(AutoKeyInvoice.auto_key_job_id == job.id)
      ).first()

      if not existing_invoice:
          latest_quote = session.exec(
              select(AutoKeyQuote)
              .where(AutoKeyQuote.tenant_id == auth.tenant_id)
              .where(AutoKeyQuote.auto_key_job_id == job.id)
              .order_by(AutoKeyQuote.created_at.desc())
          ).first()

          if latest_quote:
              session.add(
                  AutoKeyInvoice(
                      tenant_id=auth.tenant_id,
                      auto_key_job_id=job.id,
                      auto_key_quote_id=latest_quote.id,
                      invoice_number=_next_auto_key_invoice_number(session, auth.tenant_id),
                      subtotal_cents=latest_quote.subtotal_cents,
                      tax_cents=latest_quote.tax_cents,
                      total_cents=latest_quote.total_cents,
                      currency=latest_quote.currency,
                  )
              )

    session.commit()
    session.refresh(job)
    return job


@router.patch("/{job_id}", response_model=AutoKeyJobRead)
def update_auto_key_job_fields(
    job_id: UUID,
    payload: AutoKeyJobFieldUpdate,
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    job = session.get(AutoKeyJob, job_id)
    if not job or job.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Auto key job not found")

    update_data = payload.model_dump(exclude_unset=True)
    if "customer_account_id" in update_data and update_data["customer_account_id"] is not None:
        account = session.get(CustomerAccount, update_data["customer_account_id"])
        if not account or account.tenant_id != auth.tenant_id:
            raise HTTPException(status_code=404, detail="Customer account not found")
    for field, value in update_data.items():
        setattr(job, field, value)

    if job.key_quantity < 1:
        job.key_quantity = 1

    session.add(job)
    session.commit()
    session.refresh(job)
    return job


@router.delete("/{job_id}", status_code=204, response_class=Response)
def delete_auto_key_job(
    job_id: UUID,
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    job = session.get(AutoKeyJob, job_id)
    if not job or job.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Auto key job not found")

    quote_ids = session.exec(
        select(AutoKeyQuote.id)
        .where(AutoKeyQuote.tenant_id == auth.tenant_id)
        .where(AutoKeyQuote.auto_key_job_id == job_id)
    ).all()

    session.exec(
        delete(AutoKeyInvoice)
        .where(AutoKeyInvoice.tenant_id == auth.tenant_id)
        .where(AutoKeyInvoice.auto_key_job_id == job_id)
    )
    if quote_ids:
        session.exec(
            delete(AutoKeyQuoteLineItem)
            .where(AutoKeyQuoteLineItem.tenant_id == auth.tenant_id)
            .where(AutoKeyQuoteLineItem.auto_key_quote_id.in_(quote_ids))
        )
        session.exec(
            delete(AutoKeyQuote)
            .where(AutoKeyQuote.tenant_id == auth.tenant_id)
            .where(AutoKeyQuote.id.in_(quote_ids))
        )

    session.delete(job)
    session.commit()
    return Response(status_code=204)


@router.get("/{job_id}/quotes", response_model=list[AutoKeyQuoteRead])
def list_auto_key_quotes(
    job_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    job = session.get(AutoKeyJob, job_id)
    if not job or job.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Auto key job not found")

    quotes = session.exec(
        select(AutoKeyQuote)
        .where(AutoKeyQuote.tenant_id == auth.tenant_id)
        .where(AutoKeyQuote.auto_key_job_id == job_id)
        .order_by(AutoKeyQuote.created_at.desc())
    ).all()
    return [_to_quote_read(session, q) for q in quotes]


@router.post("/{job_id}/quotes", response_model=AutoKeyQuoteRead, status_code=201)
def create_auto_key_quote(
    job_id: UUID,
    payload: AutoKeyQuoteCreate,
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    job = session.get(AutoKeyJob, job_id)
    if not job or job.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Auto key job not found")
    if not payload.line_items:
        raise HTTPException(status_code=400, detail="At least one line item is required")

    subtotal = 0
    quote = AutoKeyQuote(
        tenant_id=auth.tenant_id,
        auto_key_job_id=job_id,
        tax_cents=max(0, payload.tax_cents),
    )
    session.add(quote)
    session.flush()

    for item in payload.line_items:
        total_price = int(round(item.quantity * item.unit_price_cents))
        subtotal += total_price
        session.add(
            AutoKeyQuoteLineItem(
                tenant_id=auth.tenant_id,
                auto_key_quote_id=quote.id,
                description=item.description,
                quantity=item.quantity,
                unit_price_cents=item.unit_price_cents,
                total_price_cents=total_price,
            )
        )

    quote.subtotal_cents = subtotal
    quote.total_cents = subtotal + quote.tax_cents
    session.add(quote)
    session.commit()
    session.refresh(quote)
    return _to_quote_read(session, quote)


@router.post("/quotes/{quote_id}/send", response_model=AutoKeyQuoteRead)
def send_auto_key_quote(
    quote_id: UUID,
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    quote = session.get(AutoKeyQuote, quote_id)
    if not quote or quote.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Auto key quote not found")

    quote.status = "sent"
    quote.sent_at = datetime.now(timezone.utc)
    session.add(quote)
    session.commit()
    session.refresh(quote)
    return _to_quote_read(session, quote)


@router.get("/{job_id}/invoices", response_model=list[AutoKeyInvoiceRead])
def list_auto_key_invoices(
    job_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    job = session.get(AutoKeyJob, job_id)
    if not job or job.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Auto key job not found")

    invoices = session.exec(
        select(AutoKeyInvoice)
        .where(AutoKeyInvoice.tenant_id == auth.tenant_id)
        .where(AutoKeyInvoice.auto_key_job_id == job_id)
        .order_by(AutoKeyInvoice.created_at.desc())
    ).all()
    return [
        AutoKeyInvoiceRead(
            id=i.id,
            tenant_id=i.tenant_id,
            auto_key_job_id=i.auto_key_job_id,
            auto_key_quote_id=i.auto_key_quote_id,
            invoice_number=i.invoice_number,
            status=i.status,
            subtotal_cents=i.subtotal_cents,
            tax_cents=i.tax_cents,
            total_cents=i.total_cents,
            currency=i.currency,
            created_at=i.created_at,
        )
        for i in invoices
    ]


@router.post("/{job_id}/invoices/from-quote/{quote_id}", response_model=AutoKeyInvoiceRead, status_code=201)
def create_auto_key_invoice_from_quote(
    job_id: UUID,
    quote_id: UUID,
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    job = session.get(AutoKeyJob, job_id)
    if not job or job.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Auto key job not found")

    quote = session.get(AutoKeyQuote, quote_id)
    if not quote or quote.tenant_id != auth.tenant_id or quote.auto_key_job_id != job_id:
        raise HTTPException(status_code=404, detail="Auto key quote not found")

    existing = session.exec(
        select(AutoKeyInvoice)
        .where(AutoKeyInvoice.tenant_id == auth.tenant_id)
        .where(AutoKeyInvoice.auto_key_quote_id == quote_id)
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Invoice already exists for this quote")

    invoice = AutoKeyInvoice(
        tenant_id=auth.tenant_id,
        auto_key_job_id=job_id,
        auto_key_quote_id=quote_id,
        invoice_number=_next_auto_key_invoice_number(session, auth.tenant_id),
        subtotal_cents=quote.subtotal_cents,
        tax_cents=quote.tax_cents,
        total_cents=quote.total_cents,
        currency=quote.currency,
    )
    session.add(invoice)
    session.commit()
    session.refresh(invoice)
    return AutoKeyInvoiceRead(
        id=invoice.id,
        tenant_id=invoice.tenant_id,
        auto_key_job_id=invoice.auto_key_job_id,
        auto_key_quote_id=invoice.auto_key_quote_id,
        invoice_number=invoice.invoice_number,
        status=invoice.status,
        subtotal_cents=invoice.subtotal_cents,
        tax_cents=invoice.tax_cents,
        total_cents=invoice.total_cents,
        currency=invoice.currency,
        created_at=invoice.created_at,
    )
