from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlmodel import Session, SQLModel, delete, func, select

from ..database import get_session
from ..dependencies import AuthContext, enforce_plan_limit, get_auth_context, require_feature, require_tech_or_above
from .. import sms
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
    User,
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
    customer_id: UUID | None = Query(default=None, description="Filter by customer"),
    active_only: bool = Query(default=False, description="Exclude completed, collected, no_go"),
    date_from: str | None = Query(default=None, description="Filter scheduled_at >= date (YYYY-MM-DD)"),
    date_to: str | None = Query(default=None, description="Filter scheduled_at <= date (YYYY-MM-DD)"),
    include_unscheduled: bool = Query(default=False, description="With date range, also include jobs with no scheduled_at"),
    assigned_user_id: UUID | None = Query(default=None),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    from datetime import datetime as dt
    from sqlalchemy import or_

    query = select(AutoKeyJob).where(AutoKeyJob.tenant_id == auth.tenant_id)
    if status:
        query = query.where(AutoKeyJob.status == status)
    if customer_id:
        query = query.where(AutoKeyJob.customer_id == customer_id)
    if active_only:
        query = query.where(AutoKeyJob.status.notin_(["completed", "collected", "no_go"]))
    if assigned_user_id:
        query = query.where(AutoKeyJob.assigned_user_id == assigned_user_id)
    if date_from or date_to:
        if date_from and date_to and include_unscheduled:
            try:
                start = dt.strptime(date_from, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                end = dt.strptime(date_to + " 23:59:59", "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                query = query.where(
                    or_(
                        (AutoKeyJob.scheduled_at >= start) & (AutoKeyJob.scheduled_at <= end),
                        AutoKeyJob.scheduled_at.is_(None),
                    )
                )
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD for date_from/date_to")
        else:
            if date_from:
                try:
                    start = dt.strptime(date_from, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                    query = query.where(AutoKeyJob.scheduled_at >= start)
                except ValueError:
                    raise HTTPException(status_code=400, detail="Invalid date_from format. Use YYYY-MM-DD")
            if date_to:
                try:
                    end = dt.strptime(date_to + " 23:59:59", "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                    query = query.where(AutoKeyJob.scheduled_at <= end)
                except ValueError:
                    raise HTTPException(status_code=400, detail="Invalid date_to format. Use YYYY-MM-DD")
    return session.exec(
        query.order_by(
            AutoKeyJob.scheduled_at.asc(),
            AutoKeyJob.visit_order.asc(),
            AutoKeyJob.created_at.desc(),
        )
    ).all()


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

          # Permit auto-invoicing for any actionable quote state; only declined
          # quotes should be blocked from creating an invoice on completion.
          if latest_quote and latest_quote.status != "declined":
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

    schedule_fields = {"scheduled_at", "job_address", "job_type"}
    old_scheduled_at = job.scheduled_at.isoformat() if job.scheduled_at else None
    old_job_address = job.job_address
    old_job_type = job.job_type

    update_data = payload.model_dump(exclude_unset=True)
    if "customer_account_id" in update_data and update_data["customer_account_id"] is not None:
        account = session.get(CustomerAccount, update_data["customer_account_id"])
        if not account or account.tenant_id != auth.tenant_id:
            raise HTTPException(status_code=404, detail="Customer account not found")
    for field, value in update_data.items():
        setattr(job, field, value)

    if job.key_quantity < 1:
        job.key_quantity = 1

    schedule_changed = update_data.keys() & schedule_fields and (
        (job.scheduled_at.isoformat() if job.scheduled_at else None) != old_scheduled_at
        or job.job_address != old_job_address
        or job.job_type != old_job_type
    )
    to_notify_phone = None
    if schedule_changed and job.assigned_user_id:
        assigned_user = session.get(User, job.assigned_user_id)
        if assigned_user and assigned_user.phone and assigned_user.phone.strip():
            to_notify_phone = assigned_user.phone.strip()

    session.add(job)
    session.commit()

    if to_notify_phone:
        sms.notify_auto_key_schedule_changed(
            session,
            tenant_id=auth.tenant_id,
            to_phone=to_notify_phone,
            job_number=job.job_number,
            scheduled_at=job.scheduled_at.isoformat() if job.scheduled_at else None,
            job_address=job.job_address,
            job_type=job.job_type,
        )
        session.commit()

    if schedule_changed and job.job_address and job.scheduled_at and job.customer_id:
        customer = session.get(Customer, job.customer_id)
        if customer and customer.phone and customer.phone.strip():
            sms.notify_auto_key_customer_scheduled(
                session,
                tenant_id=auth.tenant_id,
                to_phone=customer.phone.strip(),
                customer_name=customer.full_name or "Customer",
                job_number=job.job_number,
                scheduled_at=job.scheduled_at.isoformat(),
                job_address=job.job_address,
            )
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
            payment_method=getattr(i, "payment_method", None),
            paid_at=getattr(i, "paid_at", None),
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
        payment_method=getattr(invoice, "payment_method", None),
        paid_at=getattr(invoice, "paid_at", None),
        created_at=invoice.created_at,
    )


class AutoKeyInvoiceUpdate(SQLModel):
    status: str | None = None
    payment_method: str | None = None  # cash, eftpos, bank


@router.patch("/{job_id}/invoices/{invoice_id}", response_model=AutoKeyInvoiceRead)
def update_auto_key_invoice(
    job_id: UUID,
    invoice_id: UUID,
    payload: AutoKeyInvoiceUpdate,
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    """Update auto key invoice (e.g. mark paid for POS completion)."""
    invoice = session.get(AutoKeyInvoice, invoice_id)
    if not invoice or invoice.tenant_id != auth.tenant_id or invoice.auto_key_job_id != job_id:
        raise HTTPException(status_code=404, detail="Auto key invoice not found")
    if payload.status is not None:
        if payload.status not in ("unpaid", "paid", "void"):
            raise HTTPException(status_code=400, detail="Invalid status")
        invoice.status = payload.status
        if payload.status == "paid":
            invoice.paid_at = datetime.now(timezone.utc)
        elif payload.status == "unpaid":
            invoice.paid_at = None
    if payload.payment_method is not None:
        v = (payload.payment_method or "").strip().lower()
        if v and v not in ("cash", "eftpos", "bank"):
            raise HTTPException(status_code=400, detail="Invalid payment_method; use cash, eftpos, or bank")
        invoice.payment_method = v or None
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
        payment_method=getattr(invoice, "payment_method", None),
        paid_at=getattr(invoice, "paid_at", None),
        created_at=invoice.created_at,
    )


@router.post("/send-day-before-reminders", summary="Send SMS reminders to techs and customers for tomorrow's jobs")
def send_day_before_reminders(
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    """Call from a daily cron (e.g. 6pm) to remind assigned techs and customers of tomorrow's scheduled jobs."""
    now = datetime.now(timezone.utc)
    tomorrow_start = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_end = tomorrow_start + timedelta(days=1)
    jobs = list(session.exec(
        select(AutoKeyJob)
        .where(AutoKeyJob.tenant_id == auth.tenant_id)
        .where(AutoKeyJob.scheduled_at >= tomorrow_start)
        .where(AutoKeyJob.scheduled_at < tomorrow_end)
    ).all())
    techs_notified = 0
    customers_notified = 0

    # Tech reminders (jobs with assigned tech)
    by_tech: dict[UUID, list[AutoKeyJob]] = {}
    for job in jobs:
        uid = job.assigned_user_id
        if uid:
            by_tech.setdefault(uid, []).append(job)
    for uid, job_list in by_tech.items():
        user = session.get(User, uid)
        if not user or not user.phone or not user.phone.strip():
            continue
        summaries = [f"#{j.job_number} {j.title or 'Auto key'}" for j in job_list]
        sms.notify_auto_key_day_before_reminder(
            session,
            tenant_id=auth.tenant_id,
            to_phone=user.phone.strip(),
            job_summaries=summaries,
        )
        session.commit()
        techs_notified += 1

    # Customer reminders (mobile jobs with customer phone)
    seen_customers: set[UUID] = set()
    for job in jobs:
        if not job.job_address or not job.customer_id or job.customer_id in seen_customers:
            continue
        customer = session.get(Customer, job.customer_id)
        if not customer or not customer.phone or not customer.phone.strip():
            continue
        sms.notify_auto_key_customer_day_before(
            session,
            tenant_id=auth.tenant_id,
            to_phone=customer.phone.strip(),
            customer_name=customer.full_name or "Customer",
            job_number=job.job_number,
            scheduled_at=job.scheduled_at.isoformat() if job.scheduled_at else None,
            job_address=job.job_address,
        )
        session.commit()
        seen_customers.add(job.customer_id)
        customers_notified += 1

    return {"techs_notified": techs_notified, "customers_notified": customers_notified}


class SendArrivalSmsPayload(SQLModel):
    time_window: str  # e.g. "9–11am", "2–4pm"


@router.post("/{job_id}/send-arrival-sms", summary="Send arrival window SMS to customer")
def send_arrival_sms(
    job_id: UUID,
    payload: SendArrivalSmsPayload,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    """Send 'Tech arriving between [time_window]' SMS to the job's customer."""
    job = session.get(AutoKeyJob, job_id)
    if not job or job.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Job not found")
    customer = session.get(Customer, job.customer_id) if job.customer_id else None
    if not customer or not customer.phone or not customer.phone.strip():
        raise HTTPException(status_code=400, detail="Customer has no phone number")
    time_window = (payload.time_window or "").strip()
    if not time_window:
        raise HTTPException(status_code=400, detail="Time window is required")
    sms.notify_auto_key_arrival_window(
        session,
        tenant_id=auth.tenant_id,
        to_phone=customer.phone.strip(),
        customer_name=customer.full_name or "Customer",
        job_number=job.job_number,
        time_window=time_window,
    )
    session.commit()
    return {"sent": True}
