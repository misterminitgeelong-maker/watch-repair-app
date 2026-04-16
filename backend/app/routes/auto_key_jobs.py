import logging
import re
from datetime import date as date_type
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response
from sqlmodel import Session, delete, func, select

from ..auto_key_quote_suggestions import gst_tax_cents, suggest_line_items
from ..config import settings
from ..database import get_session
from ..dependencies import AuthContext, enforce_plan_limit, get_auth_context, require_feature, require_tech_or_above
from ..models import (
    AutoKeyJob,
    AutoKeyJobCreate,
    AutoKeyJobFieldUpdate,
    AutoKeyQuickIntakeCreate,
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
    Tenant,
)
from ..sms import (
    notify_auto_key_arrival_window,
    notify_auto_key_customer_day_before,
    notify_auto_key_customer_intake,
    notify_auto_key_en_route,
    notify_auto_key_invoice_ready,
    notify_auto_key_quote_sent,
)

router = APIRouter(
    prefix="/v1/auto-key-jobs",
    tags=["auto-key-jobs"],
    dependencies=[Depends(require_feature("auto_key"))],
)


_AUTO_KEY_FINAL_STATUSES = {"work_completed", "invoice_paid", "failed_job"}
logger = logging.getLogger(__name__)


def _next_prefixed_number(
    session: Session,
    *,
    tenant_id: UUID,
    model: type[AutoKeyJob] | type[AutoKeyInvoice],
    field_name: str,
    prefix: str,
) -> str:
    field = getattr(model, field_name)
    rows = session.exec(
        select(field)
        .where(model.tenant_id == tenant_id)
        .where(field.like(f"{prefix}-%"))
    ).all()
    max_seq = 0
    pat = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
    for raw in rows:
        value = str(raw or "")
        m = pat.match(value)
        if not m:
            continue
        max_seq = max(max_seq, int(m.group(1)))
    candidate = max_seq + 1
    while True:
        number = f"{prefix}-{candidate:05d}"
        exists = session.exec(
            select(model.id).where(model.tenant_id == tenant_id).where(field == number)
        ).first()
        if not exists:
            return number
        candidate += 1


def _next_auto_key_job_number(session: Session, tenant_id: UUID) -> str:
    return _next_prefixed_number(
        session,
        tenant_id=tenant_id,
        model=AutoKeyJob,
        field_name="job_number",
        prefix="AK",
    )


def _next_auto_key_invoice_number(session: Session, tenant_id: UUID) -> str:
    return _next_prefixed_number(
        session,
        tenant_id=tenant_id,
        model=AutoKeyInvoice,
        field_name="invoice_number",
        prefix="AKI",
    )


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


def _to_invoice_read(invoice: AutoKeyInvoice) -> AutoKeyInvoiceRead:
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
        payment_method=invoice.payment_method,
        paid_at=invoice.paid_at,
        created_at=invoice.created_at,
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
    logger.info("auto_key_job.created tenant=%s job=%s customer=%s", auth.tenant_id, job.id, job.customer_id)
    return job


@router.post("/quick-intake", response_model=AutoKeyJobRead, status_code=201)
def create_auto_key_quick_intake(
    payload: AutoKeyQuickIntakeCreate,
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    phone = (payload.phone or "").strip()
    full_name = (payload.full_name or "").strip() or "Customer"
    if not phone:
        raise HTTPException(status_code=400, detail="Phone number is required")

    customer = Customer(
        tenant_id=auth.tenant_id,
        full_name=full_name,
        phone=phone,
    )
    session.add(customer)
    session.flush()

    job = AutoKeyJob(
        tenant_id=auth.tenant_id,
        customer_id=customer.id,
        assigned_user_id=auth.user_id,
        job_number=_next_auto_key_job_number(session, auth.tenant_id),
        title=f"{full_name.split()[0]} - Job",
        status="awaiting_quote",
        programming_status="pending",
        key_quantity=1,
        customer_intake_token=uuid4().hex,
    )
    session.add(job)
    session.flush()

    intake_url = f"{settings.public_base_url.rstrip('/')}/mobile-intake/{job.customer_intake_token}"
    try:
        notify_auto_key_customer_intake(
            session,
            tenant_id=auth.tenant_id,
            to_phone=phone,
            customer_name=full_name,
            shop_name="Workshop",
            job_number=job.job_number,
            intake_url=intake_url,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("auto_key_job.quick_intake_sms_failed tenant=%s job=%s err=%s", auth.tenant_id, job.id, exc)

    session.commit()
    session.refresh(job)
    logger.info("auto_key_job.quick_intake_created tenant=%s job=%s customer=%s", auth.tenant_id, job.id, customer.id)
    return AutoKeyJobRead(**job.model_dump(), customer_name=customer.full_name, customer_phone=customer.phone)


@router.get("", response_model=list[AutoKeyJobRead])
def list_auto_key_jobs(
    status: str | None = Query(default=None),
    customer_id: UUID | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=500, ge=1, le=2000),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    assigned_user_id: UUID | None = Query(default=None),
    include_unscheduled: bool = Query(default=False),
    active_only: bool = Query(default=False),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    query = select(AutoKeyJob).where(AutoKeyJob.tenant_id == auth.tenant_id)
    if status:
        query = query.where(AutoKeyJob.status == status)
    if customer_id:
        query = query.where(AutoKeyJob.customer_id == customer_id)
    if date_from or date_to:
        if date_from:
            df = date_type.fromisoformat(date_from)
            query = query.where(AutoKeyJob.scheduled_at >= df)
        if date_to:
            dt = date_type.fromisoformat(date_to)
            query = query.where(AutoKeyJob.scheduled_at < dt + timedelta(days=1))
        if not include_unscheduled:
            query = query.where(AutoKeyJob.scheduled_at.is_not(None))
    if assigned_user_id:
        query = query.where(AutoKeyJob.assigned_user_id == assigned_user_id)
    if active_only:
        query = query.where(AutoKeyJob.status.notin_(_AUTO_KEY_FINAL_STATUSES))
    jobs = session.exec(query.order_by(AutoKeyJob.created_at.desc()).offset(skip).limit(limit)).all()

    # Batch enrich with customer names
    customer_ids = list({j.customer_id for j in jobs})
    customers = session.exec(
        select(Customer).where(Customer.id.in_(customer_ids))
    ).all() if customer_ids else []
    cname_map = {c.id: c.full_name for c in customers}
    cphone_map = {c.id: c.phone for c in customers}

    return [
        AutoKeyJobRead(**j.model_dump(), customer_name=cname_map.get(j.customer_id), customer_phone=cphone_map.get(j.customer_id))
        for j in jobs
    ]


@router.get("/quote-suggestions")
def get_quote_suggestions(
    job_type: str | None = Query(default=None, max_length=120),
    key_quantity: int = Query(default=1, ge=1, le=100),
    pricing_tier: str = Query(default="retail", pattern="^(retail|b2b|tier1|tier2|tier3)$"),
    _auth=Depends(get_auth_context),
):
    """Return suggested line items and total for a given job type and pricing tier."""
    items = suggest_line_items(job_type, key_quantity, pricing_tier)
    subtotal = sum(int(round(q * p)) for _, q, p in items)
    tax = gst_tax_cents(subtotal)
    return {
        "pricing_tier": pricing_tier,
        "total_cents": subtotal + tax,
        "subtotal_cents": subtotal,
        "tax_cents": tax,
        "line_items": [
            {
                "id": str(i),
                "description": desc,
                "quantity": qty,
                "unit_price_cents": unit,
                "total_price_cents": int(round(qty * unit)),
            }
            for i, (desc, qty, unit) in enumerate(items)
        ],
    }


@router.post("/{job_id}/arrival-sms")
def send_arrival_sms(
    job_id: UUID,
    time_window: str | None = Body(default=None, embed=True),
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    job = session.get(AutoKeyJob, job_id)
    if not job or job.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Auto key job not found")
    customer = session.get(Customer, job.customer_id)
    if not customer or not (customer.phone or "").strip():
        raise HTTPException(status_code=400, detail="Customer phone is required to send SMS")
    first_name = ((customer.full_name or "").strip().split() or ["there"])[0]
    window = (time_window or "").strip() or "the scheduled window"
    notify_auto_key_arrival_window(
        session,
        tenant_id=auth.tenant_id,
        to_phone=(customer.phone or "").strip(),
        customer_name=first_name,
        job_number=job.job_number,
        time_window=window,
    )
    session.commit()
    logger.info("auto_key_job.arrival_sms_sent tenant=%s job=%s", auth.tenant_id, job_id)
    return {"ok": True}


@router.post("/day-before-reminders")
def send_day_before_reminders(
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    tomorrow = datetime.now(timezone.utc).date() + timedelta(days=1)
    start = datetime.combine(tomorrow, datetime.min.time(), tzinfo=timezone.utc).replace(tzinfo=None)
    end = start + timedelta(days=1)
    jobs = session.exec(
        select(AutoKeyJob)
        .where(AutoKeyJob.tenant_id == auth.tenant_id)
        .where(AutoKeyJob.scheduled_at.is_not(None))
        .where(AutoKeyJob.scheduled_at >= start)
        .where(AutoKeyJob.scheduled_at < end)
        .where(AutoKeyJob.status.notin_(_AUTO_KEY_FINAL_STATUSES))
    ).all()
    sent = 0
    for job in jobs:
        customer = session.get(Customer, job.customer_id)
        if not customer or not (customer.phone or "").strip():
            continue
        first_name = ((customer.full_name or "").strip().split() or ["there"])[0]
        notify_auto_key_customer_day_before(
            session,
            tenant_id=auth.tenant_id,
            to_phone=(customer.phone or "").strip(),
            customer_name=first_name,
            job_number=job.job_number,
            scheduled_at=job.scheduled_at.isoformat() if job.scheduled_at else None,
            job_address=job.job_address,
        )
        sent += 1
    session.commit()
    logger.info("auto_key_job.day_before_reminders_sent tenant=%s count=%s", auth.tenant_id, sent)
    return {"sent": sent}


@router.patch("/invoices/{invoice_id}", response_model=AutoKeyInvoiceRead)
def update_auto_key_invoice(
    invoice_id: UUID,
    status: str | None = Body(default=None),
    payment_method: str | None = Body(default=None),
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    invoice = session.get(AutoKeyInvoice, invoice_id)
    if not invoice or invoice.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if status is not None:
        next_status = status.strip().lower()
        if next_status not in {"unpaid", "paid", "void"}:
            raise HTTPException(status_code=400, detail="Invalid invoice status")
        invoice.status = next_status
        invoice.paid_at = datetime.now(timezone.utc) if next_status == "paid" else None
    if payment_method is not None:
        invoice.payment_method = payment_method.strip() or None
    session.add(invoice)
    session.commit()
    session.refresh(invoice)
    logger.info("auto_key_invoice.updated tenant=%s invoice=%s status=%s", auth.tenant_id, invoice_id, invoice.status)
    return _to_invoice_read(invoice)


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

    # Auto-create invoice on work_completed when no invoice is present yet.
    moved_to_completed = previous_status != "work_completed" and job.status == "work_completed"
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
              logger.info("auto_key_invoice.auto_create_from_quote tenant=%s job=%s quote=%s", auth.tenant_id, job.id, latest_quote.id)
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
                      customer_view_token=uuid4().hex,
                  )
              )
          else:
              logger.info("auto_key_invoice.auto_create_from_cost tenant=%s job=%s total=%s", auth.tenant_id, job.id, job.cost_cents)
              subtotal = max(0, int(round(job.cost_cents / 1.1))) if job.cost_cents > 0 else 0
              tax = max(0, int(job.cost_cents - subtotal))
              session.add(
                  AutoKeyInvoice(
                      tenant_id=auth.tenant_id,
                      auto_key_job_id=job.id,
                      invoice_number=_next_auto_key_invoice_number(session, auth.tenant_id),
                      subtotal_cents=subtotal,
                      tax_cents=tax,
                      total_cents=max(0, int(job.cost_cents)),
                      currency="AUD",
                      customer_view_token=uuid4().hex,
                  )
              )

    session.commit()
    session.refresh(job)

    # ── Post-commit side-effects (SMS) ────────────────────────────────────────
    moved_to_en_route = previous_status != "en_route" and job.status == "en_route"
    if moved_to_en_route or moved_to_completed:
        _customer = session.get(Customer, job.customer_id)
        _tenant = session.get(Tenant, auth.tenant_id)
        _shop_name = (_tenant.name if _tenant else None) or "Mobile Services"

        if moved_to_en_route and _customer and (_customer.phone or "").strip():
            try:
                _first = ((_customer.full_name or "").strip().split() or ["there"])[0]
                notify_auto_key_en_route(
                    session,
                    tenant_id=auth.tenant_id,
                    to_phone=_customer.phone.strip(),
                    customer_name=_first,
                    shop_name=_shop_name,
                    job_number=job.job_number,
                    job_address=job.job_address,
                    scheduled_at=job.scheduled_at,
                )
                session.commit()
                logger.info("auto_key_job.en_route_sms_sent tenant=%s job=%s", auth.tenant_id, job.id)
            except Exception:
                logger.exception("auto_key_job.en_route_sms_failed tenant=%s job=%s", auth.tenant_id, job.id)

        if moved_to_completed and _customer and (_customer.phone or "").strip():
            try:
                _invoice = session.exec(
                    select(AutoKeyInvoice)
                    .where(AutoKeyInvoice.tenant_id == auth.tenant_id)
                    .where(AutoKeyInvoice.auto_key_job_id == job.id)
                    .order_by(AutoKeyInvoice.created_at.desc())
                ).first()
                if _invoice:
                    _first = ((_customer.full_name or "").strip().split() or ["there"])[0]
                    _view_url = f"{settings.public_base_url.rstrip('/')}/mobile-invoice/{_invoice.customer_view_token}"
                    notify_auto_key_invoice_ready(
                        session,
                        tenant_id=auth.tenant_id,
                        to_phone=_customer.phone.strip(),
                        customer_name=_first,
                        shop_name=_shop_name,
                        job_number=job.job_number,
                        invoice_number=_invoice.invoice_number,
                        total_cents=_invoice.total_cents,
                        currency=_invoice.currency or "AUD",
                        view_url=_view_url,
                    )
                    session.commit()
                    logger.info("auto_key_job.work_completed_sms_sent tenant=%s job=%s invoice=%s", auth.tenant_id, job.id, _invoice.id)
            except Exception:
                logger.exception("auto_key_job.work_completed_sms_failed tenant=%s job=%s", auth.tenant_id, job.id)

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

    # Auto-advance job to quote_sent when not already past that stage
    _QUOTE_ADVANCE_FROM = {"awaiting_quote"}
    job = session.get(AutoKeyJob, quote.auto_key_job_id)
    if job and job.tenant_id == auth.tenant_id and job.status in _QUOTE_ADVANCE_FROM:
        job.status = "quote_sent"
        session.add(job)

    session.commit()
    session.refresh(quote)

    # Send quote SMS — wrapped so failures don't surface as errors
    if job and job.status == "quote_sent":
        try:
            _customer = session.get(Customer, job.customer_id)
            _tenant = session.get(Tenant, auth.tenant_id)
            if _customer and (_customer.phone or "").strip():
                _first = ((_customer.full_name or "").strip().split() or ["there"])[0]
                _shop = (_tenant.name if _tenant else None) or "Mobile Services"
                notify_auto_key_quote_sent(
                    session,
                    tenant_id=auth.tenant_id,
                    to_phone=_customer.phone.strip(),
                    customer_name=_first,
                    shop_name=_shop,
                    job_number=job.job_number,
                    total_cents=quote.total_cents,
                    currency=quote.currency or "AUD",
                )
                session.commit()
                logger.info("auto_key_quote.quote_sent_sms tenant=%s job=%s quote=%s", auth.tenant_id, job.id, quote.id)
        except Exception:
            logger.exception("auto_key_quote.quote_sent_sms_failed tenant=%s quote=%s", auth.tenant_id, quote_id)

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
    return [_to_invoice_read(i) for i in invoices]


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
        customer_view_token=uuid4().hex,
    )
    session.add(invoice)
    session.commit()
    session.refresh(invoice)
    return _to_invoice_read(invoice)
